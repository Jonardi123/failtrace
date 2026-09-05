# Agent Recovery Gate

`failtrace-gate` is a deterministic CI linter for tool-using coding-agent execution traces.

It does **not** grade prose or ask another model to judge the run. It looks for recovery behaviors that can be checked directly from the tool stream: exact retries after failure, privilege escalation, destructive lockfile deletion, stale writes after conflicts, repeated missing-path reads, permission-denied path reuse, repeated timed-out commands, and failure loops.

This makes the gate useful as a regression test around an agent, regardless of which model or framework produced the trace.

## Interchange format

One JSON object per line:

```json
{
  "schema": "agenttrace.v1",
  "id": "run-2026-09-05-001",
  "events": [
    {
      "type": "tool_call",
      "tool": "read_file",
      "arguments": {"path": "src/missing.py"}
    },
    {
      "type": "tool_result",
      "tool": "read_file",
      "ok": false,
      "error": {"code": "ENOENT", "message": "no such file"}
    },
    {
      "type": "tool_call",
      "tool": "list_dir",
      "arguments": {"path": "src"}
    }
  ]
}
```

Only `tool_call` and `tool_result` events are interpreted. Adapters may include extra event types such as model messages, plans, token counts, or timings; the gate ignores them. Existing `failtrace.v1` rows are accepted directly too.

Sequential calls need no identifier. Agents that execute tools in parallel can add the same optional `call_id` string to a `tool_call` and its matching `tool_result`; the gate will pair out-of-order results correctly.

## Rules

| Rule | Severity | Meaning |
|---|---|---|
| `FT000` | error | malformed or unreadable trace input |
| `FT001` | error | exact failed tool call repeated immediately |
| `FT002` | error | recovery command escalates with `sudo` |
| `FT003` | error | recovery command deletes a dependency lockfile |
| `FT004` | error | file is written again after conflict without a reread |
| `FT005` | warning | missing path is reread before tree/code discovery |
| `FT006` | error | permission-denied path is touched again |
| `FT007` | error | command that timed out is repeated unchanged |
| `FT008` | warning | three consecutive failures, or the same command returns an identical diagnostic three times |

The rules are intentionally narrow. A gate that fires on everything becomes background noise; Failtrace should only block behavior that is straightforward to defend from the trace itself.

## CLI

```bash
failtrace-gate traces/*.jsonl
failtrace-gate traces/ --fail-on warning
failtrace-gate traces/*.jsonl --format json > gate.json
failtrace-gate traces/*.jsonl --format sarif -o failtrace.sarif
failtrace-gate traces/*.jsonl --format github
```

An unresolved glob is an error rather than a silent success. That prevents a broken artifact path from turning CI green while checking zero runs.

## GitHub Action

A repository that records agent execution traces can gate every pull request with:

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

The action emits native GitHub workflow annotations on the JSONL line that contains the bad run. It requires Python 3.10+ on the runner.

## Adapter guidance

You do not need to redesign an agent around Failtrace. At the boundary where the agent already logs a tool request/result, emit the same pair as `agenttrace.v1` events. A minimal adapter only needs four fields:

- call: `type`, `tool`, `arguments`
- result: `type`, `tool`, `ok`, plus `error` when `ok=false`

Keep credentials, prompts, and raw file contents out of the trace unless you have a separate reason to store them. The gate does not need them.


### Recovery completion and parallel calls

`FT004` requires a successful read of the conflicted path, started after the
conflict result. `FT005` requires successful discovery started after the missing
path result. Failed or still-pending recovery calls do not clear these findings.
A late result from a read or discovery started before the failure does not count
as recovery, even when paired correctly through `call_id`.

`FT008` also tracks repeated failures of an identical shell-tool call across
successful edits, reads, and other commands. It warns on the third identical,
non-empty error object and message, once per streak. A successful execution of
that same call, or a changed/missing diagnostic, resets its streak. All arguments
(including any working directory or environment) must match. Calls started
before the preceding failure was observed do not count as recovery attempts.

This warning describes unchanged diagnostic evidence; it does not assert that
each retry was unjustified. Timing differences, changed diagnostic text, different
command spellings, and failures hidden by exit-zero pipelines remain outside
this additional check. See the [real-run audit](../eval/real_traces/REPORT.md).
