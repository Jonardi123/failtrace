from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "failtrace.v1"


def example(
    *,
    id: str,
    category: str,
    task: str,
    plan: list[str],
    failed_tool: dict[str, Any],
    failure: dict[str, Any],
    diagnosis: str,
    recovery_plan: list[str],
    recovered_tool: dict[str, Any],
    success: dict[str, Any],
    final: str,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "id": id,
        "category": category,
        "split": "train",
        "task": task,
        "plan": plan,
        "trace": [
            {
                "role": "assistant",
                "type": "plan",
                "content": plan,
            },
            {
                "role": "assistant",
                "type": "tool_call",
                "tool": failed_tool["name"],
                "arguments": failed_tool["arguments"],
            },
            {
                "role": "tool",
                "tool": failed_tool["name"],
                "ok": False,
                "error": failure,
            },
            {
                "role": "assistant",
                "type": "diagnosis",
                "content": diagnosis,
            },
            {
                "role": "assistant",
                "type": "plan_update",
                "content": recovery_plan,
            },
            {
                "role": "assistant",
                "type": "tool_call",
                "tool": recovered_tool["name"],
                "arguments": recovered_tool["arguments"],
            },
            {
                "role": "tool",
                "tool": recovered_tool["name"],
                "ok": True,
                "result": success,
            },
            {
                "role": "assistant",
                "type": "final",
                "content": final,
            },
        ],
        "labels": {
            "should_retry": True,
            "should_call_tool_after_fail": True,
            "failure_class": category,
        },
        "notes": notes,
    }
