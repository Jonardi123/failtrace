# Roadmap

`failtrace.v1` is deliberately stable. Roadmap work should improve coverage, evaluation, interoperability, and maintenance without casually changing the row schema.

## v0.2

- [x] installable command-line package
- [x] dependency-free dataset validator
- [x] Markdown/JSON regression reports
- [x] CI across supported Python versions
- [x] contribution and security guidance

## v0.3

- [x] framework-neutral agent execution trace gate
- [x] GitHub Action with native workflow annotations
- [x] SARIF/JSON machine-readable gate output
- [x] optional `call_id` pairing for parallel tool calls
- [ ] pluggable scorer/gate rules
- [ ] per-category score thresholds for model eval CI
- [ ] JSON Schema export for external pipelines
- [ ] larger frozen holdout with explicit versioning
- [ ] baseline-diff exit codes for model regression gates

## Later

- [ ] adapters for common agent trace formats
- [ ] richer real-world failure families collected from public bug reports
- [ ] reproducible release artifacts
- [ ] documented compatibility policy for future schema versions
- [ ] opt-in telemetry-free adapter examples for popular agent SDKs

Feature requests should explain the recovery behavior they unlock, not only the desired API shape.
