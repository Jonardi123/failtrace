#!/usr/bin/env python3
"""Pack failtrace JSONL into chat-template rows that match the harness prompt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from harness import failed_call, gold_recovery, load_jsonl, prompt_for


SYSTEM = (
    "You are a coding agent. A tool just failed. Do not repeat the same call. "
    "Do not invent file contents. Do not use sudo. Do not delete lockfiles. "
    "Reply with exactly:\n"
    "DIAGNOSIS: <one sentence>\n"
    "TOOL: <tool name or none>\n"
    "ARGS: <json object>"
)


def diagnosis_of(row: dict[str, Any]) -> str:
    for step in row.get("trace") or []:
        if step.get("type") == "diagnosis" and step.get("content"):
            return str(step["content"]).strip()
    return "The tool failed. Change tool or arguments instead of repeating the call."


def assistant_target(row: dict[str, Any]) -> str:
    tool, args = gold_recovery(row)
    return (
        f"DIAGNOSIS: {diagnosis_of(row)}\n"
        f"TOOL: {tool}\n"
        f"ARGS: {json.dumps(args, ensure_ascii=False)}"
    )


def pack_row(row: dict[str, Any]) -> dict[str, Any]:
    fail_tool, fail_args, err = failed_call(row)
    rec_tool, rec_args = gold_recovery(row)
    return {
        "id": row.get("id"),
        "category": row.get("category"),
        "schema": "sftpack.v1",
        "source_schema": row.get("schema"),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt_for(row)},
            {"role": "assistant", "content": assistant_target(row)},
        ],
        "meta": {
            "failed_tool": fail_tool,
            "failed_args": fail_args,
            "error": err,
            "recovered_tool": rec_tool,
            "recovered_args": rec_args,
        },
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert failtrace JSONL to SFT chat JSONL")
    p.add_argument("src", nargs="?", help="Input failtrace JSONL")
    p.add_argument("-o", "--out", help="Output chat JSONL (stdout if omitted)")
    p.add_argument("--preset", help="Generate from a preset instead of a file")
    p.add_argument("--mix", type=int, help="Generate a balanced mix instead of a file")
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--seed", type=int)
    return p.parse_args()


def source_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.src:
        return load_jsonl(Path(args.src))
    from presets import PRESETS

    if args.mix:
        try:
            from failtrace import mix_examples
        except ImportError:
            mix_examples = None
        if mix_examples is None:
            import random

            names = sorted(PRESETS)
            bag = [names[i % len(names)] for i in range(args.mix)]
            random.Random(args.seed).shuffle(bag)
            counters = {name: 0 for name in names}
            rows = []
            for name in bag:
                rows.append(PRESETS[name](counters[name]))
                counters[name] += 1
            return rows
        return mix_examples(args.mix, seed=args.seed)
    if args.preset:
        if args.preset not in PRESETS:
            raise SystemExit(f"unknown preset: {args.preset}")
        return [PRESETS[args.preset](i) for i in range(args.count)]
    raise SystemExit("need a JSONL path, --preset, or --mix")


def main() -> int:
    args = parse_args()
    packed = [pack_row(row) for row in source_rows(args)]
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in packed) + "\n"
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {len(packed)} sft row(s) -> {path}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
