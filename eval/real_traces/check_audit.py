"""Verify a replay against the persisted manual review; never infer truth labels."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gate_report import gate_sources, json_report
from gate_rules import RULES


def observational_summary(rows, report):
    """Describe what the audited corpus actually exercised without claiming accuracy."""
    tool_calls = Counter()
    results = 0
    failures = 0
    parallel_calls = 0
    path_calls = 0
    command_calls = 0

    for row in rows:
        for event in row.get('events', []):
            if event.get('type') == 'tool_call':
                tool_calls[str(event.get('tool') or '<unknown>')] += 1
                if event.get('call_id'):
                    parallel_calls += 1
                arguments = event.get('arguments') if isinstance(event.get('arguments'), dict) else {}
                if arguments.get('path') is not None:
                    path_calls += 1
                if arguments.get('command') is not None:
                    command_calls += 1
            elif event.get('type') == 'tool_result':
                results += 1
                if event.get('ok') is False:
                    failures += 1

    finding_rules = Counter(item['rule_id'] for item in report.get('findings', []))
    known_rules = sorted(rule_id for rule_id in RULES if rule_id != 'FT000')
    return {
        'schema': 'failtrace.real-audit-summary.v1',
        'runs': len(rows),
        'tool_calls': sum(tool_calls.values()),
        'tool_results': results,
        'failed_results': failures,
        'tool_call_counts': dict(sorted(tool_calls.items())),
        'calls_with_call_id': parallel_calls,
        'calls_with_path_argument': path_calls,
        'calls_with_command_argument': command_calls,
        'finding_rule_counts': {rule_id: finding_rules.get(rule_id, 0) for rule_id in known_rules},
        'rules_with_findings': [rule_id for rule_id in known_rules if finding_rules.get(rule_id, 0)],
        'rules_without_findings': [rule_id for rule_id in known_rules if not finding_rules.get(rule_id, 0)],
        'note': (
            'Observed findings and tool-shape coverage are not positive/negative accuracy estimates. '
            'A rule with no finding may simply lack a triggering example in this corpus.'
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('traces', type=Path)
    parser.add_argument(
        '--coverage-out',
        type=Path,
        help='optional path for an observational corpus/rule coverage JSON summary',
    )
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    rows = [json.loads(line) for line in args.traces.read_text(encoding='utf-8').splitlines() if line.strip()]
    manifest = json.loads((here / 'manifest.json').read_text(encoding='utf-8'))
    if hashlib.sha256(args.traces.read_bytes()).hexdigest() != manifest['normalized_sha256']:
        raise ValueError('normalized trace checksum differs from audited data')
    reviews = json.loads((here / 'reviews.json').read_text(encoding='utf-8'))
    expected = json.loads((here / 'after.json').read_text(encoding='utf-8'))
    if [r['id'] for r in rows] != [s['id'] for s in manifest['sources']]:
        raise ValueError('run IDs or order differ from the audited sample')
    for row, review in zip(rows, reviews['per_run_review']):
        failures = [e['source_message'] for e in row['events'] if e['type'] == 'tool_result' and not e['ok']]
        if failures != review['all_nonzero_source_messages_reviewed']:
            raise ValueError(f"failure inventory differs for {row['id']}")
    checked, findings = gate_sources([str(args.traces)], max_findings=10000)
    report = json_report(checked, findings)
    for finding in report['findings']:
        finding['source'] = 'agenttrace.jsonl'
    if report != expected:
        raise ValueError('gate replay differs from after.json; inspect findings before changing expectations')

    coverage = observational_summary(rows, report)
    if args.coverage_out:
        args.coverage_out.parent.mkdir(parents=True, exist_ok=True)
        args.coverage_out.write_text(json.dumps(coverage, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    observed = ', '.join(coverage['rules_with_findings']) or 'none'
    missing = ', '.join(coverage['rules_without_findings']) or 'none'
    tools = ', '.join(f"{name}={count}" for name, count in coverage['tool_call_counts'].items()) or 'none'
    print(f"{checked} real runs replayed; {len(findings)} findings match the persisted manual audit")
    print(f"observed tools: {tools}; rule findings: {observed}; no findings for: {missing}")


if __name__ == '__main__':
    main()
