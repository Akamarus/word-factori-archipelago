import unittest
import zipfile
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from tools import build_release
from tools import verify_release
from tools.build_release import ROOT, include


class PublicationTests(unittest.TestCase):
    def test_release_build_is_byte_reproducible(self):
        build_release.write_world()
        build_release.write_release()
        first_world = hashlib.sha256(build_release.WORLD_ARCHIVE.read_bytes()).digest()
        first_release = hashlib.sha256(build_release.RELEASE_ARCHIVE.read_bytes()).digest()

        world_stat = build_release.WORLD_ARCHIVE.stat()
        os.utime(build_release.WORLD_ARCHIVE, (world_stat.st_atime + 10, world_stat.st_mtime + 10))
        build_release.write_release()

        self.assertEqual(first_world, hashlib.sha256(build_release.WORLD_ARCHIVE.read_bytes()).digest())
        self.assertEqual(first_release, hashlib.sha256(build_release.RELEASE_ARCHIVE.read_bytes()).digest())

    def test_player_guides_cover_full_client_and_curated_level_sets_without_overclaiming(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        setup = (ROOT / "word_factori" / "docs" / "setup_en.md").read_text(encoding="utf-8")
        for text in (readme, setup):
            folded = text.casefold()
            for required in (
                "install word factori archipelago.cmd", "f8", "items", "chat",
                "password", "core_campaign", "discovery_labs", "borderless",
                "/wf_overlay restart",
            ):
                self.assertIn(required, folded)
            self.assertIn("experimental", folded)
            self.assertNotIn("release candidate", folded)

    def test_release_includes_friendly_installer_and_excludes_game_font(self):
        build_release.write_world()
        build_release.write_release()

        with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
            names = set(archive.namelist())

        self.assertIn("Install Word Factori Archipelago.cmd", names)
        self.assertIn("release-manifest.json", names)
        self.assertIn("word_factori/campaign_packs.json", names)
        self.assertIn("word_factori/client_messages.py", names)
        self.assertIn("word_factori/overlay_renderer.py", names)
        self.assertFalse(any(name.casefold().endswith("fredokaone.ttf") for name in names))

    def test_release_excludes_temporary_live_rooms(self):
        generated_room = ROOT / "tests" / "live-room-example" / "AP_seed.archipelago"

        self.assertFalse(include(generated_room))

    def test_release_includes_only_approved_live_evidence_images(self):
        approved = ROOT / "docs" / "testing" / "live-overlay-items-composite.png"
        diagnostic = ROOT / "docs" / "testing" / "live-overlay-debug-plane.png"

        self.assertTrue(include(approved))
        self.assertFalse(include(diagnostic))

    def test_sensitive_and_session_artifacts_are_rejected_by_packaging_policy(self):
        prohibited = (
            ROOT / "game_mod" / "word factori archipelago" / "FredokaOne.ttf",
            ROOT / "game_mod" / "word factori archipelago" / "Letters.ttf",
            ROOT / "game_mod" / "word factori archipelago" / "data.win",
            ROOT / "game_mod" / "word factori archipelago" / "recipes.data",
            ROOT / "tests" / "fixture" / "save.json",
            ROOT / ".superpowers" / "session" / "progress.md",
        )

        for path in prohibited:
            with self.subTest(path=path.name):
                self.assertFalse(include(path))

    def test_verifier_defends_against_sensitive_archive_entries(self):
        names = [
            "game_mod/word factori archipelago/FREDOKAONE.TTF",
            "word_factori/.superpowers/session/progress.md",
            "word_factori/client.py",
        ]

        self.assertEqual(names[:2], verify_release.find_prohibited_release_entries(names))

    def test_release_verifier_does_not_require_unshipped_legacy_archive(self):
        build_release.write_world()
        build_release.write_release()
        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
                archive.extractall(directory)
            result = subprocess.run(
                [sys.executable, "tools/verify_release.py"],
                cwd=directory,
                capture_output=True,
                text=True,
            )
            (Path(directory) / "docs" / "testing" / "live-overlay-debug-plane.png").write_bytes(b"debug")
            unexpected = subprocess.run(
                [sys.executable, "tools/verify_release.py"],
                cwd=directory,
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotEqual(0, unexpected.returncode, unexpected.stdout + unexpected.stderr)


if __name__ == "__main__":
    unittest.main()
