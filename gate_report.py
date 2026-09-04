"""Input expansion and machine-readable reports for failtrace-gate."""

from __future__ import annotations

import glob
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, TextIO

from gate_rules import RULES, lint_events
from gate_schema import Finding, normalize_row


def _rows_from_stream(stream: TextIO) -> Iterable[tuple[int, Any, str | None]]:
    for line_no, raw in enumerate(stream, 1):
        if not raw.strip():
            continue
        try:
            yield line_no, json.loads(raw), None
        except json.JSONDecodeError as exc:
            yield line_no, None, f"invalid JSON: {exc.msg} at column {exc.colno}"


def _split_patterns(patterns: list[str]) -> list[str]:
    out: list[str] = []
    for pattern in patterns:
        if pattern == "-":
            out.append(pattern)
            continue
        parts = [item.strip() for item in pattern.split(",") if item.strip()]
        out.extend(parts or [pattern])
    return out


def expand_paths(patterns: list[str]) -> list[str]:
    expanded: list[str] = []
    for pattern in _split_patterns(patterns):
        if pattern == "-":
            expanded.append(pattern)
            continue
        path = Path(pattern)
        if path.is_dir():
            matches = sorted(str(p) for p in path.rglob("*.jsonl") if p.is_file())
        else:
            matches = sorted(p for p in glob.glob(pattern, recursive=True) if Path(p).is_file())
        expanded.extend(matches or [pattern])

    deduped: list[str] = []
    seen: set[str] = set()
    for path in expanded:
        if path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped


def gate_sources(paths: list[str], max_findings: int = 200) -> tuple[int, list[Finding]]:
    checked = 0
    findings: list[Finding] = []

    for raw_path in expand_paths(paths):
        if len(findings) >= max_findings:
            break

        if raw_path == "-":
            source = "<stdin>"
            stream = sys.stdin
            close = False
        else:
            source = raw_path
            try:
                stream = Path(raw_path).open("r", encoding="utf-8")
            except OSError as exc:
                findings.append(
                    Finding(
                        "FT000",
                        "error",
                        source,
                        0,
                        "<unknown>",
                        0,
                        f"cannot read trace source: {exc}",
                    )
                )
                continue
            close = True

        try:
            for line_no, row, parse_error in _rows_from_stream(stream):
                if parse_error:
                    findings.append(
                        Finding(
                            "FT000",
                            "error",
                            source,
                            line_no,
                            "<unknown>",
                            0,
                            parse_error,
                        )
                    )
                else:
                    checked += 1
                    run_id, events, errors = normalize_row(row)
                    for message in errors:
                        findings.append(
                            Finding("FT000", "error", source, line_no, run_id, 0, message)
                        )
                    if not errors:
                        findings.extend(lint_events(run_id, events, source=source, line=line_no))
                if len(findings) >= max_findings:
                    return checked, findings[:max_findings]
        finally:
            if close:
                stream.close()

    return checked, findings[:max_findings]


def summary(findings: list[Finding]) -> dict[str, int]:
    result = {"error": 0, "warning": 0, "note": 0}
    for finding in findings:
        result[finding.severity] = result.get(finding.severity, 0) + 1
    return result


def json_report(checked: int, findings: list[Finding]) -> dict[str, Any]:
    return {
        "schema": "failtrace.gate.v1",
        "runs_checked": checked,
        "finding_count": len(findings),
        "summary": summary(findings),
        "findings": [asdict(item) for item in findings],
    }


def sarif_report(findings: list[Finding]) -> dict[str, Any]:
    rules = []
    for rule_id in sorted({f.rule_id for f in findings}):
        meta = RULES[rule_id]
        rules.append(
            {
                "id": rule_id,
                "name": meta["title"].replace(" ", ""),
                "shortDescription": {"text": meta["title"]},
                "fullDescription": {"text": meta["description"]},
                "defaultConfiguration": {"level": meta["severity"]},
            }
        )

    results = []
    for finding in findings:
        result: dict[str, Any] = {
            "ruleId": finding.rule_id,
            "level": finding.severity,
            "message": {
                "text": f"{finding.message} (run {finding.run_id}, event {finding.event_index})"
            },
        }
        if finding.source != "<stdin>" and finding.line > 0:
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding.source},
                        "region": {"startLine": finding.line},
                    }
                }
            ]
        results.append(result)

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "failtrace-gate",
                        "informationUri": "https://github.com/Jonardi123/failtrace",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }


def _escape_github(value: str, *, property_value: bool = False) -> str:
    value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if property_value:
        value = value.replace(":", "%3A").replace(",", "%2C")
    return value


def github_lines(findings: list[Finding]) -> list[str]:
    lines: list[str] = []
    for finding in findings:
        if finding.severity == "error":
            level = "error"
        elif finding.severity == "warning":
            level = "warning"
        else:
            level = "notice"
        properties = []
        if finding.source != "<stdin>" and finding.line > 0:
            properties.append(f"file={_escape_github(finding.source, property_value=True)}")
            properties.append(f"line={finding.line}")
        prop_text = " " + ",".join(properties) if properties else ""
        message = _escape_github(
            f"{finding.rule_id} {finding.message} "
            f"[run={finding.run_id} event={finding.event_index}]"
        )
        lines.append(f"::{level}{prop_text}::{message}")
    return lines
