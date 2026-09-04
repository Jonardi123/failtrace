from __future__ import annotations

import json
from pathlib import Path

import failtrace_gate as gate


def run(events, run_id="run-1"):
    return {
        "schema": "agenttrace.v1",
        "id": run_id,
        "events": events,
    }


def findings_for(row):
    run_id, events, errors = gate.normalize_row(row)
    assert errors == []
    return gate.lint_events(run_id, events)


def ids(findings):
    return [item.rule_id for item in findings]


def test_safe_missing_file_recovery_has_no_findings():
    row = run(
        [
            {"type": "tool_call", "tool": "read_file", "arguments": {"path": "src/missing.py"}},
            {"type": "tool_result", "tool": "read_file", "ok": False, "error": {"code": "ENOENT", "message": "no such file"}},
            {"type": "tool_call", "tool": "list_dir", "arguments": {"path": "src"}},
            {"type": "tool_result", "tool": "list_dir", "ok": True, "result": {"items": ["app.py"]}},
            {"type": "tool_call", "tool": "read_file", "arguments": {"path": "src/app.py"}},
            {"type": "tool_result", "tool": "read_file", "ok": True, "result": {"content": "pass"}},
        ]
    )
    assert findings_for(row) == []


def test_exact_retry_and_missing_path_reread_are_detected():
    row = run(
        [
            {"type": "tool_call", "tool": "read_file", "arguments": {"path": "missing.py"}},
            {"type": "tool_result", "tool": "read_file", "ok": False, "error": {"code": "ENOENT", "message": "missing"}},
            {"type": "tool_call", "tool": "read_file", "arguments": {"path": "missing.py"}},
        ]
    )
    got = ids(findings_for(row))
    assert "FT001" in got
    assert "FT005" in got


def test_sudo_and_lockfile_delete_are_detected_after_failure():
    row = run(
        [
            {"type": "tool_call", "tool": "run_command", "arguments": {"command": "npm ci"}},
            {"type": "tool_result", "tool": "run_command", "ok": False, "error": {"code": "LOCK_MISMATCH", "message": "package lock mismatch"}},
            {"type": "tool_call", "tool": "run_command", "arguments": {"command": "sudo rm package-lock.json"}},
        ]
    )
    got = ids(findings_for(row))
    assert "FT002" in got
    assert "FT003" in got


def test_conflict_requires_reread_before_write():
    bad = run(
        [
            {"type": "tool_call", "tool": "write_file", "arguments": {"path": "src/app.py", "content": "v1"}},
            {"type": "tool_result", "tool": "write_file", "ok": False, "error": {"code": "CONFLICT", "message": "changed since last read"}},
            {"type": "tool_call", "tool": "write_file", "arguments": {"path": "src/app.py", "content": "v2"}},
        ]
    )
    assert "FT004" in ids(findings_for(bad))

    good = run(
        [
            {"type": "tool_call", "tool": "write_file", "arguments": {"path": "src/app.py", "content": "v1"}},
            {"type": "tool_result", "tool": "write_file", "ok": False, "error": {"code": "CONFLICT", "message": "changed since last read"}},
            {"type": "tool_call", "tool": "read_file", "arguments": {"path": "src/app.py"}},
            {"type": "tool_result", "tool": "read_file", "ok": True, "result": {"content": "fresh"}},
            {"type": "tool_call", "tool": "write_file", "arguments": {"path": "src/app.py", "content": "fresh+patch"}},
        ]
    )
    assert "FT004" not in ids(findings_for(good))


def test_timeout_repeat_is_detected_even_if_other_call_happens_first():
    row = run(
        [
            {"type": "tool_call", "tool": "run_command", "arguments": {"command": "pytest"}},
            {"type": "tool_result", "tool": "run_command", "ok": False, "error": {"code": "TIMEOUT", "message": "timed out"}},
            {"type": "tool_call", "tool": "list_dir", "arguments": {"path": "tests"}},
            {"type": "tool_result", "tool": "list_dir", "ok": True, "result": {}},
            {"type": "tool_call", "tool": "run_command", "arguments": {"command": "pytest"}},
        ]
    )
    assert "FT007" in ids(findings_for(row))


def test_three_failures_trigger_loop_warning():
    row = run(
        [
            {"type": "tool_call", "tool": "search_code", "arguments": {"query": "a"}},
            {"type": "tool_result", "tool": "search_code", "ok": False, "error": {"code": "E1", "message": "x"}},
            {"type": "tool_call", "tool": "search_code", "arguments": {"query": "b"}},
            {"type": "tool_result", "tool": "search_code", "ok": False, "error": {"code": "E2", "message": "x"}},
            {"type": "tool_call", "tool": "search_code", "arguments": {"query": "c"}},
            {"type": "tool_result", "tool": "search_code", "ok": False, "error": {"code": "E3", "message": "x"}},
        ]
    )
    assert "FT008" in ids(findings_for(row))


def test_failtrace_v1_rows_are_supported():
    row = {
        "schema": "failtrace.v1",
        "id": "fixture",
        "trace": [
            {"role": "assistant", "type": "tool_call", "tool": "read_file", "arguments": {"path": "x"}},
            {"role": "tool", "tool": "read_file", "ok": False, "error": {"code": "ENOENT", "message": "missing"}},
            {"role": "assistant", "type": "tool_call", "tool": "list_dir", "arguments": {"path": "."}},
            {"role": "tool", "tool": "list_dir", "ok": True, "result": {}},
        ],
    }
    run_id, events, errors = gate.normalize_row(row)
    assert run_id == "fixture"
    assert errors == []
    assert gate.lint_events(run_id, events) == []


def test_gate_sources_and_exit_threshold(tmp_path: Path, capsys):
    path = tmp_path / "trace.jsonl"
    path.write_text(
        json.dumps(
            run(
                [
                    {"type": "tool_call", "tool": "read_file", "arguments": {"path": "x"}},
                    {"type": "tool_result", "tool": "read_file", "ok": False, "error": {"code": "ENOENT", "message": "missing"}},
                    {"type": "tool_call", "tool": "read_file", "arguments": {"path": "x"}},
                ]
            )
        )
        + "\n",
        encoding="utf-8",
    )
    assert gate.main([str(path), "--fail-on", "error", "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["runs_checked"] == 1
    assert data["summary"]["error"] >= 1


def test_unmatched_glob_is_a_failure_not_silent_success(tmp_path: Path):
    checked, findings = gate.gate_sources([str(tmp_path / "*.jsonl")])
    assert checked == 0
    assert findings
    assert findings[0].rule_id == "FT000"


def test_sarif_contains_rules_and_location():
    finding = gate.Finding(
        rule_id="FT001",
        severity="error",
        source="traces/run.jsonl",
        line=4,
        run_id="r1",
        event_index=2,
        message="repeated failed call",
    )
    report = gate.sarif_report([finding])
    assert report["version"] == "2.1.0"
    result = report["runs"][0]["results"][0]
    assert result["ruleId"] == "FT001"
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 4


def test_github_annotations_are_emitted():
    finding = gate.Finding(
        rule_id="FT005",
        severity="warning",
        source="trace.jsonl",
        line=2,
        run_id="r1",
        event_index=3,
        message="missing path reread",
    )
    line = gate.github_lines([finding])[0]
    assert line.startswith("::warning file=trace.jsonl,line=2::FT005")


def test_parallel_calls_can_be_paired_with_call_id():
    row = run(
        [
            {"type": "tool_call", "call_id": "a", "tool": "read_file", "arguments": {"path": "a.py"}},
            {"type": "tool_call", "call_id": "b", "tool": "read_file", "arguments": {"path": "b.py"}},
            {"type": "tool_result", "call_id": "b", "tool": "read_file", "ok": True, "result": {"content": "b"}},
            {"type": "tool_result", "call_id": "a", "tool": "read_file", "ok": True, "result": {"content": "a"}},
        ]
    )
    assert findings_for(row) == []


def test_parallel_calls_without_call_id_are_reported_as_malformed():
    row = run(
        [
            {"type": "tool_call", "tool": "read_file", "arguments": {"path": "a.py"}},
            {"type": "tool_call", "tool": "read_file", "arguments": {"path": "b.py"}},
            {"type": "tool_result", "tool": "read_file", "ok": True, "result": {"content": "b"}},
        ]
    )
    assert "FT000" in ids(findings_for(row))
