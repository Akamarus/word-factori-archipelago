import json
import unittest

from tests.installer_fixture import InstallerFixture, ORIGINAL


class InstallerTests(InstallerFixture):
    def test_single_click_command_installs_updates_and_restore_command_keeps_mod(self):
        self.assert_success(self.run_cmd("Install Word Factori Archipelago.cmd"))
        self.assert_installed()
        self.assert_success(self.run_cmd("Install Word Factori Archipelago.cmd"))
        self.assert_installed()
        self.assert_success(self.run_cmd("Restore Original Game.cmd"))
        self.assertEqual(ORIGINAL, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())
        self.assertTrue(self.mod_target.is_dir())
        self.assertTrue(self.world_target.is_file())
        self.assertFalse(self.receipt.exists())

    def test_running_game_prevents_all_destination_writes(self):
        with self.running_game_process():
            before = self.snapshot()
            result = self.install()
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Close Word Factori", result.stderr)
            self.assertEqual(before, self.snapshot())

    def test_game_starting_during_preflight_prevents_destination_writes(self):
        before = self.snapshot()
        result = self.install_with_game_starting_during_preflight()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, self.snapshot())

    def test_clean_install_includes_required_native_patch(self):
        self.assert_success(self.install())
        self.assert_installed()

    def test_preflight_failure_never_creates_destination_directories(self):
        for failure in ("unsupported", "bad_backup", "backup_directory", "bad_delta"):
            with self.subTest(failure=failure):
                self.game.write_bytes(b"unsupported" if failure == "unsupported" else ORIGINAL)
                if self.backup.is_dir(): self.backup.rmdir()
                elif self.backup.exists(): self.backup.unlink()
                if failure == "bad_backup": self.backup.write_bytes(b"not original")
                if failure == "backup_directory": self.backup.mkdir()
                if failure == "bad_delta": self.patch.write_bytes(b"invalid gzip")
                before = self.snapshot()
                self.assertNotEqual(0, self.install().returncode)
                self.assertEqual(before, self.snapshot())

    def test_existing_install_refuses_update_without_force(self):
        self.assert_success(self.install())
        before = self.snapshot()
        result = self.install()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("already installed", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_update_keeps_prior_world_and_mod_as_reported_backups(self):
        self.assert_success(self.install())
        self.world_target.write_bytes(b"old world")
        (self.mod_target / "old-marker.txt").write_text("old mod")
        result = self.install("-Force")
        self.assert_success(result)
        self.assert_installed()
        world_backups = list(self.world_target.parent.glob("*.backup"))
        mod_backups = list((self.local_app_data / "factori/archipelago/install-backups").glob("*/mod"))
        self.assertEqual(1, len(world_backups))
        self.assertEqual(b"old world", world_backups[0].read_bytes())
        self.assertEqual(1, len(mod_backups))
        self.assertEqual("old mod", (mod_backups[0] / "old-marker.txt").read_text())
        self.assertEqual([self.mod_target], list(self.mod_target.parent.iterdir()))
        self.assertIn(str(world_backups[0]), result.stdout)
        self.assertIn(str(mod_backups[0]), result.stdout)

    def test_pairing_checked_against_installed_receipt_before_mod_replacement(self):
        self.assert_success(self.install())
        receipt = json.loads(self.receipt.read_text())
        receipt["game_data"] = str(self.root / "other-game/data.win")
        self.receipt.write_text(json.dumps(receipt))
        before = self.snapshot()
        result = self.install("-Force")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("different game copy", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_native_failure_restores_previous_world_mod_and_game(self):
        self.assert_success(self.install())
        self.assert_success(self.native("-Restore"))
        (self.mod_target / "old-marker.txt").write_text("keep me")
        self.world_target.write_bytes(b"prior world")
        # This new mod blocks receipt creation only after it is committed.
        (self.distribution / "game_mod/word factori archipelago/archipelago_enhanced_install.json").mkdir()
        old_mod = {p.name: p.read_bytes() for p in self.mod_target.iterdir() if p.is_file()}
        result = self.install("-Force")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(b"prior world", self.world_target.read_bytes())
        self.assertEqual(old_mod, {p.name: p.read_bytes() for p in self.mod_target.iterdir() if p.is_file()})
        self.assertEqual(ORIGINAL, self.game.read_bytes())
        self.assertFalse(list(self.mod_target.parent.glob("*.stage")))

    def test_invalid_staged_world_keeps_game_and_installed_files(self):
        self.assert_success(self.install())
        before = self.snapshot()
        (self.distribution / "word_factori.apworld").write_bytes(b"not a zip")
        self.assertNotEqual(0, self.install("-Force").returncode)
        self.assertEqual(before, self.snapshot())

    def test_uninstall_restores_game_preserving_backup_neighbors_and_save(self):
        self.assert_success(self.install())
        neighbor = self.world_target.parent / "neighbor.apworld"
        neighbor.write_bytes(b"neighbor")
        mod_neighbor = self.mod_target.parent / "another mod"
        mod_neighbor.mkdir()
        save = self.local_app_data / "factori/save.json"
        save.write_bytes(b"save")
        self.assert_success(self.install("-Uninstall"))
        self.assertEqual(ORIGINAL, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())
        self.assertFalse(self.world_target.exists())
        self.assertFalse(self.mod_target.exists())
        self.assertEqual(b"neighbor", neighbor.read_bytes())
        self.assertTrue(mod_neighbor.is_dir())
        self.assertEqual(b"save", save.read_bytes())

    def test_uninstall_keeps_mod_receipt_if_game_cannot_restore(self):
        self.assert_success(self.install())
        self.backup.write_bytes(b"corrupt backup")
        before = self.snapshot()
        self.assertNotEqual(0, self.install("-Uninstall").returncode)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
