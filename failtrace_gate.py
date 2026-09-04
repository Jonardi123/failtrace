#!/usr/bin/env python3
"""CLI for the framework-neutral coding-agent recovery gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from gate_report import gate_sources, github_lines, json_report, sarif_report, summary
from gate_rules import RULES, lint_events
from gate_schema import SEVERITY_ORDER, Event, Finding, normalize_row

# Re-export the small programmatic API from the CLI module for backwards-compatible
# imports and simple adapter tests.
__all__ = [
    "Event",
    "Finding",
    "RULES",
    "gate_sources",
    "github_lines",
    "json_report",
    "lint_events",
    "normalize_row",
    "sarif_report",
]


def _write_json(data: dict[str, Any], output: str | None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _emit_text(checked: int, findings: list[Finding]) -> None:
    for finding in findings:
        where = finding.source + (f":{finding.line}" if finding.line else "")
        print(
            f"{where} [{finding.run_id}] {finding.severity.upper()} "
            f"{finding.rule_id}: {finding.message} (event {finding.event_index})"
        )
    counts = summary(findings)
    print(
        f"Checked {checked} run(s): {counts['error']} error(s), "
        f"{counts['warning']} warning(s), {counts['note']} note(s)."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lint coding-agent execution traces for unsafe or looping recovery behavior."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="agenttrace.v1/failtrace.v1 JSONL files, directories, or globs; use - for stdin",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "sarif", "github"),
        default="text",
        help="output format",
    )
    parser.add_argument("-o", "--out", help="write JSON or SARIF output to a file")
    parser.add_argument(
        "--fail-on",
        choices=("note", "warning", "error", "never"),
        default="error",
        help="minimum severity that makes the command exit 1",
    )
    parser.add_argument("--max-findings", type=int, default=200)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_findings < 1:
        print("--max-findings must be >= 1", file=sys.stderr)
        return 2
    if args.out and args.format not in {"json", "sarif"}:
        print("--out is only supported with --format json or --format sarif", file=sys.stderr)
        return 2

    checked, findings = gate_sources(args.paths, max_findings=args.max_findings)
    if args.format == "json":
        _write_json(json_report(checked, findings), args.out)
    elif args.format == "sarif":
        _write_json(sarif_report(findings), args.out)
    elif args.format == "github":
        for line in github_lines(findings):
            print(line)
        counts = summary(findings)
        print(
            f"failtrace-gate: checked {checked} run(s); "
            f"{counts['error']} error(s), {counts['warning']} warning(s)"
        )
    else:
        _emit_text(checked, findings)

    if args.fail_on == "never":
        return 0
    threshold = SEVERITY_ORDER[args.fail_on]
    return 1 if any(SEVERITY_ORDER[f.severity] >= threshold for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
