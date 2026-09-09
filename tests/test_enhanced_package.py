from pathlib import Path
import tempfile
import unittest
from tools.build_enhanced_playtest import build_playtest


class EnhancedPackageTests(unittest.TestCase):
    def test_unknown_game_is_refused_before_creating_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.win"
            original.write_bytes(b"unknown game")
            output = root / "playtest.zip"
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                build_playtest(original, root / "missing.win", output)
            self.assertFalse(output.exists())

    def test_existing_archive_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "playtest.zip"
            output.write_bytes(b"keep")
            with self.assertRaisesRegex(ValueError, "exists"):
                build_playtest(root / "missing.win", root / "missing2.win", output)
            self.assertEqual(b"keep", output.read_bytes())
