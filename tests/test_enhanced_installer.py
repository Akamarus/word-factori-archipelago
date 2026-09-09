import unittest
from pathlib import Path

from tests.installer_fixture import InstallerFixture, ORIGINAL, PATCHED


class NativeInstallerTests(InstallerFixture):
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
