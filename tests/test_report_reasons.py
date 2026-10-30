"""Regression tests for failure-reason reporting."""

import unittest

from failtrace_report import summarize


class ReportReasonTests(unittest.TestCase):
    def test_string_reason_is_counted_once_not_by_character(self):
        report = summarize([{"ok": False, "category": "tool", "reasons": "command timed out"}])
        self.assertEqual(report["failure_reasons"], [
            {"reason": "command timed out", "count": 1}
        ])

    def test_list_reasons_preserve_counts(self):
        report = summarize([
            {"ok": False, "reasons": ["timeout", "retry failed"]},
            {"ok": False, "reasons": ["timeout"]},
        ])
        self.assertEqual(report["failure_reasons"], [
            {"reason": "timeout", "count": 2},
            {"reason": "retry failed", "count": 1},
        ])

    def test_missing_or_empty_reasons_use_fallback(self):
        report = summarize([
            {"ok": False, "reasons": None},
            {"ok": False, "reasons": ""},
            {"ok": False, "reasons": []},
        ])
        self.assertEqual(report["failure_reasons"], [
            {"reason": "unspecified failure", "count": 3}
        ])


if __name__ == "__main__":
    unittest.main()
