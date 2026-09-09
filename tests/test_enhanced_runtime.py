import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from word_factori import enhanced_runtime as runtime


class RuntimeTests(unittest.TestCase):
    def test_publication_is_idempotent_across_restart_and_revisions_increase(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            levels = [{"text": "I", "module_counts": {"Merger2": 0}}]
            self.assertTrue(runtime.publish_runtime(path, "a" * 64, "b" * 64, levels))
            first = path.read_bytes()
            self.assertFalse(runtime.publish_runtime(path, "a" * 64, "b" * 64, levels))
            self.assertEqual(first, path.read_bytes())
            levels[0]["module_counts"] = {}
            self.assertTrue(runtime.publish_runtime(path, "a" * 64, "b" * 64, levels))
            second = json.loads(path.read_text())
            self.assertGreater(second["revision"], json.loads(first)["revision"])
            self.assertEqual({}, second["levels"][0]["module_counts"])

    def test_failed_atomic_replace_preserves_last_valid_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            runtime.publish_runtime(path, "a" * 64, "b" * 64, [{"text": "I", "module_counts": {}}])
            before = path.read_bytes()
            with patch("word_factori.mod.os.replace", side_effect=OSError("busy")):
                with self.assertRaises(OSError):
                    runtime.publish_runtime(path, "c" * 64, "b" * 64, [{"text": "I", "module_counts": {}}])
            self.assertEqual(before, path.read_bytes())
            self.assertEqual([path], list(path.parent.iterdir()))

    def test_wrong_identity_and_non_finite_caps_are_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            for room, counts in (("x", {}), ("a" * 64, {"Merger2": float("nan")}), ("a" * 64, {"other": 1}), ("a" * 64, {"Bend": True})):
                with self.assertRaises(ValueError):
                    runtime.publish_runtime(path, room, "b" * 64, [{"text": "I", "module_counts": counts}])
            self.assertFalse(path.exists())


if __name__ == "__main__": unittest.main()
