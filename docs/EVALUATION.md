# Evaluation workflow

The evaluation harness is intentionally small and deterministic.

## 1. Freeze a holdout

```bash
python eval/freeze.py
```

Do not regenerate the holdout between model comparisons unless you intentionally create a new benchmark version.

## 2. Verify the scorer

```bash
failtrace-harness --mode gold
failtrace-harness --mode same
```

The gold recovery should pass every row. Replaying the failed call should fail every row.

## 3. Evaluate a model

```bash
failtrace-harness \
  --mode model \
  --url http://127.0.0.1:1234/v1/chat/completions \
  --model local \
  --json > run.txt
```

The endpoint must implement the common chat-completions response shape used by many local OpenAI-compatible servers.

## 4. Produce a report

```bash
failtrace-report run.txt -o run.md
```

For regression comparison:

```bash
failtrace-report run.txt --baseline previous.txt -o regression.md
```

The report includes overall pass rate, per-category pass rates, and the most common failure reasons.

## What the score means

The scorer is behavioral. It penalizes mistakes such as:

- repeating the same failed call;
- retrying a path known to be missing;
- writing again after a conflict without re-reading;
- using `sudo` as a recovery shortcut;
- destructive lockfile recovery;
- re-running a timed-out command unchanged;
- calling side-effect tools for a text-only question.

It is not a general coding benchmark and should not be presented as one.
