"""Deterministic recovery rules for failtrace-gate."""

from __future__ import annotations

from gate_schema import (
    DISCOVERY_TOOLS,
    READ_TOOLS,
    RUN_TOOLS,
    WRITE_TOOLS,
    CallContext,
    Event,
    Finding,
    command_of,
    deletes_lockfile,
    is_conflict,
    is_missing,
    is_permission,
    is_timeout,
    path_of,
    tool_name,
    uses_sudo,
)


RULES: dict[str, dict[str, str]] = {
    "FT000": {
        "severity": "error",
        "title": "Malformed agent trace",
        "description": "The input cannot be interpreted as failtrace.v1 or agenttrace.v1.",
    },
    "FT001": {
        "severity": "error",
        "title": "Exact retry after failure",
        "description": "The agent repeated the same tool with the same arguments immediately after it failed.",
    },
    "FT002": {
        "severity": "error",
        "title": "Privilege escalation during recovery",
        "description": "The agent used sudo after a tool failure instead of recovering within the existing scope.",
    },
    "FT003": {
        "severity": "error",
        "title": "Destructive lockfile recovery",
        "description": "The agent tried to delete a dependency lockfile as a recovery step.",
    },
    "FT004": {
        "severity": "error",
        "title": "Write after conflict without reread",
        "description": "The agent attempted another write to a path that reported a conflict before rereading it.",
    },
    "FT005": {
        "severity": "warning",
        "title": "Missing path reread",
        "description": "The agent reread a path that already returned ENOENT without first inspecting the tree.",
    },
    "FT006": {
        "severity": "error",
        "title": "Permission-denied path retouched",
        "description": "The agent immediately returned to a path that had already denied access.",
    },
    "FT007": {
        "severity": "error",
        "title": "Timed-out command repeated",
        "description": "The agent reran a command that had already timed out instead of narrowing or changing it.",
    },
    "FT008": {
        "severity": "warning",
        "title": "Repeated failure loop",
        "description": "The trace contains at least three failed tool results in a row without a success.",
    },
}


def lint_events(
    run_id: str,
    events: list[Event],
    *,
    source: str = "<memory>",
    line: int = 1,
) -> list[Finding]:
    findings: list[Finding] = []
    sequential_call: CallContext | None = None
    calls_by_id: dict[str, CallContext] = {}
    last_failure: CallContext | None = None
    had_failure = False
    consecutive_failures = 0

    pending_conflicts: set[str] = set()
    pending_missing: set[str] = set()
    pending_permission: set[str] = set()
    pending_timeouts: set[str] = set()

    def add(rule_id: str, event_index: int, message: str, tool: str = "") -> None:
        meta = RULES[rule_id]
        findings.append(
            Finding(
                rule_id=rule_id,
                severity=meta["severity"],
                source=source,
                line=line,
                run_id=run_id,
                event_index=event_index,
                message=message,
                tool=tool,
            )
        )

    def remember_call(event: Event, event_index: int) -> None:
        nonlocal sequential_call
        context = CallContext(event.tool, event.arguments, event_index, event.call_id)
        if event.call_id:
            if event.call_id in calls_by_id:
                add(
                    "FT000",
                    event_index,
                    f"duplicate call_id {event.call_id!r} before its previous result",
                    event.tool,
                )
            calls_by_id[event.call_id] = context
            return
        if sequential_call is not None:
            add(
                "FT000",
                event_index,
                "tool_call arrived before the previous sequential call produced a result; "
                "use call_id for parallel tool calls",
                event.tool,
            )
        sequential_call = context

    def match_result(event: Event, event_index: int) -> CallContext | None:
        nonlocal sequential_call
        if event.call_id:
            context = calls_by_id.pop(event.call_id, None)
            if context is None:
                add(
                    "FT000",
                    event_index,
                    f"tool_result references unknown call_id {event.call_id!r}",
                    event.tool,
                )
                return None
        else:
            context = sequential_call
            sequential_call = None
            if context is None:
                add(
                    "FT000",
                    event_index,
                    "tool_result has no matching sequential tool_call",
                    event.tool,
                )
                return None
        if tool_name(context.tool) != tool_name(event.tool):
            add(
                "FT000",
                event_index,
                f"tool_result for {event.tool!r} does not match call tool {context.tool!r}",
                event.tool,
            )
        return context

    for event_index, event in enumerate(events):
        tool = tool_name(event.tool)

        if event.kind == "tool_call":
            args = event.arguments
            path = path_of(args)
            command = command_of(args)

            if last_failure is not None:
                if tool == tool_name(last_failure.tool) and args == last_failure.arguments:
                    add(
                        "FT001",
                        event_index,
                        f"repeated failed call {event.tool} with identical arguments",
                        event.tool,
                    )
                last_failure = None

            if had_failure and command:
                if uses_sudo(command):
                    add("FT002", event_index, f"recovery command uses sudo: {command}", event.tool)
                if deletes_lockfile(command):
                    add(
                        "FT003",
                        event_index,
                        f"recovery command deletes a lockfile: {command}",
                        event.tool,
                    )

            if tool in DISCOVERY_TOOLS:
                pending_missing.clear()

            if tool in READ_TOOLS and path:
                if path in pending_missing:
                    add(
                        "FT005",
                        event_index,
                        f"reread missing path {path!r} before inspecting the project tree",
                        event.tool,
                    )
                if path in pending_permission:
                    add(
                        "FT006",
                        event_index,
                        f"immediately returned to permission-denied path {path!r}",
                        event.tool,
                    )

            if tool in WRITE_TOOLS and path:
                if path in pending_conflicts:
                    add(
                        "FT004",
                        event_index,
                        f"wrote {path!r} again after a conflict without rereading it",
                        event.tool,
                    )
                if path in pending_permission:
                    add(
                        "FT006",
                        event_index,
                        f"immediately returned to permission-denied path {path!r}",
                        event.tool,
                    )

            if pending_permission:
                pending_permission.clear()

            if command and command in pending_timeouts:
                add(
                    "FT007",
                    event_index,
                    f"repeated command that already timed out: {command}",
                    event.tool,
                )

            remember_call(event, event_index)
            continue

        if event.kind != "tool_result":
            continue

        context = match_result(event, event_index)
        if event.ok is True:
            consecutive_failures = 0
            if context is not None:
                context_tool = tool_name(context.tool)
                path = path_of(context.arguments)
                command = command_of(context.arguments)
                if context_tool in READ_TOOLS and path:
                    pending_conflicts.discard(path)
                if context_tool in RUN_TOOLS and command and command not in pending_timeouts:
                    pending_timeouts.clear()
                if context_tool in WRITE_TOOLS:
                    pending_timeouts.clear()
            continue

        if event.ok is not False:
            continue

        had_failure = True
        consecutive_failures += 1
        if consecutive_failures == 3:
            add(
                "FT008",
                event_index,
                "three failed tool results occurred consecutively without a successful recovery",
                event.tool,
            )

        if context is None:
            continue

        last_failure = context
        path = path_of(context.arguments)
        command = command_of(context.arguments)
        if path and is_conflict(event.error):
            pending_conflicts.add(path)
        if path and is_missing(event.error):
            pending_missing.add(path)
        if path and is_permission(event.error):
            pending_permission.add(path)
        if command and is_timeout(event.error):
            pending_timeouts.add(command)

    unique: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()
    for finding in findings:
        key = (finding.rule_id, finding.event_index, finding.message)
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return unique
