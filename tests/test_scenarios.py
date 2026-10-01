import tempfile
import unittest
from pathlib import Path

from chaos_pass.scenarios import (
    deep_nesting,
    path_length_boundary,
    rename_churn,
    wildcard_chain,
)

class ScenarioRepeatabilityTests(unittest.TestCase):
    def test_rename_churn_can_run_twice_for_same_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = rename_churn(root, "chaos-goblin")
            second = rename_churn(root, "chaos-goblin")
            self.assertEqual(first.status, "SURVIVED")
            self.assertEqual(second.status, "SURVIVED")

    def test_deep_nesting_uses_short_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            result = deep_nesting(Path(temp), "boundary-hunter")
            self.assertEqual(result.status, "SURVIVED")
            self.assertTrue(any(item == "depth=24" for item in result.evidence))

    def test_path_length_probe_characterizes_limit_instead_of_throwing(self):
        with tempfile.TemporaryDirectory() as temp:
            result = path_length_boundary(Path(temp), "boundary-hunter")
            self.assertIn(result.status, {"SURVIVED", "BEND"})
            self.assertTrue(result.evidence)

    def test_wildcard_chain_is_repeat_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = wildcard_chain(root, "wildcard", 123)
            second = wildcard_chain(root, "wildcard", 123)
            self.assertTrue(first)
            self.assertTrue(second)
            self.assertFalse(any(f.status == "BREAK" for f in first))
            self.assertFalse(any(f.status == "BREAK" for f in second))

if __name__ == "__main__":
    unittest.main()