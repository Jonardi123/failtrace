"""Boundary checks for the audit-only importer; fixtures here are synthetic."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    'audit_collect', Path(__file__).resolve().parents[1] / 'eval/real_traces/collect.py'
)
collector = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(collector)
SOURCE = {'id': 'audit', 'instance_id': 'case', 'model': 'recorded-model',
          'url': 'https://example.invalid/never-requested', 'sha256': '0' * 64}


def trajectory(command, response):
    return {'instance_id': 'case', 'info': {'exit_status': 'Submitted'}, 'messages': [
        {'role': 'assistant', 'content': '```bash\n' + command + '\n```'},
        {'role': 'user', 'content': response},
    ]}


def test_preserves_nonzero_empty_output_and_zero_with_error_text():
    # R02 grep no-match is nonzero; R04's pipeline printed ENOENT but exited 0.
    no_match = trajectory('grep x file.py', '<returncode>1</returncode>\n<output>\n</output>')
    row = collector.convert(no_match, SOURCE)
    assert row['events'][1]['ok'] is False
    assert row['events'][1]['error'] == {'code': 'EXIT_1', 'message': ''}
    masked = trajectory('nl missing.py | head',
                        '<returncode>0</returncode>\n<output>\nnl: missing.py: No such file or directory\n</output>')
    row = collector.convert(masked, SOURCE)
    assert row['events'][1]['ok'] is True
    assert 'No such file' in row['events'][1]['result']['output']
    assert 'error' not in row['events'][1]


def test_accepts_claude_text_blocks_without_changing_recorded_command():
    data = trajectory('printf hello', '<returncode>0</returncode>\n<output>\nhello</output>')
    data['messages'][1]['content'] = [{'type': 'text', 'text': data['messages'][1]['content']}]
    row = collector.convert(data, SOURCE)
    assert row['events'][0]['arguments']['command'] == 'printf hello'
    assert row['events'][1]['result'] == {'returncode': 0, 'output': 'hello'}
    assert row['events'][1]['source_message'] == 1


def test_submission_with_missing_return_code_stays_unknown():
    data = trajectory('echo MICRO_SWE_AGENT_FINAL_OUTPUT && git diff', 'diff --git ...')
    row = collector.convert(data, SOURCE)
    assert len(row['events']) == 1
    assert row['events'][0]['type'] == 'tool_call'
    assert row['unscored'][0]['source_message'] == 1


def test_truncated_output_is_marked_and_preserved():
    envelope = ('<warning>\noutput too long\n</warning><output_head>\nfirst\n</output_head>'
                '<output_tail>\nlast\n</output_tail>')
    row = collector.convert(trajectory('cat big.py', '<returncode>0</returncode>\n' + envelope), SOURCE)
    assert row['events'][1]['result']['output_truncated'] is True
    assert row['events'][1]['result']['output'] == envelope


@pytest.mark.parametrize('response', ['looks successful', '<returncode>unknown</returncode>'])
def test_unknown_status_is_rejected_not_guessed(response):
    with pytest.raises(ValueError, match='unrecognized tool result'):
        collector.convert(trajectory('some-command', response), SOURCE)


def test_changed_source_bytes_fail_checksum_before_producing_trace(tmp_path):
    (tmp_path / 'audit.traj.json').write_text(json.dumps(trajectory('true', 'unknown')), encoding='utf-8')
    with pytest.raises(ValueError, match='checksum mismatch'):
        collector.collect({'sources': [SOURCE]}, tmp_path, offline=True)
    assert not (tmp_path / 'agenttrace.jsonl').exists()
