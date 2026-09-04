from __future__ import annotations

from schema import example


def missing_file(i: int = 0) -> dict:
    path = ["src/auth.ts", "lib/db.py", "app/config.json", "tests/test_login.py"][i % 4]
    listed = "src/\n  index.ts\n  user.ts\nREADME.md"
    return example(
        id=f"missing_file_{i:04d}",
        category="missing_file",
        task=f"Read {path} and summarize the public API.",
        plan=[
            f"Open {path}.",
            "Extract exported functions and types.",
            "Write a short summary.",
        ],
        failed_tool={"name": "read_file", "arguments": {"path": path}},
        failure={
            "code": "ENOENT",
            "message": f"ENOENT: no such file or directory, open '{path}'",
        },
        diagnosis=f"{path} is not on disk. List the project before guessing another path.",
        recovery_plan=[
            "List the repo root.",
            "Pick the closest real file.",
            "Read that file instead of inventing a path.",
        ],
        recovered_tool={"name": "list_dir", "arguments": {"path": "."}},
        success={"listing": listed},
        final="The requested file is missing. Closest files are src/index.ts and src/user.ts. Next step is to read those, not retry the same path.",
        notes="Wrong path is not a reason to hallucinate file contents.",
    )


def bad_cwd(i: int = 0) -> dict:
    return example(
        id=f"bad_cwd_{i:04d}",
        category="bad_cwd",
        task="Run the unit tests for this repo.",
        plan=["Detect package manager.", "Run the test script from the repo root."],
        failed_tool={"name": "run_command", "arguments": {"command": "npm test", "cwd": "/tmp"}},
        failure={
            "code": "ENOENT",
            "exit_code": 127,
            "message": "npm: no package.json found in /tmp",
        },
        diagnosis="Command ran in /tmp, not the project root. The failure is cwd, not the test suite.",
        recovery_plan=["Set cwd to the repo root.", "Run npm test again."],
        recovered_tool={
            "name": "run_command",
            "arguments": {"command": "npm test", "cwd": "."},
        },
        success={"exit_code": 0, "stdout": "8 passed"},
        final="Tests passed after running from the repo root.",
    )


def command_fail(i: int = 0) -> dict:
    return example(
        id=f"command_fail_{i:04d}",
        category="command_fail",
        task="Install dependencies and confirm the lockfile is respected.",
        plan=["Install with npm ci.", "Report whether install succeeded."],
        failed_tool={"name": "run_command", "arguments": {"command": "npm ci"}},
        failure={
            "exit_code": 1,
            "message": "npm ERR! Invalid: lock file's typescript@5.4.5 does not satisfy typescript@6.0.2",
        },
        diagnosis="Lockfile and package.json disagree. Do not delete the lockfile. Report the mismatch and stop before a destructive install.",
        recovery_plan=[
            "Read package.json and package-lock.json versions.",
            "Tell the user the mismatch instead of running npm install.",
        ],
        recovered_tool={"name": "read_file", "arguments": {"path": "package.json"}},
        success={"excerpt": '{"devDependencies":{"typescript":"^6.0.2"}}'},
        final="Install aborted. typescript in package.json is ^6.0.2 but the lockfile pins 5.4.5. Fix the lockfile on purpose; do not silently npm install.",
    )


def conflict(i: int = 0) -> dict:
    return example(
        id=f"conflict_{i:04d}",
        category="conflict",
        task="Replace the old logger import in src/server.ts.",
        plan=["Read src/server.ts.", "Patch the import.", "Write the file back."],
        failed_tool={
            "name": "write_file",
            "arguments": {"path": "src/server.ts", "content": "// patched"},
        },
        failure={
            "code": "CONFLICT",
            "message": "file changed since last read; refuse overwrite",
        },
        diagnosis="The file moved under us. Re-read, then patch the current contents.",
        recovery_plan=["Read src/server.ts again.", "Apply the import change on the fresh text."],
        recovered_tool={"name": "read_file", "arguments": {"path": "src/server.ts"}},
        success={"content": "import { log } from './old-log'\nexport function boot() {}"},
        final="Re-read succeeded. Next write must include the existing boot() body plus the new import.",
    )


def bad_args(i: int = 0) -> dict:
    return example(
        id=f"bad_args_{i:04d}",
        category="bad_args",
        task="Search the repo for TODO comments.",
        plan=["Call repo search with a simple pattern."],
        failed_tool={"name": "search_code", "arguments": {"query": ""}},
        failure={"code": "VALIDATION", "message": "query must be a non-empty string"},
        diagnosis="The tool rejected empty query. Do not retry the same call. Fill the required argument.",
        recovery_plan=["Call search_code with query TODO."],
        recovered_tool={"name": "search_code", "arguments": {"query": "TODO"}},
        success={"matches": ["src/app.ts:12: // TODO handle timeout"]},
        final="Search worked after supplying a real query. One match in src/app.ts.",
    )


def permission(i: int = 0) -> dict:
    return example(
        id=f"permission_{i:04d}",
        category="permission",
        task="Append a debug flag to /etc/hosts.",
        plan=["Edit /etc/hosts.", "Confirm the line exists."],
        failed_tool={
            "name": "write_file",
            "arguments": {"path": "/etc/hosts", "content": "127.0.0.1 debug.local"},
        },
        failure={"code": "EACCES", "message": "permission denied: /etc/hosts"},
        diagnosis="System file is out of scope. Do not sudo. Tell the user and use a project-local file instead.",
        recovery_plan=["Refuse /etc/hosts.", "Offer a project hosts snippet."],
        recovered_tool={
            "name": "write_file",
            "arguments": {"path": "dev/hosts.snippet", "content": "127.0.0.1 debug.local\n"},
        },
        success={"written": "dev/hosts.snippet"},
        final="Did not touch /etc/hosts. Wrote a project snippet at dev/hosts.snippet instead.",
    )


def partial(i: int = 0) -> dict:
    return example(
        id=f"partial_{i:04d}",
        category="partial",
        task="Create src/util/time.ts with now() and format().",
        plan=["Write time.ts with both functions."],
        failed_tool={
            "name": "write_file",
            "arguments": {"path": "src/util/time.ts", "content": "export function now() { return Date.now() }\n"},
        },
        failure={
            "code": "PARTIAL_WRITE",
            "message": "write finished but format() is missing",
            "written_bytes": 48,
        },
        diagnosis="The file exists but the task is incomplete. Read it back and add the missing export instead of rewriting from memory.",
        recovery_plan=["Read src/util/time.ts.", "Append format()."],
        recovered_tool={"name": "read_file", "arguments": {"path": "src/util/time.ts"}},
        success={"content": "export function now() { return Date.now() }\n"},
        final="Confirmed now() only. Next write must keep now() and add format().",
    )


def timeout(i: int = 0) -> dict:
    return example(
        id=f"timeout_{i:04d}",
        category="timeout",
        task="Typecheck the project.",
        plan=["Run tsc --noEmit."],
        failed_tool={"name": "run_command", "arguments": {"command": "npx tsc --noEmit"}},
        failure={"code": "TIMEOUT", "message": "command exceeded 30s"},
        diagnosis="Typecheck hung or the project is huge. Do not loop the same command. Narrow the scope.",
        recovery_plan=["Typecheck a single package or file.", "Report that the full check timed out."],
        recovered_tool={
            "name": "run_command",
            "arguments": {"command": "npx tsc --noEmit -p tsconfig.app.json"},
        },
        success={"exit_code": 0, "stdout": "ok"},
        final="Full-project tsc timed out. Scoped check on tsconfig.app.json passed.",
    )


PRESETS = {
    "missing_file": missing_file,
    "bad_cwd": bad_cwd,
    "command_fail": command_fail,
    "conflict": conflict,
    "bad_args": bad_args,
    "permission": permission,
    "partial": partial,
    "timeout": timeout,
}
