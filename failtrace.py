#!/usr/bin/env python3
"""Emit recovery training examples as JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from presets import PRESETS
from schema import example


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate agent failure-recovery traces.")
    p.add_argument("--preset", choices=sorted(PRESETS), help="Built-in failure class")
    p.add_argument("--list", action="store_true", help="List presets")
    p.add_argument("--count", type=int, default=1, help="How many examples to emit")
    p.add_argument("-o", "--out", help="Write JSONL here instead of stdout")
    p.add_argument("--task", help="Custom task text")
    p.add_argument("--tool", help="Failed tool name")
    p.add_argument("--args", default="{}", help="Failed tool arguments as JSON")
    p.add_argument("--error", help="Error message from the tool")
    p.add_argument("--code", default="ERROR", help="Error code")
    return p.parse_args()


def from_custom(args: argparse.Namespace) -> dict:
    try:
        tool_args = json.loads(args.args)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid --args JSON: {exc}") from exc
    if not args.task or not args.tool or not args.error:
        raise SystemExit("custom mode needs --task --tool --error")
    return example(
        id="custom_0000",
        category="custom",
        task=args.task,
        plan=[f"Call {args.tool} to make progress on the task."],
        failed_tool={"name": args.tool, "arguments": tool_args},
        failure={"code": args.code, "message": args.error},
        diagnosis="The tool failed. Do not repeat the same call. Inspect the error, then pick a smaller next step.",
        recovery_plan=[
            "Name the failure class in one sentence.",
            "Choose a different tool or different arguments.",
        ],
        recovered_tool={"name": "list_dir", "arguments": {"path": "."}},
        success={"listing": "(inspect real files before retrying)"},
        final="Stopped repeating the failed call. Next action depends on what list_dir shows.",
        notes="Custom traces still force a different second tool call.",
    )


def main() -> int:
    args = parse_args()
    if args.list:
        for name in sorted(PRESETS):
            print(name)
        return 0

    rows: list[dict] = []
    if args.preset:
        factory = PRESETS[args.preset]
        rows = [factory(i) for i in range(args.count)]
    elif args.task:
        rows = [from_custom(args)]
    else:
        print("need --preset or --task/--tool/--error", file=sys.stderr)
        return 2

    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    if args.out:
        path = Path(args.out)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {len(rows)} example(s) -> {path}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
