# Security policy

## Supported versions

Security fixes are applied to the current `main` branch and the newest tagged release.

## Reporting a vulnerability

Please do not post sensitive vulnerability details in a public issue.

Use GitHub's private vulnerability reporting feature for this repository when available. If private reporting is unavailable, contact the maintainer through the contact method listed on the GitHub profile and include only enough detail to establish a safe private channel.

Useful reports include:

- affected commit or version;
- impact;
- minimal reproduction;
- whether untrusted dataset content, model output, or endpoint responses are involved;
- a suggested fix, if known.

## Scope

`failtrace` is primarily a local data-generation and evaluation tool. Reports involving unsafe command execution, path handling, untrusted JSON/JSONL parsing, or unexpected network behavior in the harness are especially useful.
