"""Verify a replay against the persisted manual review; never infer truth labels."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gate_report import gate_sources, json_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('traces', type=Path)
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
    print(f"{checked} real runs replayed; {len(findings)} findings match the persisted manual audit")


if __name__ == '__main__':
    main()
