"""Checks for observational coverage reporting in the real-trace audit helper."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    'audit_check', Path(__file__).resolve().parents[1] / 'eval/real_traces/check_audit.py'
)
audit_check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(audit_check)


def test_observational_summary_reports_tool_shapes_and_rule_gaps_without_accuracy_claims():
    rows = [
        {
            'schema': 'agenttrace.v1',
            'id': 'r1',
            'events': [
                {'type': 'tool_call', 'tool': 'run_command', 'arguments': {'command': 'pytest'}},
                {'type': 'tool_result', 'tool': 'run_command', 'ok': False,
                 'error': {'code': 'EXIT_1', 'message': 'failed'}},
                {'type': 'tool_call', 'call_id': 'read-1', 'tool': 'read_file',
                 'arguments': {'path': 'src/app.py'}},
                {'type': 'tool_result', 'call_id': 'read-1', 'tool': 'read_file', 'ok': True},
            ],
        },
        {
            'schema': 'agenttrace.v1',
            'id': 'r2',
            'events': [
                {'type': 'tool_call', 'tool': 'run_command', 'arguments': {'command': 'python repro.py'}},
                {'type': 'tool_result', 'tool': 'run_command', 'ok': False,
                 'error': {'code': 'EXIT_1', 'message': 'same traceback'}},
            ],
        },
    ]
    report = {
        'findings': [
            {'rule_id': 'FT008'},
            {'rule_id': 'FT008'},
        ]
    }

    summary = audit_check.observational_summary(rows, report)

    assert summary['schema'] == 'failtrace.real-audit-summary.v1'
    assert summary['runs'] == 2
    assert summary['tool_calls'] == 3
    assert summary['tool_results'] == 3
    assert summary['failed_results'] == 2
    assert summary['tool_call_counts'] == {'read_file': 1, 'run_command': 2}
    assert summary['calls_with_call_id'] == 1
    assert summary['calls_with_path_argument'] == 1
    assert summary['calls_with_command_argument'] == 2
    assert summary['finding_rule_counts']['FT008'] == 2
    assert summary['rules_with_findings'] == ['FT008']
    assert 'FT001' in summary['rules_without_findings']
    assert 'not positive/negative accuracy estimates' in summary['note']


def test_observational_summary_keeps_all_known_rules_visible_when_no_findings_exist():
    summary = audit_check.observational_summary([], {'findings': []})

    assert summary['rules_with_findings'] == []
    assert summary['rules_without_findings'] == [
        'FT001', 'FT002', 'FT003', 'FT004', 'FT005', 'FT006', 'FT007', 'FT008'
    ]
    assert all(count == 0 for count in summary['finding_rule_counts'].values())
