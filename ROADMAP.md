# Roadmap

`failtrace.v1` is deliberately stable. Roadmap work should improve coverage, evaluation, packaging, and maintenance without casually changing the row schema.

## v0.2

- [x] installable command-line package
- [x] dependency-free dataset validator
- [x] Markdown/JSON regression reports
- [x] CI across supported Python versions
- [x] contribution and security guidance

## v0.3

- [ ] pluggable scorer rules
- [ ] per-category score thresholds for CI
- [ ] JSON Schema export for external pipelines
- [ ] larger frozen holdout with explicit versioning
- [ ] baseline-diff exit codes for regression gates

## Later

- [ ] adapters for common agent trace formats
- [ ] richer real-world failure families collected from public bug reports
- [ ] reproducible release artifacts
- [ ] documented compatibility policy for future schema versions

Feature requests should explain the recovery behavior they unlock, not only the desired API shape.
