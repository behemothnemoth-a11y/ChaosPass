import tempfile
import unittest
from pathlib import Path
import json

from chaos_pass.adapters import discover_adapters
from chaos_pass.config import TargetConfig
from chaos_pass.profiles import load_profile_definition
from chaos_pass.regressions import load_regression_cases

class RegressionCorpusTests(unittest.TestCase):
    def test_corpus_loads_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / "regressions"
            directory.mkdir()
            (directory / "history.json").write_text(
                json.dumps({
                    "cases": [{
                        "id": "CASE-1",
                        "title": "Historical behavior",
                        "historical_symptom": "old symptom",
                        "current_expectation": "stays fixed",
                        "regression_test": "tests/test_demo.py::test_case",
                    }]
                }),
                encoding="utf-8",
            )
            cases = load_regression_cases(root)
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].case_id, "CASE-1")

    def test_regression_adapter_surfaces_historical_cases_in_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / "regressions"
            directory.mkdir()
            (directory / "history.json").write_text(
                json.dumps({
                    "cases": [{
                        "id": "CASE-2",
                        "title": "Repeat-safe scenario",
                        "historical_symptom": "old collision",
                        "current_expectation": "no collision",
                        "regression_test": "tests/test_demo.py::test_repeat",
                    }]
                }),
                encoding="utf-8",
            )
            fingerprint, stack = discover_adapters(root, TargetConfig({}, None))
            self.assertIn("regression-corpus", stack.names)
            plan = stack.plan(load_profile_definition("regression-archaeologist"))
            self.assertTrue(any(
                action.action_id == "CASE-2"
                and action.source_adapter == "regression-corpus"
                and not action.executable
                for action in plan.actions
            ))

    def test_chaospass_self_corpus_contains_known_findings(self):
        repo_root = Path(__file__).resolve().parents[1]
        cases = load_regression_cases(repo_root)
        ids = {case.case_id for case in cases}
        self.assertTrue({
            "CP-SELF-001",
            "CP-SELF-002",
            "CP-SELF-003",
            "CP-SELF-004",
            "CP-SELF-005",
        }.issubset(ids))

if __name__ == "__main__":
    unittest.main()