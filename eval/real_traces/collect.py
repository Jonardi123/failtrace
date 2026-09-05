"""Reproduce the pinned mini-SWE-agent trace audit; never execute source commands."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def message_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(
        isinstance(block, dict) and block.get('type') == 'text'
        and isinstance(block.get('text'), str) for block in content
    ):
        return ''.join(block['text'] for block in content)
    raise ValueError('unsupported message content; do not infer a tool outcome')


def convert(trajectory, source):
    """Use only the bash block and recorded return code, without interpreting prose."""
    events, unscored = [], []
    messages = trajectory['messages']
    if trajectory['instance_id'] != source['instance_id']:
        raise ValueError('instance_id differs from manifest')
    for index, message in enumerate(messages):
        if message['role'] != 'assistant':
            continue
        commands = re.findall(r'```bash\s*\n(.*?)\n```', message_text(message['content']), re.S)
        if len(commands) != 1:
            raise ValueError(f'messages[{index}]: expected exactly one bash command')
        command = commands[0].strip()
        call_id = f'message-{index}'
        events.append({'type': 'tool_call', 'tool': 'run_command',
                       'arguments': {'command': command}, 'call_id': call_id,
                       'source_message': index})
        if index + 1 >= len(messages) or messages[index + 1]['role'] != 'user':
            raise ValueError(f'messages[{index}]: missing recorded response')
        response = message_text(messages[index + 1]['content'])
        result = re.fullmatch(r'<returncode>(-?\d+)</returncode>\n<output>\n(.*)</output>', response, re.S)
        truncated = False
        if result is None:
            result = re.fullmatch(
                r'<returncode>(-?\d+)</returncode>\n(<warning>\n.*?</warning>'
                r'<output_head>.*?</output_head>.*?<output_tail>.*?</output_tail>)', response, re.S)
            truncated = result is not None
        if result is None:
            # mini-SWE-agent's submission handler returns a diff without an exit
            # code. Preserve the call; leave its result unknown, not successful.
            if (index == len(messages) - 2 and trajectory['info'].get('exit_status') == 'Submitted'
                    and 'MICRO_SWE_AGENT_FINAL_OUTPUT' in command):
                unscored.append({'source_message': index + 1, 'reason': 'submission result has no return code'})
                continue
            raise ValueError(f'messages[{index + 1}]: unrecognized tool result')
        returncode, output = int(result[1]), result[2]
        event = {'type': 'tool_result', 'tool': 'run_command', 'call_id': call_id,
                 'ok': returncode == 0, 'result': {'returncode': returncode, 'output': output},
                 'source_message': index + 1}
        if truncated:
            event['result']['output_truncated'] = True
        if returncode != 0:
            event['error'] = {'code': f'EXIT_{returncode}', 'message': output}
        events.append(event)
    return {'schema': 'agenttrace.v1', 'id': source['id'], 'events': events,
            'provenance': {k: source[k] for k in ('url', 'sha256', 'instance_id', 'model')},
            'unscored': unscored}


def collect(manifest, directory, *, offline=False):
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for source in manifest['sources']:
        path = directory / (source['id'] + '.traj.json')
        if not path.exists():
            if offline:
                raise FileNotFoundError(path)
            with urllib.request.urlopen(source['url'], timeout=60) as response:
                raw = response.read()
        else:
            raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source['sha256']:
            raise ValueError(f"source checksum mismatch: {source['id']}")
        if not path.exists():
            path.write_bytes(raw)
        rows.append(convert(json.loads(raw), source))
    output = directory / 'agenttrace.jsonl'
    output.write_bytes(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode('utf-8'))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True, help='local cache and normalized output directory')
    parser.add_argument('--offline', action='store_true', help='require already cached source files')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    print(collect(manifest, args.work_dir, offline=args.offline))


if __name__ == '__main__':
    main()
