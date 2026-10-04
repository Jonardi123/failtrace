import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize('script', ['failtrace_gate.py', 'failtrace_validate.py'])
def test_invalid_utf8_is_reported_as_json_instead_of_crashing(tmp_path, script):
    path = tmp_path / 'broken.jsonl'
    path.write_bytes(b'\xff\n')
    args = ['--format', 'json'] if script == 'failtrace_gate.py' else ['--json']
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / script),
                             str(path), *args], capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    findings = report['findings'] if script == 'failtrace_gate.py' else report['issues']
    assert len(findings) == 1
    assert 'UTF-8' in findings[0]['message']
    assert 'Traceback' not in result.stderr
