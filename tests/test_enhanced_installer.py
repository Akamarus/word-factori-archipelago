import unittest
import json
import hashlib
from pathlib import Path

from tests.installer_fixture import InstallerFixture, ORIGINAL, PATCHED, LEGACY, PREVIOUS, RELEASE150


class NativeInstallerTests(InstallerFixture):
    def test_release_150_upgrade_and_restore_preserve_original(self):
        self.mod_target.mkdir(parents=True)
        self.game.write_bytes(RELEASE150)
        self.backup.write_bytes(ORIGINAL)
        self.receipt.write_text(json.dumps({"protocol": "enhanced_v2",
            "capability": "free_word_machine_enforcement_v1",
            "original_sha256": hashlib.sha256(ORIGINAL).hexdigest(),
            "patched_sha256": hashlib.sha256(RELEASE150).hexdigest(),
            "game_data": str(self.game.resolve())}))
        self.assert_success(self.native())
        self.assertEqual(PATCHED, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())
        self.assert_success(self.native('-Restore'))
        self.assertEqual(ORIGINAL, self.game.read_bytes())

    def test_previous_v2_upgrade_and_restore_preserve_original(self):
        self.mod_target.mkdir(parents=True)
        self.game.write_bytes(PREVIOUS)
        self.backup.write_bytes(ORIGINAL)
        self.receipt.write_text(json.dumps({"protocol": "enhanced_v2",
            "capability": "free_word_machine_enforcement_v1",
            "original_sha256": hashlib.sha256(ORIGINAL).hexdigest(),
            "patched_sha256": hashlib.sha256(PREVIOUS).hexdigest(),
            "game_data": str(self.game.resolve())}))
        self.assert_success(self.native())
        self.assertEqual(PATCHED, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())
        self.assert_success(self.native('-Restore'))
        self.assertEqual(ORIGINAL, self.game.read_bytes())

    def legacy_installation(self):
        self.mod_target.mkdir(parents=True)
        self.game.write_bytes(LEGACY)
        self.backup.write_bytes(ORIGINAL)
        self.receipt.write_text(json.dumps({"protocol": "enhanced_v1",
            "original_sha256": hashlib.sha256(ORIGINAL).hexdigest(),
            "patched_sha256": hashlib.sha256(LEGACY).hexdigest(), "game_data": str(self.game.resolve())}))

    def test_legacy_upgrade_preserves_backup_and_writes_enforcement_receipt(self):
        self.legacy_installation()
        self.assert_success(self.native())
        self.assertEqual(PATCHED, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual("enhanced_v2", receipt["protocol"])
        self.assertEqual("free_word_machine_enforcement_v1", receipt["capability"])
        before = self.snapshot()
        self.assert_success(self.native())
        self.assertEqual(before, self.snapshot())

    def test_legacy_missing_or_corrupt_backup_refuses_without_writes(self):
        self.legacy_installation()
        for payload in (None, b"corrupt backup"):
            if payload is None:
                self.backup.unlink()
            else:
                self.backup.write_bytes(payload)
            before = self.snapshot()
            self.assertNotEqual(0, self.native().returncode)
            self.assertEqual(before, self.snapshot())

    def test_legacy_restore_keeps_verified_original_backup(self):
        self.legacy_installation()
        self.assert_success(self.native('-Restore'))
        self.assertEqual(ORIGINAL, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())
        self.assertFalse(self.receipt.exists())

    def test_legacy_receipt_write_failure_restores_exact_previous_game(self):
        self.legacy_installation()
        self.receipt.unlink()
        self.receipt.mkdir()
        self.assertNotEqual(0, self.native().returncode)
        self.assertEqual(LEGACY, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())

    def test_current_receipt_missing_capability_refuses_changes(self):
        self.mod_target.mkdir(parents=True)
        self.assert_success(self.native())
        document = json.loads(self.receipt.read_text())
        document.pop('capability')
        self.receipt.write_text(json.dumps(document))
        before = self.snapshot()
        self.assertNotEqual(0, self.native().returncode)
        self.assertEqual(before, self.snapshot())

    def test_check_only_returns_game_path_without_creating_missing_mod_or_backup(self):
        before = self.snapshot()
        result = self.native("-CheckOnly")
        self.assert_success(result)
        resolved_game = Path(result.stdout.strip())
        self.assertTrue(resolved_game.is_absolute())
        self.assertTrue(self.game.samefile(resolved_game))
        self.assertEqual(before, self.snapshot())

    def test_unknown_game_is_rejected_without_writes_for_install_and_restore(self):
        self.game.write_bytes(b"unknown build")
        for args in ((), ("-Restore",), ("-CheckOnly",)):
            before = self.snapshot()
            self.assertNotEqual(0, self.native(*args).returncode)
            self.assertEqual(before, self.snapshot())

    def test_patched_game_still_requires_valid_delta_in_preflight(self):
        self.mod_target.mkdir(parents=True)
        self.assert_success(self.native())
        self.assert_success(self.native("-CheckOnly"))
        self.patch.write_bytes(b"corrupt gzip")
        before = self.snapshot()
        self.assertNotEqual(0, self.native("-CheckOnly").returncode)
        self.assertEqual(before, self.snapshot())

    def test_running_game_blocks_restore_without_removing_receipt(self):
        self.mod_target.mkdir(parents=True)
        self.assert_success(self.native())
        with self.running_game_process():
            before = self.snapshot()
            result = self.native("-Restore")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Close Word Factori", result.stderr)
            self.assertEqual(before, self.snapshot())

    def test_receipt_failure_rolls_game_back_and_keeps_original_backup(self):
        self.mod_target.mkdir(parents=True)
        self.receipt.mkdir()
        self.assertNotEqual(0, self.native().returncode)
        self.assertEqual(ORIGINAL, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())
        self.assertFalse(list(self.game_dir.glob("*.tmp")))

    def test_restore_keeps_mod_and_backup_but_removes_receipt(self):
        self.mod_target.mkdir(parents=True)
        marker = self.mod_target / "levels.json"
        marker.write_bytes(b"[]")
        self.assert_success(self.native())
        self.assertEqual(PATCHED, self.game.read_bytes())
        self.assert_success(self.native("-Restore"))
        self.assertEqual(ORIGINAL, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())
        self.assertFalse(self.receipt.exists())
        self.assertEqual(b"[]", marker.read_bytes())


if __name__ == "__main__":
    unittest.main()
