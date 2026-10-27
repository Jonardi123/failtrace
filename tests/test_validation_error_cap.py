"""Regression tests for failtrace validation error limits."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from failtrace_validate import validate_sources


class ValidationErrorLimitTests(unittest.TestCase):
    def test_one_malformed_row_cannot_exceed_error_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.jsonl"
            # A single row violates several independent schema requirements.
            path.write_text('{"schema":"wrong","trace":[]}\n', encoding="utf-8")
            checked_all, all_issues = validate_sources([str(path)], max_errors=100)
            self.assertEqual(checked_all, 1)
            self.assertGreater(len(all_issues), 3)

            for limit in (1, 2, 3):
                with self.subTest(max_errors=limit):
                    checked, issues = validate_sources([str(path)], max_errors=limit)
                    self.assertEqual(checked, 1)
                    self.assertEqual(len(issues), limit)
                    self.assertEqual(issues, all_issues[:limit])

    def test_duplicate_id_does_not_allow_extra_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.jsonl"
            # Both rows are malformed; the second also repeats an ID.
            path.write_text(
                '{"id":"same","schema":"wrong","trace":[]}\n'
                '{"id":"same","schema":"wrong","trace":[]}\n',
                encoding="utf-8",
            )
            checked_all, all_issues = validate_sources([str(path)], max_errors=100)
            self.assertEqual(checked_all, 2)
            self.assertTrue(any("duplicate id" in issue.message for issue in all_issues))
            limit = next(
                index + 1
                for index, issue in enumerate(all_issues)
                if "duplicate id" in issue.message
            )
            checked, issues = validate_sources([str(path)], max_errors=limit)
            self.assertEqual(checked, 2)
            self.assertEqual(len(issues), limit)
            self.assertEqual(issues, all_issues[:limit])


if __name__ == "__main__":
    unittest.main()
