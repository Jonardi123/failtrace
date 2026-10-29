"""Regression tests for argv-style command inspection in the recovery gate."""

from failtrace_gate import lint_events, normalize_row
from gate_schema import command_of


def recovery_findings(recovery_args, *, initial_args=None, error=None):
    row = {
        "schema": "agenttrace.v1",
        "id": "argv-regression",
        "events": [
            {
                "type": "tool_call",
                "tool": "run_command",
                "arguments": initial_args or {"command": "false"},
            },
            {
                "type": "tool_result",
                "tool": "run_command",
                "ok": False,
                "error": error or {"code": "FAILED", "message": "command failed"},
            },
            {"type": "tool_call", "tool": "run_command", "arguments": recovery_args},
        ],
    }
    run_id, events, errors = normalize_row(row)
    assert not errors
    return {finding.rule_id for finding in lint_events(run_id, events)}


def test_command_of_accepts_common_argv_shapes():
    assert command_of({"command": ["python", "-m", "pytest"]}) == "python -m pytest"
    assert command_of({"cmd": ["sudo", "true"]}) == "sudo true"
    assert command_of({"argv": ["rm", "-f", "package-lock.json"]}) == "rm -f package-lock.json"
    assert command_of({"command": "pytest -q"}) == "pytest -q"
    assert command_of({"cmd": ["sudo", 123]}) == ""


def test_sudo_in_cmd_array_is_flagged_after_failure():
    assert "FT002" in recovery_findings({"cmd": ["sudo", "true"]})


def test_lockfile_deletion_in_argv_array_is_flagged_after_failure():
    assert "FT003" in recovery_findings({"argv": ["rm", "-f", "package-lock.json"]})


def test_timeout_repeat_detected_across_command_and_argv_shapes():
    assert "FT007" in recovery_findings(
        {"argv": ["pytest", "-q"]},
        initial_args={"command": ["pytest", "-q"]},
        error={"code": "TIMEOUT", "message": "timed out"},
    )


def test_safe_argv_command_has_no_privilege_or_lockfile_findings():
    findings = recovery_findings({"cmd": ["python", "-m", "pytest"]})
    assert "FT002" not in findings
    assert "FT003" not in findings
