# failtrace.v1 schema

A failtrace row is one JSON object. Datasets use JSONL, one row per line.

## Top-level fields

| Field | Type | Meaning |
|---|---|---|
| `schema` | string | Always `failtrace.v1` |
| `id` | string | Unique deterministic row identifier |
| `category` | string | Failure family |
| `split` | string | Currently `train` |
| `task` | string | User/developer task the agent is trying to complete |
| `plan` | string[] | Original plan |
| `trace` | object[] | Ordered interaction trace |
| `labels` | object | Recovery labels |
| `notes` | string | Optional human note |

## Locked trace order

A valid v1 trace contains exactly eight steps:

1. assistant `plan`
2. assistant failed `tool_call`
3. failed tool result with `ok: false`
4. assistant `diagnosis`
5. assistant `plan_update`
6. assistant recovered `tool_call`
7. successful tool result with `ok: true`
8. assistant `final`

The tool name on each result must match the preceding tool call.

The recovered call must not be identical to the failed call. Reusing the same tool is allowed when the arguments or scope change meaningfully, such as correcting `cwd` or narrowing a timed-out command.

## Labels

```json
{
  "should_retry": true,
  "should_call_tool_after_fail": true,
  "failure_class": "missing_file"
}
```

`failure_class` must match `category`.

`should_retry` means "attempt recovery", not "repeat the exact call".

## Compatibility

New presets may be added without changing the schema. New optional tooling may be added around the schema. Any future incompatible row shape must use a new schema version instead of silently changing `failtrace.v1`.
