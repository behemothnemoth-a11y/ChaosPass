from __future__ import annotations

import io
from contextlib import redirect_stdout
import unittest

from chaos_pass.builtin_adapters import _configured_probe_failure_classification
from chaos_pass.cli import build_parser

class CliRegressionTests(unittest.TestCase):
    def test_plan_help_includes_description(self):
        parser = build_parser()
        output = io.StringIO()
        with self.assertRaises(SystemExit) as exc, redirect_stdout(output):
            parser.parse_args(["plan", "--help"])
        self.assertEqual(exc.exception.code, 0)
        self.assertIn(
            "Build a read-only persona-to-adapter attack plan",
            output.getvalue(),
        )

    def test_configured_probe_failure_classification(self):
        self.assertEqual(
            _configured_probe_failure_classification(
                "adapter:expert-ux", {}, timed_out=False
            ),
            ("BEND", "medium"),
        )
        self.assertEqual(
            _configured_probe_failure_classification(
                "adapter:expert-accessibility", {}, timed_out=False
            ),
            ("BEND", "medium"),
        )
        self.assertEqual(
            _configured_probe_failure_classification(
                "adapter:expert-qa", {}, timed_out=False
            ),
            ("BREAK", "high"),
        )
        self.assertEqual(
            _configured_probe_failure_classification(
                "adapter:expert-ux",
                {"failure_status": "WEIRD", "failure_severity": "low"},
                timed_out=False,
            ),
            ("WEIRD", "low"),
        )

if __name__ == "__main__":
    unittest.main()