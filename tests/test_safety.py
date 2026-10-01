import tempfile
import unittest
from pathlib import Path

from chaos_pass.safety import diff_snapshots, snapshot_path

class SafetyTests(unittest.TestCase):
    def test_snapshot_detects_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "a.txt"
            file.write_text("one", encoding="utf-8")
            before = snapshot_path(root)
            file.write_text("two", encoding="utf-8")
            after = snapshot_path(root)
            self.assertEqual(diff_snapshots(before, after), ["CHANGED a.txt"])

    def test_snapshot_detects_add_remove(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = root / "a.txt"
            a.write_text("a", encoding="utf-8")
            before = snapshot_path(root)
            a.unlink()
            (root / "b.txt").write_text("b", encoding="utf-8")
            after = snapshot_path(root)
            self.assertEqual(diff_snapshots(before, after), ["REMOVED a.txt", "ADDED b.txt"])

if __name__ == "__main__":
    unittest.main()
