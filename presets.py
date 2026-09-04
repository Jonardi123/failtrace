from __future__ import annotations

from schema import example


def _pick(seq, i: int):
    return seq[i % len(seq)]


def _stamp_path(path: str, i: int) -> str:
    parent, name = path.rsplit("/", 1) if "/" in path else (".", path)
    if "." in name:
        stem, ext = name.rsplit(".", 1)
        return f"{parent}/{stem}_{i}.{ext}"
    return f"{parent}/{name}_{i}"


def missing_file(i: int = 0) -> dict:
    path = _stamp_path(
        _pick(
            [
                "src/auth.ts",
                "lib/db.py",
                "app/config.json",
                "tests/test_login.py",
                "pkg/session.go",
                "server/router.js",
                "client/api.tsx",
                "scripts/migrate.rb",
                "internal/cache.rs",
                "cmd/main.java",
            ],
            i,
        ),
        i,
    )
    listed = _pick(
        [
            "src/\n  index.ts\n  user.ts\nREADME.md",
            "lib/\n  store.py\n  util.py\nREADME.md",
            "app/\n  main.py\n  settings.py\nREADME.md",
            "tests/\n  test_app.py\n  conftest.py\nREADME.md",
        ],
        i,
    )
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
        final=f"The requested file {path} is missing. Closest files are in the listing. Next step is to read those, not retry the same path.",
        notes="Wrong path is not a reason to hallucinate file contents.",
    )


def bad_cwd(i: int = 0) -> dict:
    command, tool_name, ok_stdout = _pick(
        [
            ("npm test", "npm", "8 passed"),
            ("pytest", "pytest", "12 passed"),
            ("go test ./...", "go", "ok"),
            ("cargo test", "cargo", "test result: ok"),
            ("make test", "make", "all tests passed"),
            ("poetry run pytest", "Poetry", "9 passed"),
            ("mvn test", "mvn", "BUILD SUCCESS"),
            ("bundle exec rspec", "rspec", "32 examples, 0 failures"),
            ("pnpm test", "pnpm", "6 passed"),
            ("yarn test", "yarn", "4 passed"),
        ],
        i,
    )
    cwd = _pick(
        ["/tmp", "/var/tmp", "/home", "/opt", "/root", "/usr/local", "/mnt", "/data", "/workspace", "/tmp/build"],
        i,
    )
    command = f"{command} --run-id {i}"
    return example(
        id=f"bad_cwd_{i:04d}",
        category="bad_cwd",
        task=f"Run the unit tests for this repo using `{command}`.",
        plan=["Detect package manager.", "Run the test script from the repo root."],
        failed_tool={"name": "run_command", "arguments": {"command": command, "cwd": cwd}},
        failure={
            "code": "ENOENT",
            "exit_code": 127,
            "message": f"{tool_name}: no project file found in {cwd} (run-id {i})",
        },
        diagnosis=f"Command ran in {cwd}, not the project root. The failure is cwd, not the test suite.",
        recovery_plan=["Set cwd to the repo root.", f"Run `{command}` again."],
        recovered_tool={
            "name": "run_command",
            "arguments": {"command": command, "cwd": "."},
        },
        success={"exit_code": 0, "stdout": ok_stdout},
        final=f"Tests passed after running `{command}` from the repo root instead of {cwd}.",
    )


def command_fail(i: int = 0) -> dict:
    command, lock_path, pkg, locked, wanted, excerpt = _pick(
        [
            (
                "npm ci",
                "package-lock.json",
                "typescript",
                "5.4.5",
                "6.0.2",
                '{"devDependencies":{"typescript":"^6.0.2"}}',
            ),
            (
                "pip install -r requirements.txt",
                "requirements.lock",
                "django",
                "4.2.1",
                "5.0.0",
                '{"django":"^5.0.0"}',
            ),
            (
                "poetry install --no-root",
                "poetry.lock",
                "pydantic",
                "1.10.14",
                "2.8.0",
                '{"pydantic":"^2.8.0"}',
            ),
            (
                "pnpm install --frozen-lockfile",
                "pnpm-lock.yaml",
                "react",
                "18.2.0",
                "19.0.0",
                '{"dependencies":{"react":"^19.0.0"}}',
            ),
            (
                "yarn install --immutable",
                "yarn.lock",
                "eslint",
                "8.57.0",
                "9.9.0",
                '{"devDependencies":{"eslint":"^9.9.0"}}',
            ),
            (
                "cargo build --locked",
                "Cargo.lock",
                "serde",
                "1.0.197",
                "1.0.210",
                'serde = "1.0.210"',
            ),
            (
                "go mod download",
                "go.sum",
                "golang.org/x/net",
                "v0.22.0",
                "v0.28.0",
                "require golang.org/x/net v0.28.0",
            ),
            (
                "bundle install --deployment",
                "Gemfile.lock",
                "rails",
                "7.1.3",
                "7.2.0",
                'gem "rails", "~> 7.2.0"',
            ),
            (
                "composer install --no-dev",
                "composer.lock",
                "symfony/console",
                "6.4.3",
                "7.1.0",
                '{"require":{"symfony/console":"^7.1.0"}}',
            ),
            (
                "uv sync --frozen",
                "uv.lock",
                "httpx",
                "0.27.0",
                "0.28.1",
                'httpx = "^0.28.1"',
            ),
        ],
        i,
    )
    read_path = _stamp_path(_pick(["package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Gemfile"], i), i)
    command = f"{command} --run-id {i}"
    return example(
        id=f"command_fail_{i:04d}",
        category="command_fail",
        task=f"Install dependencies with `{command}` and confirm {lock_path} is respected.",
        plan=[f"Install with `{command}`.", "Report whether install succeeded."],
        failed_tool={"name": "run_command", "arguments": {"command": command}},
        failure={
            "exit_code": 1,
            "message": f"ERR! Invalid: {lock_path} has {pkg}@{locked} which does not satisfy {pkg}@{wanted} (run-id {i})",
        },
        diagnosis=f"{lock_path} and the manifest disagree on {pkg}. Do not delete the lockfile. Report the mismatch and stop before a destructive install.",
        recovery_plan=[
            f"Read {read_path} and {lock_path} versions.",
            "Tell the user the mismatch instead of forcing an install.",
        ],
        recovered_tool={"name": "read_file", "arguments": {"path": read_path}},
        success={"excerpt": excerpt},
        final=f"Install aborted. {pkg} in {read_path} is {wanted} but {lock_path} pins {locked}. Fix the lockfile on purpose; do not silently reinstall.",
    )


def conflict(i: int = 0) -> dict:
    path = _stamp_path(
        _pick(
            [
                "src/server.ts",
                "lib/app.py",
                "pkg/router.go",
                "app/models.rb",
                "client/store.tsx",
                "internal/db.rs",
                "cmd/worker.java",
                "server/auth.js",
                "src/config.toml",
                "tests/helpers.mjs",
            ],
            i,
        ),
        i,
    )
    old_import = _pick(
        [
            "import { log } from './old-log'",
            "from old_log import log",
            'import "old-log"',
            "require('./old-log')",
        ],
        i,
    )
    return example(
        id=f"conflict_{i:04d}",
        category="conflict",
        task=f"Replace the old logger import in {path}.",
        plan=[f"Read {path}.", "Patch the import.", "Write the file back."],
        failed_tool={
            "name": "write_file",
            "arguments": {"path": path, "content": f"// patched {i}"},
        },
        failure={
            "code": "CONFLICT",
            "message": f"file {path} changed since last read; refuse overwrite (rev {i})",
        },
        diagnosis=f"{path} moved under us. Re-read, then patch the current contents.",
        recovery_plan=[f"Read {path} again.", "Apply the import change on the fresh text."],
        recovered_tool={"name": "read_file", "arguments": {"path": path}},
        success={"content": f"{old_import}\nexport function boot() {{}}"},
        final=f"Re-read of {path} succeeded. Next write must include the existing boot() body plus the new import.",
    )


def bad_args(i: int = 0) -> dict:
    bad_query = _pick(["", " ", "\t", "??", "***", "{}", "null", "[]", ".", ".."], i)
    good_query = _pick(["TODO", "FIXME", "HACK", "XXX", "NOTE", "BUG", "deprecated", "panic", "unwrap", "todo!"], i)
    match_path = _stamp_path(_pick(["src/app.ts", "lib/main.py", "pkg/server.go", "app/job.rb"], i), i)
    return example(
        id=f"bad_args_{i:04d}",
        category="bad_args",
        task=f"Search the repo for {good_query} comments in {match_path}.",
        plan=["Call repo search with a simple pattern."],
        failed_tool={"name": "search_code", "arguments": {"query": bad_query}},
        failure={
            "code": "VALIDATION",
            "message": f"query {bad_query!r} is invalid; need a non-empty search string (case {i})",
        },
        diagnosis="The tool rejected the query. Do not retry the same call. Fill the required argument.",
        recovery_plan=[f"Call search_code with query {good_query}."],
        recovered_tool={"name": "search_code", "arguments": {"query": good_query}},
        success={"matches": [f"{match_path}:12: // {good_query} handle timeout"]},
        final=f"Search worked after supplying {good_query!r}. One match in {match_path}.",
    )


def permission(i: int = 0) -> dict:
    path = _stamp_path(
        _pick(
            [
                "/etc/hosts",
                "/etc/passwd",
                "/etc/sudoers",
                "/var/log/syslog",
                "/root/.ssh/authorized_keys",
                "/etc/ssh/sshd_config",
                "/var/spool/cron/root",
                "/etc/systemd/system/app.service",
                "/boot/grub/grub.cfg",
                "/etc/nginx/nginx.conf",
            ],
            i,
        ),
        i,
    )
    snippet = _stamp_path(
        _pick(
            [
                "dev/hosts.snippet",
                "dev/passwd.snippet",
                "dev/sudoers.snippet",
                "dev/syslog.snippet",
                "dev/authorized_keys.snippet",
                "dev/sshd_config.snippet",
                "dev/cron.snippet",
                "dev/app.service.snippet",
                "dev/grub.cfg.snippet",
                "dev/nginx.conf.snippet",
            ],
            i,
        ),
        i,
    )
    line = _pick(
        [
            "127.0.0.1 debug.local",
            "127.0.0.1 api.local",
            "10.0.0.2 cache.local",
            "192.168.1.10 app.local",
        ],
        i,
    )
    return example(
        id=f"permission_{i:04d}",
        category="permission",
        task=f"Append `{line}` to {path}.",
        plan=[f"Edit {path}.", "Confirm the line exists."],
        failed_tool={
            "name": "write_file",
            "arguments": {"path": path, "content": line},
        },
        failure={"code": "EACCES", "message": f"permission denied: {path} (attempt {i})"},
        diagnosis=f"System file {path} is out of scope. Do not sudo. Tell the user and use a project-local file instead.",
        recovery_plan=[f"Refuse {path}.", f"Offer a project snippet at {snippet}."],
        recovered_tool={
            "name": "write_file",
            "arguments": {"path": snippet, "content": line + "\n"},
        },
        success={"written": snippet},
        final=f"Did not touch {path}. Wrote a project snippet at {snippet} instead.",
    )


def partial(i: int = 0) -> dict:
    path = _stamp_path(
        _pick(
            [
                "src/util/time.ts",
                "lib/text.py",
                "pkg/ids.go",
                "app/money.rb",
                "client/date.tsx",
                "internal/hash.rs",
                "server/slug.js",
                "src/util/url.mjs",
                "cmd/format.java",
                "tests/helpers.ts",
            ],
            i,
        ),
        i,
    )
    have, missing = _pick(
        [
            ("now", "format"),
            ("trim", "slugify"),
            ("new_id", "parse_id"),
            ("cents", "format_money"),
            ("parse", "formatDate"),
            ("digest", "hex"),
            ("encode", "decode"),
            ("join", "split"),
            ("pad", "clip"),
            ("ok", "err"),
        ],
        i,
    )
    written = f"export function {have}() {{ return Date.now() }}\n"
    return example(
        id=f"partial_{i:04d}",
        category="partial",
        task=f"Create {path} with {have}() and {missing}().",
        plan=[f"Write {path} with both functions."],
        failed_tool={
            "name": "write_file",
            "arguments": {"path": path, "content": written},
        },
        failure={
            "code": "PARTIAL_WRITE",
            "message": f"write finished but {missing}() is missing from {path} (bytes={40 + i})",
            "written_bytes": 40 + i,
        },
        diagnosis=f"{path} exists but the task is incomplete. Read it back and add the missing export instead of rewriting from memory.",
        recovery_plan=[f"Read {path}.", f"Append {missing}()."],
        recovered_tool={"name": "read_file", "arguments": {"path": path}},
        success={"content": written},
        final=f"Confirmed {have}() only in {path}. Next write must keep {have}() and add {missing}().",
    )


def timeout(i: int = 0) -> dict:
    command, scoped, task = _pick(
        [
            ("npx tsc --noEmit", "npx tsc --noEmit -p tsconfig.app.json", "Typecheck the project."),
            ("pytest", "pytest tests/test_unit.py", "Run the full test suite."),
            ("cargo test --workspace", "cargo test -p app", "Test every crate."),
            ("go test ./...", "go test ./internal/app", "Run all Go tests."),
            ("npm run lint", "npx eslint src/index.ts", "Lint the whole repo."),
            ("mypy .", "mypy src/app.py", "Typecheck all Python."),
            ("mvn -q test", "mvn -q -pl app test", "Run Maven tests."),
            ("bundle exec rspec", "bundle exec rspec spec/models", "Run RSpec."),
            ("pnpm -r build", "pnpm --filter web build", "Build every package."),
            ("make all", "make app", "Build the entire project."),
        ],
        i,
    )
    command = f"{command} --run-id {i}"
    scoped = f"{scoped} --run-id {i}"
    seconds = 30 + (i % 12) * 5
    return example(
        id=f"timeout_{i:04d}",
        category="timeout",
        task=f"{task} Use `{command}`.",
        plan=[f"Run `{command}`."],
        failed_tool={"name": "run_command", "arguments": {"command": command}},
        failure={"code": "TIMEOUT", "message": f"command exceeded {seconds}s: {command}"},
        diagnosis="The command hung or the project is huge. Do not loop the same command. Narrow the scope.",
        recovery_plan=[f"Run `{scoped}` instead.", "Report that the full command timed out."],
        recovered_tool={
            "name": "run_command",
            "arguments": {"command": scoped},
        },
        success={"exit_code": 0, "stdout": "ok"},
        final=f"`{command}` timed out after {seconds}s. Scoped `{scoped}` passed.",
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
