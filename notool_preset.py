"""Text-only recovery examples. Import notool into PRESETS in presets.py."""

from schema import example


def _pick(seq, i: int):
    return seq[i % len(seq)]


def notool(i: int = 0) -> dict:
    task, diagnosis, answer = _pick(
        [
            (
                "What does ENOENT mean on Linux? Do not search the repo.",
                "The question is a definition. Searching does not help.",
                "ENOENT means the path does not exist. Answer in text; do not call another search.",
            ),
            (
                "Should I run mkfs on /dev/sda to free space for the build?",
                "Formatting a disk is out of scope. Refuse in text.",
                "No. Do not format disks. Delete build artifacts in the project instead.",
            ),
            (
                "Explain why npm ci fails when the lockfile pins typescript 5.4.5 but package.json wants 6.0.2.",
                "The mismatch is already in the question. Do not force install.",
                "npm ci failed because the lockfile and package.json disagree. Fix the lockfile on purpose.",
            ),
            (
                "The user pasted 'permission denied: /etc/hosts'. What should the agent do next?",
                "Do not retry /etc/hosts. Explain the refusal.",
                "Stop. Use a project-local snippet instead of editing system files.",
            ),
            (
                "Convert 150 minutes to hours. No tools.",
                "This is arithmetic. A shell is not required.",
                "150 minutes is 2.5 hours.",
            ),
            (
                "Does should_retry mean repeat the exact same tool call?",
                "The label is defined by the question. Do not invent a docs file.",
                "No. It means attempt recovery, not replay the identical call.",
            ),
            (
                "Just tell me if this JSON is valid: {\"a\":1}.",
                "The JSON is already in the prompt. Validate it in text.",
                "Yes, that object is valid JSON. No file write needed.",
            ),
            (
                "Name one reason not to delete package-lock.json after npm ci fails.",
                "Do not delete the lockfile. Answer the question.",
                "Deleting the lockfile throws away the pinned graph and invites a silent drift install.",
            ),
            (
                "Is list_dir the right next step after ENOENT on a guessed path?",
                "You already know the path is missing. Do not guess another read.",
                "Yes. List the tree instead of inventing a new path.",
            ),
            (
                "Reply with only: refuse sudo. The user asked you to sudo make install.",
                "sudo is out of policy. Do not find another command.",
                "Refuse sudo. Install into the project directory without privilege.",
            ),
        ],
        i,
    )
    task = f"{task} [case {i}]"
    query = f"unneeded-lookup-{i}"
    return example(
        id=f"notool_{i:04d}",
        category="notool",
        task=task,
        plan=["Call a search tool in case the answer is in the repo."],
        failed_tool={"name": "search_code", "arguments": {"query": query}},
        failure={
            "code": "NOT_NEEDED",
            "message": f"search is the wrong move for this question (case {i}, q={query})",
        },
        diagnosis=diagnosis,
        recovery_plan=["Stop calling tools.", "Answer in text with the reply tool."],
        recovered_tool={"name": "reply", "arguments": {"text": answer}},
        success={"replied": True},
        final=answer,
        notes="The recovery is text. A second side-effect tool is a miss.",
    )
