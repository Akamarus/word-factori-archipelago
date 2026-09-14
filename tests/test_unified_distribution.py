import dataclasses
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tests import test_world_layout as fixtures
from tools import build_release


class UnifiedDistributionTests(unittest.TestCase):
    def test_linux_installer_runs_from_extracted_player_zip_without_source_checkout(self):
        build_release.write_world()
        build_release.write_release()
        with tempfile.TemporaryDirectory(prefix="wf package ") as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
                for name in ("Install Word Factori Archipelago.sh", "tools/install_linux.py",
                             "tools/linux_transaction.py", "tools/enhanced_delta.py", "docs/linux-proton.md"):
                    self.assertIn(name, archive.namelist())
                self.assertNotIn(b"\r", archive.read("Install Word Factori Archipelago.sh"))
                with zipfile.ZipFile(io.BytesIO(archive.read("word_factori.apworld"))) as world:
                    self.assertIn("word_factori/platform_paths.py", world.namelist())
                archive.extractall(root)
            self.assertFalse((root / "word_factori").exists())
            result = subprocess.run([sys.executable, "-E", "-s", str(root / "tools/install_linux.py"), "--help"],
                                    cwd=root, capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("--config", result.stdout)
            if sys.platform.startswith("linux"):
                result = subprocess.run(["bash", str(root / "Install Word Factori Archipelago.sh"), "--help"],
                                        cwd=root.parent, capture_output=True, text=True, timeout=30)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("--ap-worlds", result.stdout)

    def test_missing_or_modified_patch_cannot_replace_the_player_archive(self):
        build_release.write_world()
        build_release.write_release()
        before = hashlib.sha256(build_release.RELEASE_ARCHIVE.read_bytes()).digest()
        with tempfile.TemporaryDirectory(dir=build_release.ROOT) as temporary:
            missing = Path(temporary) / "enhanced.patch.gz"
            with patch.object(build_release, "PATCH_FILE", missing):
                with self.assertRaises(FileNotFoundError):
                    build_release.write_release()
                missing.write_bytes(b"corrupted patch")
                with self.assertRaisesRegex(ValueError, "patch failed verification"):
                    build_release.write_release()
        self.assertEqual(before, hashlib.sha256(build_release.RELEASE_ARCHIVE.read_bytes()).digest())

    def test_default_world_needs_no_mode_options_and_uses_native_machine_rules(self):
        world = fixtures.WorldLayoutTests().make_world(47)
        del world.options.integration_mode
        del world.options.campaign_layout
        # Generate with only the options exposed by the unified integration.
        world.generate_early()
        slot = world.fill_slot_data()
        self.assertEqual("enhanced", slot["integration_mode"])
        self.assertEqual("machines_enhanced_four_of_six_v1", slot["progression_model"])
        self.assertFalse(slot["reload_required_for_items"])
        self.assertEqual(4, slot["tutorial_page_unlock_count"])

    def test_generation_does_not_offer_a_second_integration_or_layout(self):
        fields = {field.name for field in dataclasses.fields(fixtures.world_options.WordFactoriOptions)}
        self.assertNotIn("integration_mode", fields)
        self.assertNotIn("campaign_layout", fields)

    def test_one_player_archive_contains_the_required_patch_and_restore_tool(self):
        build_release.write_world()
        build_release.write_release()
        with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
            names = set(archive.namelist())
            self.assertIn("tools/install_enhanced.ps1", names)
            self.assertIn("tools/enhanced.patch.gz", names)
            self.assertIn("Restore Original Game.cmd", names)
            self.assertIn("Install Word Factori Archipelago.cmd", names)
            self.assertNotIn("Install or Update Playtest.cmd", names)
            self.assertNotIn("Enhanced Player.yaml", names)


if __name__ == "__main__":
    unittest.main()
