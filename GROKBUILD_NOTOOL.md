# Land notool

Paste this into Grok Build in the failtrace repo:

```
Wire notool into the generator without breaking failtrace.v1.

1. In presets.py: `from notool_preset import notool` and add `"notool": notool` to PRESETS.
2. In test_failtrace.py MixTests.test_mix_writes_jsonl_file, mix `len(PRESETS)` rows, not 8.
3. In harness.py score(), if category is notool: fail any read_file/write_file/run_command/search_code; allow reply or none.
4. Keep two tool_calls in the trace. Recovery tool is `reply` with {"text": ...}.
5. Run pytest -q. Do not change the schema version.
```
