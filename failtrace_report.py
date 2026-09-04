#!/usr/bin/env python3
"""Turn failtrace harness results into a compact regression report."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_results(path: str) -> list[dict[str, Any]]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    text = text.strip()
    if not text:
        raise ValueError("input is empty")

    if text.startswith("["):
        # harness.py --json prints a human summary after the JSON. Decode the
        # first JSON value and tolerate the trailing summary text.
        parsed, _end = json.JSONDecoder().raw_decode(text)
        if not isinstance(parsed, list):
            raise ValueError("JSON input must be an array")
        rows = parsed
    else:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]

    if not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("results must contain one or more JSON objects")
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    passed = sum(1 for row in rows if row.get("ok") is True)

    grouped: dict[str, list[bool]] = defaultdict(list)
    reasons: Counter[str] = Counter()
    for row in rows:
        category = str(row.get("category") or "unknown")
        grouped[category].append(row.get("ok") is True)
        if row.get("ok") is not True:
            for reason in row.get("reasons") or ["unspecified failure"]:
                reasons[str(reason)] += 1

    by_category = {}
    for category, values in sorted(grouped.items()):
        cat_passed = sum(values)
        by_category[category] = {
            "passed": cat_passed,
            "total": len(values),
            "pass_rate": cat_passed / len(values),
        }

    return {
        "schema": "failtrace.report.v1",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total,
        "by_category": by_category,
        "failure_reasons": [
            {"reason": reason, "count": count}
            for reason, count in reasons.most_common()
        ],
    }


def compare(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    categories = sorted(set(current["by_category"]) | set(baseline["by_category"]))
    category_delta = {}
    for category in categories:
        now = current["by_category"].get(category, {}).get("pass_rate")
        before = baseline["by_category"].get(category, {}).get("pass_rate")
        category_delta[category] = None if now is None or before is None else now - before
    return {
        "pass_rate_delta": current["pass_rate"] - baseline["pass_rate"],
        "by_category": category_delta,
    }


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_markdown(summary: dict[str, Any], title: str, delta: dict[str, Any] | None = None) -> str:
    lines = [
        f"# {title}",
        "",
        f"**Overall:** {summary['passed']}/{summary['total']} passed ({_pct(summary['pass_rate'])}).",
    ]
    if delta:
        sign = "+" if delta["pass_rate_delta"] >= 0 else ""
        lines.append(f" **Baseline delta:** {sign}{delta['pass_rate_delta'] * 100:.1f} pp.")
    lines += [
        "",
        "| Category | Passed | Pass rate |",
        "|---|---:|---:|",
    ]
    for category, data in summary["by_category"].items():
        suffix = ""
        if delta:
            d = delta["by_category"].get(category)
            if d is not None:
                suffix = f" ({'+' if d >= 0 else ''}{d * 100:.1f} pp)"
        lines.append(
            f"| `{category}` | {data['passed']}/{data['total']} | {_pct(data['pass_rate'])}{suffix} |"
        )

    lines += ["", "## Top failure reasons", ""]
    if summary["failure_reasons"]:
        for item in summary["failure_reasons"][:10]:
            lines.append(f"- {item['count']}× {item['reason']}")
    else:
        lines.append("No failures. 🎯")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize failtrace harness JSON.")
    parser.add_argument("results", help="JSON array or JSONL from the harness; use - for stdin")
    parser.add_argument("--baseline", help="optional previous results to compare against")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--title", default="Failtrace evaluation report")
    parser.add_argument("-o", "--out", help="write report here instead of stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        current = summarize(load_results(args.results))
        baseline = summarize(load_results(args.baseline)) if args.baseline else None
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"failtrace-report: {exc}", file=sys.stderr)
        return 2

    delta = compare(current, baseline) if baseline else None
    if args.format == "json":
        payload: dict[str, Any] = dict(current)
        if delta:
            payload["comparison"] = delta
        output = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    else:
        output = render_markdown(current, args.title, delta)

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
