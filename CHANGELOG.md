# Changelog

All notable changes to failtrace are documented here.

## 0.3.0 - 2026-09-05

### Added
- `failtrace-gate`, a framework-neutral CI linter for recorded coding-agent tool traces
- `agenttrace.v1`, a tiny interchange format for tool calls/results with optional `call_id` pairing for parallel calls
- deterministic recovery rules for exact retries, privilege escalation, lockfile deletion, stale conflict writes, missing-path rereads, permission retries, repeated timeouts, and failure loops
- text, JSON, GitHub annotation, and SARIF outputs
- root-level composite GitHub Action for gating agent traces in pull requests
- safe/unsafe example traces and dedicated gate documentation

### Changed
- package description and README now cover live agent regression gating in addition to dataset generation/evaluation
- CI smoke-tests both a safe trace and a deliberately unsafe trace across Python 3.10-3.13

## 0.2.0 - 2026-09-05

### Added
- installable CLI entry points via `pyproject.toml`
- `failtrace-validate` for schema, duplicate-ID, and recovery-invariant checks
- `failtrace-report` for Markdown/JSON evaluation summaries and baseline comparison
- GitHub Actions CI across supported Python versions
- contribution, roadmap, security, and schema documentation
- MIT license

### Changed
- expanded README with end-to-end generation, validation, evaluation, reporting, and SFT workflows

## 0.1.0

- initial `failtrace.v1` generator
- balanced seeded mixes
- frozen evaluation harness
- SFT packing
- `notool` recovery class
