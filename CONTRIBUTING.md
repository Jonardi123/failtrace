# Contributing to failtrace

Thanks for helping improve recovery behavior for tool-using agents.

## Before opening a PR

1. Keep `failtrace.v1` backward compatible.
2. Prefer a new preset or scorer rule over adding new top-level schema fields.
3. Make failures concrete: include the failed tool, arguments, error, diagnosis, and a recovery that changes the next action.
4. Keep generated rows deterministic for the same preset index.
5. Add or update tests for every behavior change.

## Local checks

```bash
python -m pip install -e ".[test]"
python -m pytest -q
failtrace --mix 200 --seed 1 -o /tmp/failtrace.jsonl
failtrace-validate /tmp/failtrace.jsonl
failtrace-harness --mode gold
failtrace-harness --mode same
```

## Adding a preset

A good preset represents a failure family that appears in real coding-agent work and teaches a reusable recovery decision.

Please include:

- a short explanation of the failure class;
- at least 10 meaningful variations across paths, commands, errors, or tasks;
- no duplicate IDs;
- a recovery step that does not replay the failed call;
- tests proving the generated rows satisfy the locked schema.

Avoid adding a preset only to increase row count. Coverage matters more than volume.

## Pull requests

Keep PRs focused. Describe the failure or maintenance problem, the behavioral change, how it was tested, and whether the schema or holdout behavior changes.
