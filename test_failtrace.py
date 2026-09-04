#!/usr/bin/env python3
"""Lock failtrace.v1 and the CLI that emits it."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from presets import PRESETS
from schema import SCHEMA_VERSION, example

ROOT = Path(__file__).resolve().parent
REQUIRED_KEYS = {
    "schema",
    "id",
    "category",
    "split",
    "task",
    "plan",
    "trace",
    "labels",
    "notes",
}
LABEL_KEYS = {"should_retry", "should_call_tool_after_fail", "failure_class"}
TRACE_SHAPE = [
    ("assistant", "plan"),
    ("assistant", "tool_call"),
    ("tool", None),
    ("assistant", "diagnosis"),
    ("assistant", "plan_update"),
    ("assistant", "tool_call"),
    ("tool", None),
    ("assistant", "final"),
]


def cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "failtrace.py"), *argv],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def parse_jsonl(text: str) -> list[dict]:
    lines = [line for line in text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def failed_and_recovered(row: dict) -> tuple[dict, dict, dict, dict]:
    calls = [step for step in row["trace"] if step.get("type") == "tool_call"]
    tools = [step for step in row["trace"] if step.get("role") == "tool"]
    if len(calls) != 2 or len(tools) != 2:
        raise AssertionError("trace must have two tool_call steps and two tool results")
    return calls[0], tools[0], calls[1], tools[1]


def assert_valid_v1(test: unittest.TestCase, row: dict) -> None:
    test.assertIsInstance(row, dict)
    test.assertEqual(row.keys(), REQUIRED_KEYS)
    test.assertEqual(row["schema"], SCHEMA_VERSION)
    test.assertEqual(row["schema"], "failtrace.v1")
    test.assertIsInstance(row["id"], str)
    test.assertTrue(row["id"])
    test.assertIsInstance(row["category"], str)
    test.assertTrue(row["category"])
    test.assertEqual(row["split"], "train")
    test.assertIsInstance(row["task"], str)
    test.assertTrue(row["task"])
    test.assertIsInstance(row["plan"], list)
    test.assertTrue(row["plan"])
    test.assertTrue(all(isinstance(item, str) and item for item in row["plan"]))
    test.assertIsInstance(row["notes"], str)
    test.assertIsInstance(row["labels"], dict)
    test.assertEqual(row["labels"].keys(), LABEL_KEYS)
    test.assertIs(row["labels"]["should_retry"], True)
    test.assertIs(row["labels"]["should_call_tool_after_fail"], True)
    test.assertEqual(row["labels"]["failure_class"], row["category"])

    trace = row["trace"]
    test.assertIsInstance(trace, list)
    test.assertEqual(len(trace), len(TRACE_SHAPE))
    for step, (role, step_type) in zip(trace, TRACE_SHAPE):
        test.assertEqual(step["role"], role)
        if step_type is None:
            test.assertNotIn("type", step)
        else:
            test.assertEqual(step["type"], step_type)

    failed_call, failed_result, recovered_call, recovered_result = failed_and_recovered(row)
    test.assertIs(failed_result["ok"], False)
    test.assertIn("error", failed_result)
    test.assertIsInstance(failed_result["error"], dict)
    test.assertTrue(failed_result["error"])
    test.assertIs(recovered_result["ok"], True)
    test.assertIn("result", recovered_result)
    test.assertIsInstance(recovered_result["result"], dict)

    tool_results = [step for step in trace if step.get("role") == "tool"]
    test.assertEqual(sum(1 for step in tool_results if step["ok"] is False), 1)
    test.assertEqual(sum(1 for step in tool_results if step["ok"] is True), 1)
    fail_at = next(i for i, step in enumerate(trace) if step.get("role") == "tool" and step["ok"] is False)
    recover_at = next(i for i, step in enumerate(trace) if step.get("role") == "tool" and step["ok"] is True)
    test.assertLess(fail_at, recover_at)

    test.assertEqual(failed_call["tool"], failed_result["tool"])
    test.assertEqual(recovered_call["tool"], recovered_result["tool"])
    test.assertIsInstance(failed_call["arguments"], dict)
    test.assertIsInstance(recovered_call["arguments"], dict)
    same_name = failed_call["tool"] == recovered_call["tool"]
    same_args = failed_call["arguments"] == recovered_call["arguments"]
    test.assertFalse(
        same_name and same_args,
        "recovered tool name or arguments must differ from the failed call",
    )
    json.dumps(row)


class SchemaTests(unittest.TestCase):
    def test_every_preset_emits_valid_v1(self) -> None:
        self.assertTrue(PRESETS)
        for name, factory in PRESETS.items():
            with self.subTest(preset=name):
                row = factory(0)
                assert_valid_v1(self, row)
                self.assertEqual(row["category"], name)
                self.assertTrue(row["id"].startswith(name))

    def test_trace_is_one_failed_call_then_a_different_recovery(self) -> None:
        for name, factory in PRESETS.items():
            with self.subTest(preset=name):
                row = factory(0)
                failed_call, failed_result, recovered_call, recovered_result = failed_and_recovered(row)
                self.assertIs(failed_result["ok"], False)
                self.assertIs(recovered_result["ok"], True)
                self.assertNotEqual(
                    (failed_call["tool"], failed_call["arguments"]),
                    (recovered_call["tool"], recovered_call["arguments"]),
                )

    def test_example_helper_matches_locked_shape(self) -> None:
        row = example(
            id="lock_0000",
            category="lock",
            task="do a thing",
            plan=["step"],
            failed_tool={"name": "read_file", "arguments": {"path": "a"}},
            failure={"code": "ENOENT", "message": "missing"},
            diagnosis="gone",
            recovery_plan=["list"],
            recovered_tool={"name": "list_dir", "arguments": {"path": "."}},
            success={"listing": "ok"},
            final="stop",
        )
        assert_valid_v1(self, row)


class CliTests(unittest.TestCase):
    def test_list_prints_every_preset(self) -> None:
        result = cli("--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        names = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(names, sorted(PRESETS))
        self.assertFalse(result.stdout.strip() == "")

    def test_preset_emits_one_valid_json_line(self) -> None:
        result = cli("--preset", "missing_file")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = parse_jsonl(result.stdout)
        self.assertEqual(len(rows), 1)
        assert_valid_v1(self, rows[0])
        self.assertEqual(rows[0]["category"], "missing_file")

    def test_count_emits_that_many_jsonl_rows(self) -> None:
        result = cli("--preset", "bad_cwd", "--count", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = parse_jsonl(result.stdout)
        self.assertEqual(len(rows), 3)
        ids = [row["id"] for row in rows]
        self.assertEqual(ids, ["bad_cwd_0000", "bad_cwd_0001", "bad_cwd_0002"])
        for row in rows:
            assert_valid_v1(self, row)

    def test_every_preset_flag_works(self) -> None:
        for name in PRESETS:
            with self.subTest(preset=name):
                result = cli("--preset", name, "--count", "1")
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = parse_jsonl(result.stdout)
                self.assertEqual(len(rows), 1)
                assert_valid_v1(self, rows[0])
                self.assertEqual(rows[0]["category"], name)

    def test_custom_task_tool_error(self) -> None:
        result = cli(
            "--task",
            "Add a test for login",
            "--tool",
            "read_file",
            "--args",
            '{"path":"src/auth.ts"}',
            "--error",
            "ENOENT: no such file or directory",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = parse_jsonl(result.stdout)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        assert_valid_v1(self, row)
        self.assertEqual(row["category"], "custom")
        self.assertEqual(row["task"], "Add a test for login")
        failed_call, failed_result, recovered_call, _ = failed_and_recovered(row)
        self.assertEqual(failed_call["tool"], "read_file")
        self.assertEqual(failed_call["arguments"], {"path": "src/auth.ts"})
        self.assertEqual(failed_result["error"]["message"], "ENOENT: no such file or directory")
        self.assertNotEqual(failed_call["tool"], recovered_call["tool"])

    def test_custom_missing_fields_exits(self) -> None:
        result = cli("--task", "only a task")
        self.assertNotEqual(result.returncode, 0)

    def test_out_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.jsonl"
            result = cli("--preset", "timeout", "--count", "2", "-o", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = parse_jsonl(path.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 2)
            for row in rows:
                assert_valid_v1(self, row)


class VarietyTests(unittest.TestCase):
    COUNT = 20

    def test_count_20_is_not_cloned_rows(self) -> None:
        for name, factory in PRESETS.items():
            with self.subTest(preset=name):
                rows = [factory(i) for i in range(self.COUNT)]
                self.assertEqual(len(rows), self.COUNT)
                ids = [row["id"] for row in rows]
                self.assertEqual(len(set(ids)), self.COUNT)
                bodies = []
                for row in rows:
                    assert_valid_v1(self, row)
                    body = {k: v for k, v in row.items() if k != "id"}
                    bodies.append(json.dumps(body, sort_keys=True))
                self.assertEqual(len(set(bodies)), self.COUNT, f"{name} repeated whole rows")

    def test_index_varies_path_command_error_and_task(self) -> None:
        for name, factory in PRESETS.items():
            with self.subTest(preset=name):
                rows = [factory(i) for i in range(self.COUNT)]
                tasks = [row["task"] for row in rows]
                errors = []
                paths = []
                commands = []
                for row in rows:
                    failed_call, failed_result, _, _ = failed_and_recovered(row)
                    errors.append(failed_result["error"]["message"])
                    args = failed_call["arguments"]
                    if "path" in args:
                        paths.append(args["path"])
                    if "command" in args:
                        commands.append(args["command"])
                self.assertEqual(len(set(tasks)), self.COUNT, f"{name} cloned task")
                self.assertEqual(len(set(errors)), self.COUNT, f"{name} cloned error")
                if paths:
                    self.assertEqual(len(set(paths)), self.COUNT, f"{name} cloned path")
                if commands:
                    self.assertEqual(len(set(commands)), self.COUNT, f"{name} cloned command")

    def test_cli_count_20_unique(self) -> None:
        result = cli("--preset", "missing_file", "--count", "20")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = parse_jsonl(result.stdout)
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({row["id"] for row in rows}), 20)
        self.assertEqual(len({row["task"] for row in rows}), 20)


class MixTests(unittest.TestCase):
    def test_mix_emits_n_valid_jsonl_rows(self) -> None:
        result = cli("--mix", "20")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = parse_jsonl(result.stdout)
        self.assertEqual(len(rows), 20)
        for row in rows:
            assert_valid_v1(self, row)

    def test_mix_is_balanced_across_presets(self) -> None:
        n = 20
        result = cli("--mix", str(n))
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = parse_jsonl(result.stdout)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["category"]] = counts.get(row["category"], 0) + 1
        self.assertEqual(set(counts), set(PRESETS))
        values = list(counts.values())
        self.assertLessEqual(max(values) - min(values), 1)
        self.assertEqual(sum(values), n)

    def test_mix_ids_are_unique(self) -> None:
        result = cli("--mix", "24")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = parse_jsonl(result.stdout)
        ids = [row["id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_mix_writes_jsonl_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mix.jsonl"
            result = cli("--mix", "8", "-o", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(path.exists())
            rows = parse_jsonl(path.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 8)
            self.assertEqual({row["category"] for row in rows}, set(PRESETS))
            for row in rows:
                assert_valid_v1(self, row)

    def test_mix_rejects_preset(self) -> None:
        result = cli("--mix", "4", "--preset", "timeout")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
