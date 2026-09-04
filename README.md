# failtrace

Generate one recovery-style agent training example from a task + a broken tool result.

Default output is JSONL. Each line is one complete episode:

task → plan → tool call → failure → recovery plan → recovered call → success.

## Run

```bash
python failtrace.py --preset missing_file
python failtrace.py --preset missing_file --count 20 -o out.jsonl
python failtrace.py --list
python failtrace.py --task "Add a test for login" --tool read_file --args '{"path":"src/auth.ts"}' --error "ENOENT: no such file or directory"
```

## Presets

| id | failure |
|---|---|
| missing_file | path does not exist |
| bad_cwd | command run in wrong directory |
| command_fail | nonzero exit |
| conflict | file changed under you |
| bad_args | tool rejected arguments |
| permission | read-only / denied |
| partial | tool wrote only half the work |
| timeout | tool timed out |

Add a new preset in `presets.py`. Do not invent a new schema until the old one fills.
