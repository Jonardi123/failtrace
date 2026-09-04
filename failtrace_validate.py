#!/usr/bin/env python3
"""Validate failtrace.v1 JSONL datasets.

The validator is intentionally dependency-free so it can run in CI, pre-commit
hooks, or tiny training containers.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, TextIO


SCHEMA_VERSION = "failtrace.v1"
EXPECTED_TRACE = (
    ("assistant", "plan"),
    ("assistant", "tool_call"),
    ("tool", None),
    ("assistant", "diagnosis"),
    ("assistant", "plan_update"),
    ("assistant", "tool_call"),
    ("tool", None),
    ("assistant", "final"),
)


@dataclass(frozen=True)
class ValidationIssue:
    source: str
    line: int
    row_id: str | None
    message: str


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_row(row: Any) -> list[str]:
    """Return structural errors for one failtrace row."""
    errors: list[str] = []
    if not isinstance(row, dict):
        return ["row must be a JSON object"]

    if row.get("schema") != SCHEMA_VERSION:
        errors.append(f"schema must be {SCHEMA_VERSION!r}")

    for key in ("id", "category", "task"):
        if not _nonempty_string(row.get(key)):
            errors.append(f"{key} must be a non-empty string")

    if row.get("split") != "train":
        errors.append("split must be 'train'")

    plan = row.get("plan")
    if not isinstance(plan, list) or not plan or not all(_nonempty_string(x) for x in plan):
        errors.append("plan must be a non-empty list of non-empty strings")

    labels = row.get("labels")
    if not isinstance(labels, dict):
        errors.append("labels must be an object")
    else:
        if labels.get("should_retry") is not True:
            errors.append("labels.should_retry must be true")
        if labels.get("should_call_tool_after_fail") is not True:
            errors.append("labels.should_call_tool_after_fail must be true")
        if labels.get("failure_class") != row.get("category"):
            errors.append("labels.failure_class must equal category")

    trace = row.get("trace")
    if not isinstance(trace, list):
        errors.append("trace must be a list")
        return errors

    if len(trace) != len(EXPECTED_TRACE):
        errors.append(f"trace must contain exactly {len(EXPECTED_TRACE)} steps")
        return errors

    for index, (step, expected) in enumerate(zip(trace, EXPECTED_TRACE)):
        role, step_type = expected
        if not isinstance(step, dict):
            errors.append(f"trace[{index}] must be an object")
            continue
        if step.get("role") != role:
            errors.append(f"trace[{index}].role must be {role!r}")
        if step_type is None:
            if "type" in step:
                errors.append(f"trace[{index}] tool result must not contain type")
        elif step.get("type") != step_type:
            errors.append(f"trace[{index}].type must be {step_type!r}")

    if errors and any(not isinstance(step, dict) for step in trace):
        return errors

    failed_call, failed_result, recovered_call, recovered_result = trace[1], trace[2], trace[5], trace[6]

    if failed_result.get("ok") is not False:
        errors.append("first tool result must have ok=false")
    if not isinstance(failed_result.get("error"), dict) or not failed_result.get("error"):
        errors.append("failed tool result must contain a non-empty error object")
    if recovered_result.get("ok") is not True:
        errors.append("second tool result must have ok=true")
    if not isinstance(recovered_result.get("result"), dict):
        errors.append("successful tool result must contain a result object")

    for label, call in (("failed", failed_call), ("recovered", recovered_call)):
        if not _nonempty_string(call.get("tool")):
            errors.append(f"{label} tool_call.tool must be a non-empty string")
        if not isinstance(call.get("arguments"), dict):
            errors.append(f"{label} tool_call.arguments must be an object")

    if failed_call.get("tool") != failed_result.get("tool"):
        errors.append("failed tool_call.tool must match failed tool result tool")
    if recovered_call.get("tool") != recovered_result.get("tool"):
        errors.append("recovered tool_call.tool must match successful tool result tool")

    if (
        failed_call.get("tool") == recovered_call.get("tool")
        and failed_call.get("arguments") == recovered_call.get("arguments")
    ):
        errors.append("recovery must not repeat the exact failed tool call")

    return errors


def _rows_from_stream(stream: TextIO, source: str) -> Iterable[tuple[int, Any, str | None]]:
    for line_no, raw in enumerate(stream, 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            yield line_no, None, f"invalid JSON: {exc.msg} at column {exc.colno}"
            continue
        yield line_no, row, None


def validate_sources(paths: list[str], max_errors: int = 100) -> tuple[int, list[ValidationIssue]]:
    checked = 0
    issues: list[ValidationIssue] = []
    seen_ids: dict[str, tuple[str, int]] = {}

    for raw_path in paths:
        source = raw_path
        if raw_path == "-":
            stream = sys.stdin
            close = False
            source = "<stdin>"
        else:
            try:
                stream = Path(raw_path).open("r", encoding="utf-8")
            except OSError as exc:
                issues.append(ValidationIssue(raw_path, 0, None, f"cannot read file: {exc}"))
                if len(issues) >= max_errors:
                    break
                continue
            close = True

        try:
            for line_no, row, parse_error in _rows_from_stream(stream, source):
                if parse_error:
                    issues.append(ValidationIssue(source, line_no, None, parse_error))
                else:
                    checked += 1
                    row_id = row.get("id") if isinstance(row, dict) and isinstance(row.get("id"), str) else None
                    if row_id:
                        if row_id in seen_ids:
                            first_source, first_line = seen_ids[row_id]
                            issues.append(
                                ValidationIssue(
                                    source,
                                    line_no,
                                    row_id,
                                    f"duplicate id; first seen at {first_source}:{first_line}",
                                )
                            )
                        else:
                            seen_ids[row_id] = (source, line_no)
                    for message in validate_row(row):
                        issues.append(ValidationIssue(source, line_no, row_id, message))
                if len(issues) >= max_errors:
                    return checked, issues
        finally:
            if close:
                stream.close()

    return checked, issues


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate failtrace.v1 JSONL datasets.")
    parser.add_argument("paths", nargs="+", help="JSONL files to validate; use - for stdin")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable JSON report")
    parser.add_argument("--max-errors", type=int, default=100, help="stop after this many errors")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_errors < 1:
        print("--max-errors must be >= 1", file=sys.stderr)
        return 2

    checked, issues = validate_sources(args.paths, args.max_errors)
    if args.json:
        json.dump(
            {
                "schema": "failtrace.validation.v1",
                "valid": not issues,
                "rows_checked": checked,
                "issue_count": len(issues),
                "issues": [asdict(issue) for issue in issues],
            },
            sys.stdout,
            indent=2,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
    elif issues:
        for issue in issues:
            row = f" [{issue.row_id}]" if issue.row_id else ""
            where = f"{issue.source}:{issue.line}" if issue.line else issue.source
            print(f"{where}{row}: {issue.message}", file=sys.stderr)
        print(f"FAIL: {len(issues)} issue(s) across {checked} parsed row(s)", file=sys.stderr)
    else:
        print(f"OK: {checked} row(s) validated")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
