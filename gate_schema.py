"""Interchange schema and normalization helpers for failtrace-gate."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any


SEVERITY_ORDER = {"note": 0, "warning": 1, "error": 2}

LOCKFILES = (
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "uv.lock",
    "pipfile.lock",
    "cargo.lock",
    "gemfile.lock",
    "composer.lock",
    "go.sum",
)

RUN_TOOLS = {"run_command", "exec_command", "shell", "bash", "terminal"}
READ_TOOLS = {"read_file", "read", "fetch_file", "open_file"}
WRITE_TOOLS = {"write_file", "update_file", "create_file", "apply_patch", "patch_file"}
DISCOVERY_TOOLS = {
    "list_dir",
    "list_directory",
    "ls",
    "search_code",
    "search",
    "find_file",
    "find_files",
    "glob",
}


@dataclass(frozen=True)
class Event:
    kind: str
    tool: str
    arguments: dict[str, Any]
    ok: bool | None = None
    error: dict[str, Any] | None = None
    call_id: str = ""


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    source: str
    line: int
    run_id: str
    event_index: int
    message: str
    tool: str = ""


@dataclass(frozen=True)
class CallContext:
    tool: str
    arguments: dict[str, Any]
    event_index: int
    call_id: str = ""


def tool_name(tool: Any) -> str:
    return str(tool or "").strip().lower()


def path_of(arguments: dict[str, Any]) -> str:
    value = arguments.get("path")
    return str(value) if isinstance(value, (str, os.PathLike)) else ""


def command_of(arguments: dict[str, Any]) -> str:
    value = arguments.get("command")
    return str(value) if value is not None else ""


def error_text(error: dict[str, Any] | None) -> str:
    if not error:
        return ""
    code = str(error.get("code") or "")
    message = str(error.get("message") or error.get("error") or "")
    return f"{code} {message}".lower()


def is_conflict(error: dict[str, Any] | None) -> bool:
    text = error_text(error)
    return "conflict" in text or "changed since" in text or "stale write" in text


def is_missing(error: dict[str, Any] | None) -> bool:
    text = error_text(error)
    return "enoent" in text or "no such file" in text or "not found" in text


def is_permission(error: dict[str, Any] | None) -> bool:
    text = error_text(error)
    return (
        "eacces" in text
        or "eperm" in text
        or "permission denied" in text
        or "access denied" in text
    )


def is_timeout(error: dict[str, Any] | None) -> bool:
    text = error_text(error)
    return "timeout" in text or "timed out" in text or "exceeded" in text


def uses_sudo(command: str) -> bool:
    return bool(re.search(r"(?:^|[;&|\s])sudo(?:\s|$)", command, flags=re.IGNORECASE))


def deletes_lockfile(command: str) -> bool:
    lowered = command.lower()
    delete_verb = bool(
        re.search(
            r"(?:^|[;&|\s])(?:rm(?:\s+-[^\s]+)*|del|erase|unlink|remove-item)\s+",
            lowered,
        )
    )
    return delete_verb and any(name in lowered for name in LOCKFILES)


def _failtrace_events(row: dict[str, Any]) -> tuple[str, list[Event], list[str]]:
    run_id = str(row.get("id") or "<unknown>")
    trace = row.get("trace")
    if not isinstance(trace, list):
        return run_id, [], ["failtrace.v1 row must contain a trace list"]

    errors: list[str] = []
    events: list[Event] = []
    for index, step in enumerate(trace):
        if not isinstance(step, dict):
            errors.append(f"trace[{index}] must be an object")
            continue
        if step.get("type") == "tool_call":
            tool = step.get("tool")
            args = step.get("arguments")
            if not isinstance(tool, str) or not tool.strip():
                errors.append(f"trace[{index}] tool_call.tool must be a non-empty string")
                continue
            if not isinstance(args, dict):
                errors.append(f"trace[{index}] tool_call.arguments must be an object")
                continue
            events.append(Event("tool_call", tool, args))
        elif step.get("role") == "tool":
            tool = step.get("tool")
            ok = step.get("ok")
            if not isinstance(tool, str) or not tool.strip():
                errors.append(f"trace[{index}] tool result tool must be a non-empty string")
                continue
            if not isinstance(ok, bool):
                errors.append(f"trace[{index}] tool result ok must be boolean")
                continue
            error = step.get("error") if isinstance(step.get("error"), dict) else None
            events.append(Event("tool_result", tool, {}, ok=ok, error=error))
    return run_id, events, errors


def _agenttrace_events(row: dict[str, Any]) -> tuple[str, list[Event], list[str]]:
    errors: list[str] = []
    run_id = row.get("id")
    if not isinstance(run_id, str) or not run_id.strip():
        run_id = "<unknown>"
        errors.append("agenttrace.v1 id must be a non-empty string")

    raw_events = row.get("events")
    if not isinstance(raw_events, list):
        return str(run_id), [], errors + ["agenttrace.v1 events must be a list"]

    events: list[Event] = []
    for index, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            errors.append(f"events[{index}] must be an object")
            continue
        event_type = raw.get("type")
        if event_type not in {"tool_call", "tool_result"}:
            continue

        tool = raw.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            errors.append(f"events[{index}].tool must be a non-empty string")
            continue
        call_id = raw.get("call_id")
        normalized_call_id = str(call_id) if isinstance(call_id, str) else ""

        if event_type == "tool_call":
            args = raw.get("arguments", {})
            if not isinstance(args, dict):
                errors.append(f"events[{index}].arguments must be an object")
                continue
            events.append(Event("tool_call", tool, args, call_id=normalized_call_id))
            continue

        ok = raw.get("ok")
        if not isinstance(ok, bool):
            errors.append(f"events[{index}].ok must be boolean")
            continue
        error = raw.get("error") if isinstance(raw.get("error"), dict) else None
        if ok is False and error is None:
            errors.append(f"events[{index}] failed tool_result must contain an error object")
        events.append(
            Event(
                "tool_result",
                tool,
                {},
                ok=ok,
                error=error,
                call_id=normalized_call_id,
            )
        )

    return str(run_id), events, errors


def normalize_row(row: Any) -> tuple[str, list[Event], list[str]]:
    if not isinstance(row, dict):
        return "<unknown>", [], ["row must be a JSON object"]
    schema = row.get("schema")
    if schema == "failtrace.v1":
        return _failtrace_events(row)
    if schema == "agenttrace.v1":
        return _agenttrace_events(row)
    return str(row.get("id") or "<unknown>"), [], [
        "schema must be 'failtrace.v1' or 'agenttrace.v1'"
    ]
