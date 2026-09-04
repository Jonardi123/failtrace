from __future__ import annotations

import json
from pathlib import Path

from failtrace_report import compare, render_markdown, summarize
from failtrace_validate import validate_row, validate_sources
from presets import PRESETS


def test_validator_accepts_generated_rows():
    for name, factory in PRESETS.items():
        row = factory(0)
        assert validate_row(row) == [], name


def test_validator_rejects_exact_retry():
    row = PRESETS["missing_file"](0)
    failed = row["trace"][1]
    row["trace"][5] = {
        "role": "assistant",
        "type": "tool_call",
        "tool": failed["tool"],
        "arguments": dict(failed["arguments"]),
    }
    row["trace"][6] = {
        "role": "tool",
        "tool": failed["tool"],
        "ok": True,
        "result": {},
    }
    assert "recovery must not repeat the exact failed tool call" in validate_row(row)


def test_validate_sources_detects_duplicate_ids(tmp_path: Path):
    row = PRESETS["timeout"](0)
    path = tmp_path / "data.jsonl"
    path.write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n",
        encoding="utf-8",
    )
    checked, issues = validate_sources([str(path)])
    assert checked == 2
    assert any("duplicate id" in issue.message for issue in issues)


def test_report_summary_and_baseline_delta():
    current = summarize(
        [
            {"category": "a", "ok": True, "reasons": ["ok"]},
            {"category": "a", "ok": False, "reasons": ["bad args"]},
            {"category": "b", "ok": True, "reasons": ["ok"]},
        ]
    )
    baseline = summarize(
        [
            {"category": "a", "ok": False, "reasons": ["bad args"]},
            {"category": "a", "ok": False, "reasons": ["bad args"]},
            {"category": "b", "ok": True, "reasons": ["ok"]},
        ]
    )
    delta = compare(current, baseline)
    assert current["passed"] == 2
    assert round(delta["pass_rate_delta"], 6) == round(1 / 3, 6)
    report = render_markdown(current, "Report", delta)
    assert "# Report" in report
    assert "bad args" in report
