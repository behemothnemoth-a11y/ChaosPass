import tempfile
import unittest
from pathlib import Path

from chaos_pass.runner import run
from chaos_pass.safety import snapshot_path

class RunnerTests(unittest.TestCase):
    def test_full_pass_leaves_original_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "target"
            target.mkdir()
            (target / "alpha.txt").write_text("alpha", encoding="utf-8")
            nested = target / "nested"
            nested.mkdir()
            (nested / "beta.txt").write_text("beta", encoding="utf-8")

            before = snapshot_path(target)
            report = run(target, "full-chaos-pass", 32 * 1024 * 1024, seed=1234)
            after = snapshot_path(target)

            self.assertTrue(report.integrity_passed)
            self.assertEqual(before, after)
            self.assertTrue(any(f.profile == "charlie" for f in report.findings))
            self.assertTrue(any(f.profile == "wildcard" for f in report.findings))
            self.assertTrue(any(f.profile == "expert-baseline" for f in report.findings))

if __name__ == "__main__":
    unittest.main()
