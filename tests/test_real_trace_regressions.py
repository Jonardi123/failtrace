"""Minimized regression for R01's real failure loop, plus boundary controls.

Source: eval/real_traces/manifest.json R01, messages 42–51. The recorded check
failed with the same traceback while edits to unrelated lines returned zero.
These are reduced tests, not additional real runs or evaluation data.
"""
from __future__ import annotations

import pytest

from gate_rules import lint_events
from gate_schema import Event


CHECK = {'command': 'python3 repro_separability_bug.py'}
DIAGNOSTIC = {'code': 'EXIT_1', 'message': 'IndentationError: unexpected indent'}


def result_pair(arguments=CHECK, error=DIAGNOSTIC, call_id=''):
    return [Event('tool_call', 'run_command', arguments, call_id=call_id),
            Event('tool_result', 'run_command', {}, ok=error is None, error=error, call_id=call_id)]


def intervening_edit():
    return result_pair({'command': "sed -i '25,29s/^/    /' astropy/modeling/separable.py"}, None)


def warnings(events):
    return [f for f in lint_events('regression', events) if f.rule_id == 'FT008']


def test_r01_identical_diagnostic_survives_successful_edits_and_reads():
    events = (result_pair() + intervening_edit() + result_pair()
              + [Event('tool_call', 'read_file', {'path': 'astropy/modeling/separable.py'}),
                 Event('tool_result', 'read_file', {}, ok=True)] + result_pair())
    found = warnings(events)
    assert len(found) == 1
    assert found[0].event_index == 9
    assert found[0].severity == 'warning'
    assert 'identical failure diagnostic' in found[0].message


@pytest.mark.parametrize('reset', [
    result_pair(error=None),
    result_pair(error={'code': 'EXIT_1', 'message': 'NameError: model is not defined'}),
    result_pair(error={'code': 'EXIT_1', 'message': ''}),
])
def test_success_or_changed_or_missing_diagnostic_resets_streak(reset):
    events = result_pair() + intervening_edit() + result_pair() + intervening_edit()
    events += reset + intervening_edit() + result_pair()
    assert warnings(events) == []


def test_command_arguments_keep_environments_separate():
    events = []
    for cwd in ['one', 'two', 'three']:
        events += result_pair({**CHECK, 'cwd': cwd}) + intervening_edit()
    assert warnings(events) == []


def test_two_failed_checks_after_edits_are_not_a_loop_warning():
    assert warnings(result_pair() + intervening_edit() + result_pair()) == []


def test_empty_grep_output_does_not_become_a_repeated_diagnostic():
    events = []
    for _ in range(3):
        events += result_pair({'command': "grep -n 'class TimeSeries' astropy/timeseries/core.py"},
                              {'code': 'EXIT_1', 'message': ''}) + intervening_edit()
    assert warnings(events) == []


def test_one_warning_per_unchanged_streak_without_duplicate_consecutive_alert():
    # Preserve the existing consecutive-failure warning, without adding a second
    # FT008 at the same result or flooding a long streak.
    events = result_pair() * 4
    assert len(warnings(events)) == 1
    events = (result_pair() + intervening_edit()) * 4
    assert len(warnings(events)) == 1


def test_old_parallel_success_cannot_clear_newer_observed_failures():
    old = result_pair(error=None, call_id='old')
    events = [old[0]] + result_pair(call_id='first') + intervening_edit()
    events += result_pair(call_id='second') + [old[1]]
    events += intervening_edit() + result_pair(call_id='third')
    assert len(warnings(events)) == 1


def test_parallel_results_are_not_counted_as_recovery_attempts():
    pairs = [result_pair(call_id=str(i)) for i in range(3)]
    events = [p[0] for p in pairs]
    for p in pairs:
        # Interrupt the existing global consecutive-failure warning as well.
        events += [p[1]] + intervening_edit()
    assert warnings(events) == []
