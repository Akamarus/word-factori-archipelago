import unittest
import zipfile

from tools import build_release
from tools import verify_release
from tools.build_release import ROOT, include


class PublicationTests(unittest.TestCase):
    def test_release_includes_friendly_installer_and_excludes_game_font(self):
        build_release.write_world()
        build_release.write_release()

        with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
            names = set(archive.namelist())

        self.assertIn("Install Word Factori Archipelago.cmd", names)
        self.assertFalse(any(name.casefold().endswith("fredokaone.ttf") for name in names))

    def test_release_excludes_temporary_live_rooms(self):
        generated_room = ROOT / "tests" / "live-room-example" / "AP_seed.archipelago"

        self.assertFalse(include(generated_room))

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


if __name__ == "__main__":
    unittest.main()
