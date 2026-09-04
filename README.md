# failtrace

**Failure-recovery traces, evals, and data QA for tool-using coding agents.**

`failtrace` generates small, deterministic episodes where an agent makes a tool call, encounters a concrete failure, diagnoses it, changes course, and succeeds. The project is designed for SFT data, regression tests, and local/OpenAI-compatible agent evaluation.

It is dependency-free at runtime and keeps the `failtrace.v1` schema intentionally small.

## Why this exists

Coding agents often fail in boring but expensive ways: they retry a missing path, overwrite a changed file, run from the wrong directory, reach for `sudo`, or repeat a command that already timed out. `failtrace` turns those recovery patterns into reproducible data and tests.

Each episode follows one locked shape:

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

See [`docs/SCHEMA.md`](docs/SCHEMA.md) for the full shape.

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest -q
```

CI runs the test suite across supported Python versions and smoke-tests generation, validation, SFT packing, and both reference harness modes.

Contributions are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before adding a new failure class because the project deliberately prefers better coverage of real recovery behavior over schema churn.

## Project status

The project is active and the `failtrace.v1` schema is locked for compatibility. Current work is focused on better scoring, more real-world failure families, portable reports, and stronger regression workflows. See [`ROADMAP.md`](ROADMAP.md).

## Security

Please use the private reporting guidance in [`SECURITY.md`](SECURITY.md) for vulnerabilities. Do not publish sensitive exploit details in a public issue.

## License

MIT. See [`LICENSE`](LICENSE).
