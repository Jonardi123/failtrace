# failtrace

**Failure-recovery traces, evals, and CI gates for tool-using coding agents.**

`failtrace` is a dependency-free toolkit for a specific coding-agent problem: what happens **after a tool fails**. It can generate deterministic recovery-training episodes, evaluate a model on frozen failures, validate datasets, compare regression reports, and now gate recorded agent runs directly in CI.

The project keeps `failtrace.v1` intentionally small and adds a separate `agenttrace.v1` interchange format for real execution logs.

## Why this exists

Coding agents often fail in boring but expensive ways: they retry a missing path, overwrite a changed file, run from the wrong directory, reach for `sudo`, delete a lockfile to make an install pass, or repeat a command that already timed out.

Those failures are easy to describe after the fact and surprisingly easy to reintroduce when prompts, tools, models, or agent controllers change. Failtrace turns them into reproducible training data **and** deterministic CI checks.

A generated recovery episode follows one locked shape:

```text
task
  -> plan
  -> tool call
  -> failure
  -> diagnosis
  -> recovery plan
  -> different recovery call
  -> success
  -> final
```

A recorded production/dev run can instead be fed to `failtrace-gate`, which inspects only the tool call/result stream and fails on concrete recovery regressions.

## Quick start

```bash
git clone https://github.com/Jonardi123/failtrace.git
cd failtrace
python -m pip install -e .
```

Generate a balanced dataset:

```bash
failtrace --mix 200 --seed 7 -o data/recovery.jsonl
failtrace-validate data/recovery.jsonl
```

Gate recorded agent runs:

```bash
failtrace-gate artifacts/agent-runs/*.jsonl
```

Run the frozen eval against a local or OpenAI-compatible endpoint:

```bash
failtrace-harness \
  --mode model \
  --url http://127.0.0.1:1234/v1/chat/completions \
  --model local \
  --json > results.txt
```

Turn the result into a report:

```bash
failtrace-report results.txt -o report.md
```

Compare a new run against a previous baseline:

```bash
failtrace-report new-results.txt --baseline baseline-results.txt -o regression.md
```

## Agent recovery gate

`failtrace-gate` is framework-neutral. Record one JSON object per run using the small `agenttrace.v1` format:

```json
{
  "schema": "agenttrace.v1",
  "id": "run-001",
  "events": [
    {"type": "tool_call", "tool": "read_file", "arguments": {"path": "src/missing.py"}},
    {"type": "tool_result", "tool": "read_file", "ok": false, "error": {"code": "ENOENT", "message": "no such file"}},
    {"type": "tool_call", "tool": "list_dir", "arguments": {"path": "src"}}
  ]
}
```

The gate currently detects:

| Rule | Severity | Recovery regression |
|---|---|---|
| `FT001` | error | exact failed tool call is repeated |
| `FT002` | error | agent escalates to `sudo` after failure |
| `FT003` | error | recovery deletes a dependency lockfile |
| `FT004` | error | stale/conflicting file is rewritten without reread |
| `FT005` | warning | missing path is reread before project discovery |
| `FT006` | error | permission-denied path is immediately touched again |
| `FT007` | error | timed-out command is repeated unchanged |
| `FT008` | warning | three consecutive failures, or three identical diagnostics from the same command despite intervening activity |

Malformed or unreadable traces are `FT000` errors. Parallel tools may use an optional `call_id` on the call and matching result, so out-of-order results remain deterministic.

Outputs are available as text, JSON, native GitHub Actions annotations, or SARIF:

```bash
failtrace-gate traces/ --fail-on warning
failtrace-gate traces/*.jsonl --format json > gate.json
failtrace-gate traces/*.jsonl --format sarif -o failtrace.sarif
failtrace-gate traces/*.jsonl --format github
```

An unmatched glob fails instead of silently checking zero runs.

### Real-run validation

An initial audit of 12 published mini-SWE-agent runs found two useful warnings
and one missed repair loop, now covered by a regression. This small, correlated
sample supports advisory use; it does not establish production accuracy or
general recovery coverage. See the [audit report](eval/real_traces/REPORT.md) for
source hashes, manual classifications, limitations, and reproduction commands.

### GitHub Action

Because this repository is also a composite action, a project that already records agent runs can gate every pull request with:

```yaml
name: agent-recovery-gate
on: [pull_request]

jobs:
  failtrace:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Jonardi123/failtrace@main
        with:
          path: artifacts/agent-runs/*.jsonl
          fail-on: error
```

The action emits annotations on the JSONL line containing the bad run. See [`docs/GATE.md`](docs/GATE.md) for the interchange format, rules, adapter guidance, and CI behavior.

## Built-in recovery classes

| Preset | Failure being trained |
|---|---|
| `missing_file` | Stop guessing paths after `ENOENT`; inspect the tree |
| `bad_cwd` | Recognize that the command ran outside the project root |
| `command_fail` | Diagnose manifest/lockfile mismatches without destructive recovery |
| `conflict` | Re-read before writing when a file changed underneath the agent |
| `bad_args` | Repair rejected tool arguments instead of replaying them |
| `permission` | Avoid privilege escalation and use project-local alternatives |
| `partial` | Inspect a partial write and finish only the missing work |
| `timeout` | Narrow the scope instead of looping the same expensive command |
| `notool` | Stop calling side-effect tools when the correct recovery is text |

List them at any time:

```bash
failtrace --list
```

## Generate custom traces

```bash
failtrace \
  --task "Add a test for login" \
  --tool read_file \
  --args '{"path":"src/auth.ts"}' \
  --error "ENOENT: no such file or directory"
```

Default output is JSONL, one complete episode per line.

## Validate datasets

`failtrace-validate` checks schema version, trace order, tool/result pairing, labels, duplicate IDs, and the core invariant that recovery must not repeat the exact failed tool call.

```bash
failtrace-validate train.jsonl
failtrace-validate train.jsonl holdout.jsonl
failtrace-validate train.jsonl --json > validation.json
cat train.jsonl | failtrace-validate -
```

The command exits non-zero on invalid data, which makes it useful in CI and dataset pipelines.

## Evaluation harness

The holdout can be frozen locally:

```bash
python eval/freeze.py
```

Then run the reference checks:

```bash
failtrace-harness --mode gold
failtrace-harness --mode same
```

`gold` must pass. `same` must fail every example. For model mode, the model sees only the task, failed tool call, arguments, and error.

```bash
failtrace-harness \
  --mode model \
  --url http://127.0.0.1:1234/v1/chat/completions \
  --model local
```

The evaluator checks recovery behavior, not prose style.

## SFT packing

Convert failtrace rows into chat-template JSONL matching the harness prompt:

```bash
failtrace-sftpack --mix 200 --seed 7 -o data/recovery_sft_200.jsonl
```

Or pack an existing dataset:

```bash
failtrace-sftpack data/recovery.jsonl -o data/recovery_sft.jsonl
```

## Schema guarantees

`failtrace.v1` is intentionally conservative. A valid row has:

- one failed tool result before one successful tool result;
- exactly two tool calls;
- a diagnosis and updated plan between failure and recovery;
- a recovery call that is not identical to the failed call;
- `labels.failure_class` matching the top-level category;
- deterministic IDs and reproducible balanced mixes when `--seed` is used.

See [`docs/SCHEMA.md`](docs/SCHEMA.md) for the generated-data shape and [`docs/GATE.md`](docs/GATE.md) for live execution traces.

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest -q
```

CI runs the test suite across supported Python versions and smoke-tests generation, validation, SFT packing, the reference harness, and the safe/unsafe recovery gate fixtures.

Contributions are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before adding a new failure class because the project deliberately prefers better coverage of real recovery behavior over schema churn.

## Project status

The project is active and the `failtrace.v1` schema is locked for compatibility. Current work is focused on better scoring, real-world failure families, agent-framework adapters, and stronger regression workflows. See [`ROADMAP.md`](ROADMAP.md).

## Security

Please use the private reporting guidance in [`SECURITY.md`](SECURITY.md) for vulnerabilities. Do not publish sensitive exploit details in a public issue.

## License

MIT. See [`LICENSE`](LICENSE).
