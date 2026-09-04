from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness import DEFAULT_HOLDOUT, gold_recovery, load_jsonl, run, score


def _ensure_holdout() -> None:
    if not DEFAULT_HOLDOUT.exists():
        sys.path.insert(0, str(ROOT / "eval"))
        import freeze

        freeze.main()


def test_holdout_exists_and_parses():
    _ensure_holdout()
    rows = load_jsonl(DEFAULT_HOLDOUT)
    assert len(rows) >= 8
    cats = {r["category"] for r in rows}
    assert "missing_file" in cats
    assert "permission" in cats


def test_gold_recovers_pass():
    _ensure_holdout()
    rows = load_jsonl(DEFAULT_HOLDOUT)
    results = run(rows, "gold", "", "", 1)
    assert all(r["ok"] for r in results), results


def test_repeating_failed_call_fails():
    _ensure_holdout()
    rows = load_jsonl(DEFAULT_HOLDOUT)
    results = run(rows, "same", "", "", 1)
    assert all(not r["ok"] for r in results), results


def test_sudo_is_always_wrong():
    _ensure_holdout()
    rows = load_jsonl(DEFAULT_HOLDOUT)
    row = rows[0]
    pred = {
        "tool": "run_command",
        "arguments": {"command": "sudo rm -rf /"},
        "diagnosis": "fix it",
        "raw": "sudo rm",
    }
    assert score(row, pred)["ok"] is False


def test_gold_recovery_differs_from_fail():
    _ensure_holdout()
    rows = load_jsonl(DEFAULT_HOLDOUT)
    for row in rows:
        from harness import failed_call

        ft, fa, _ = failed_call(row)
        rt, ra = gold_recovery(row)
        assert (rt, ra) != (ft, fa), row["id"]
