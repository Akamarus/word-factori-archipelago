import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from word_factori import enhanced_runtime as runtime


class RuntimeTests(unittest.TestCase):
    def test_linux_receipt_must_match_selected_installation_and_patched_game(self):
        from word_factori.platform_paths import InstallationPaths
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game" / "data.win"
            game.parent.mkdir()
            game.write_bytes(b"patched fixture")
            prefix = root / "pfx"
            factori = prefix / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "factori"
            mod = factori / "mods" / "word factori archipelago"
            mod.mkdir(parents=True)
            worlds = root / "custom_worlds"
            worlds.mkdir()
            paths = InstallationPaths(game, prefix, factori)
            receipt = {"protocol": runtime.PATCH_PROTOCOL, "original_sha256": runtime.ORIGINAL_SHA256,
                       "patched_sha256": runtime.PATCHED_SHA256, "game_data": str(game),
                       "platform": "linux", "prefix": str(prefix), "factori_root": str(factori),
                       "ap_worlds": str(worlds)}
            backup = game.with_name("data.wf-ap-original.win")
            backup.write_bytes(b"original fixture")
            with patch.object(runtime, "ORIGINAL_SHA256", hashlib.sha256(backup.read_bytes()).hexdigest()), \
                 patch.object(runtime, "PATCHED_SHA256", hashlib.sha256(game.read_bytes()).hexdigest()):
                receipt["original_sha256"] = runtime.ORIGINAL_SHA256
                receipt["patched_sha256"] = runtime.PATCHED_SHA256
                (mod / runtime.RECEIPT_NAME).write_text(json.dumps(receipt))
                self.assertTrue(runtime.patch_readiness(mod, paths).ready)
                other_mod = root / "other" / "mods" / "word factori archipelago"
                other_mod.mkdir(parents=True)
                (other_mod / runtime.RECEIPT_NAME).write_text(json.dumps(receipt))
                self.assertFalse(runtime.patch_readiness(other_mod, paths).ready)
                for field in ("game_data", "prefix", "factori_root", "ap_worlds"):
                    altered = dict(receipt, **{field: str(root / "another")})
                    (mod / runtime.RECEIPT_NAME).write_text(json.dumps(altered))
                    self.assertFalse(runtime.patch_readiness(mod, paths).ready, field)
                (mod / runtime.RECEIPT_NAME).write_text(json.dumps(receipt))
                game.write_bytes(b"updated game")
                self.assertEqual("game_hash_mismatch", runtime.patch_readiness(mod, paths).code)
                game.write_bytes(b"original fixture")
                self.assertIn("unpatched", runtime.patch_readiness(mod, paths).message)

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
