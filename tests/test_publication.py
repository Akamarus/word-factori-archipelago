import unittest
import zipfile
import hashlib
import json
import os
from pathlib import Path
import tempfile

from tools import build_release
from tools import verify_release
from tools.build_release import ROOT, include


class PublicationTests(unittest.TestCase):
    EXPECTED_WORLD_ENTRIES = {
        "word_factori/Components.py",
        "word_factori/__init__.py",
        "word_factori/archipelago.json",
        "word_factori/bridge.py",
        "word_factori/campaign.json",
        "word_factori/campaign.py",
        "word_factori/campaign_packs.json",
        "word_factori/capabilities.py",
        "word_factori/client.py",
        "word_factori/client_core.py",
        "word_factori/client_messages.py",
        "word_factori/data.py",
        "word_factori/dispatch.py",
        "word_factori/dispatch_store.py",
        "word_factori/docs/setup_en.md",
        "word_factori/layout.py",
        "word_factori/mod.py",
        "word_factori/options.py",
        "word_factori/overlay_model.py",
        "word_factori/overlay_preferences.py",
        "word_factori/overlay_protocol.py",
        "word_factori/overlay_renderer.py",
        "word_factori/overlay_supervisor.py",
        "word_factori/recipe_graph.py",
        "word_factori/requirements.py",
        "word_factori/save.py",
        "word_factori/version.py",
        "word_factori/window_tracker.py",
    }

    def test_release_text_formats_have_deterministic_checkout_line_endings(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()

        self.assertTrue(
            {
                "*.py text eol=lf",
                "*.json text eol=lf",
                "*.md text eol=lf",
                "*.yml text eol=lf",
                "*.yaml text eol=lf",
                "LICENSE text eol=lf",
                "*.ps1 text eol=crlf",
                "*.cmd text eol=crlf",
            }.issubset(set(attributes))
        )

    def test_public_attribution_matches_the_maintainer_approved_identity(self):
        from word_factori.version import AUTHOR

        metadata = json.loads((ROOT / "word_factori" / "archipelago.json").read_text(encoding="utf-8"))
        credits = json.loads(
            (ROOT / "game_mod" / "word factori archipelago" / "credits.json").read_text(
                encoding="utf-8"
            )
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        approved_disclosure = (
            "Created and maintained by Jack (@Akamarus). AI tools were used extensively "
            "for planning, implementation assistance, documentation, and review. Jack "
            "directed the project, made the product and integration decisions, performed "
            "live game testing, validated release behavior, and retains responsibility "
            "for maintenance and releases."
        )

        self.assertEqual(["Akamarus"], metadata["authors"])
        self.assertEqual("Akamarus", AUTHOR)
        self.assertIn("Independent community integration", credits["LeftPage"])
        self.assertEqual(
            approved_disclosure,
            " ".join(credits["LeftPage"][2:] + credits["RightPage"][1:2]),
        )
        self.assertIn(approved_disclosure, readme)
        self.assertTrue(readme.startswith("# Word Factori Archipelago"))
        self.assertTrue(
            readme[readme.index("Created and maintained"):].startswith(
                "Created and maintained by Jack (@Akamarus)"
            )
        )
        self.assertIn("Copyright (c) 2026 Jack (@Akamarus)", license_text)

    def test_release_version_is_shared_by_world_metadata_and_player_archive(self):
        from word_factori.version import VERSION

        metadata = json.loads((ROOT / "word_factori" / "archipelago.json").read_text(encoding="utf-8"))

        self.assertEqual("1.3.0", VERSION)
        self.assertEqual(VERSION, metadata["world_version"])
        self.assertEqual("0.6.7", metadata["minimum_ap_version"])
        self.assertEqual("0.6.7", metadata["maximum_ap_version"])
        self.assertEqual(9, metadata["version"])
        self.assertEqual(7, metadata["compatible_version"])
        self.assertEqual(f"word-factori-archipelago-{VERSION}.zip", build_release.RELEASE_ARCHIVE.name)

    def test_examples_select_seed_specific_shuffled_pages(self):
        for name in ("WordFactori.yaml", "WordFactoriTarget.yaml"):
            example = (ROOT / "examples" / name).read_text(encoding="utf-8")

            self.assertIn("campaign_layout: shuffled_pages", example)

    def test_readme_explains_the_any_four_page_unlock(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8").casefold()

        self.assertIn("four of the six", readme)

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
        self.assertNotIn("Automated verification covers generation", readme)

    def test_apworld_contains_only_the_explicit_runtime_payload(self):
        unexpected = ROOT / "word_factori" / "unexpected-debug.txt"
        unexpected.write_text("must never enter the APWorld", encoding="utf-8")
        try:
            build_release.write_world()
        finally:
            unexpected.unlink()

        with zipfile.ZipFile(build_release.WORLD_ARCHIVE) as archive:
            self.assertEqual(self.EXPECTED_WORLD_ENTRIES, set(archive.namelist()))

    def test_player_release_contains_only_the_supported_player_payload(self):
        build_release.write_world()
        build_release.write_release()

        with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
            names = set(archive.namelist())

        self.assertEqual(
            {
                "Install Word Factori Archipelago.cmd",
                "LICENSE",
                "README.md",
                "docs/images/word-factori-archipelago-chat.png",
                "docs/images/word-factori-discovery-lab-v.png",
                "examples/WordFactori.yaml",
                "examples/WordFactoriTarget.yaml",
                "game_mod/word factori archipelago/archipelago_campaign.json",
                "game_mod/word factori archipelago/credits.json",
                "game_mod/word factori archipelago/levels.json",
                "game_mod/word factori archipelago/recipes.json",
                "game_mod/word factori archipelago/tips.json",
                "install.ps1",
                "release-manifest.json",
                "word_factori.apworld",
            },
            names,
        )

    def test_release_excludes_temporary_live_rooms(self):
        generated_room = ROOT / "tests" / "live-room-example" / "AP_seed.archipelago"

        self.assertFalse(include(generated_room))

    def test_player_release_policy_rejects_testing_evidence_images(self):
        evidence = ROOT / "docs" / "testing" / "live-overlay-items-composite.png"
        diagnostic = ROOT / "docs" / "testing" / "live-overlay-debug-plane.png"

        self.assertFalse(include(evidence))
        self.assertFalse(include(diagnostic))

    def test_sensitive_and_session_artifacts_are_rejected_by_packaging_policy(self):
        prohibited = (
            ROOT / "game_mod" / "word factori archipelago" / "FredokaOne.ttf",
            ROOT / "game_mod" / "word factori archipelago" / "Letters.ttf",
            ROOT / "game_mod" / "word factori archipelago" / "data.win",
            ROOT / "game_mod" / "word factori archipelago" / "recipes.data",
            ROOT / "tests" / "fixture" / "save.json",
            ROOT / ".superpowers" / "session" / "progress.md",
            ROOT / "docs" / "superpowers" / "plans" / "internal.md",
        )

        for path in prohibited:
            with self.subTest(path=path.name):
                self.assertFalse(include(path))

    def test_verifier_defends_against_sensitive_archive_entries(self):
        names = [
            "game_mod/word factori archipelago/FREDOKAONE.TTF",
            "word_factori/.superpowers/session/progress.md",
            "docs/superpowers/plans/internal.md",
            "word_factori/client.py",
        ]

        self.assertEqual(names[:3], verify_release.find_prohibited_release_entries(names))

    def test_distribution_docs_reference_only_shipped_installer_files(self):
        build_release.write_world()
        build_release.write_release()
        with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
            release_files = set(archive.namelist())

        documents = (
            ROOT / "README.md",
            ROOT / "docs" / "release-notes-v1.2.0-correction.md",
            ROOT / "docs" / "release-notes-v1.2.1.md",
            ROOT / "docs" / "release-notes-v1.2.2.md",
            ROOT / "docs" / "release-notes-v1.3.0.md",
        )
        missing = {
            path.relative_to(ROOT).as_posix(): verify_release.find_missing_documented_installers(
                path.read_text(encoding="utf-8"), release_files
            )
            for path in documents
        }

        self.assertEqual({path.relative_to(ROOT).as_posix(): [] for path in documents}, missing)

    def test_readme_local_images_exist_and_are_in_the_player_package(self):
        build_release.write_world()
        build_release.write_release()
        with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
            release_files = set(archive.namelist())

        missing = verify_release.find_missing_local_markdown_images(
            (ROOT / "README.md").read_text(encoding="utf-8"), release_files
        )

        self.assertEqual([], missing)

    def test_readme_local_links_resolve_in_checkout_and_player_package(self):
        build_release.write_world()
        build_release.write_release()
        with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
            release_files = set(archive.namelist())

        missing = verify_release.find_missing_local_markdown_links(
            (ROOT / "README.md").read_text(encoding="utf-8"), release_files
        )

        self.assertEqual([], missing)

    def test_release_verifier_rejects_unexpected_player_archive_entries(self):
        build_release.write_world()
        build_release.write_release()
        with tempfile.TemporaryDirectory() as directory:
            tampered = Path(directory) / build_release.RELEASE_ARCHIVE.name
            tampered.write_bytes(build_release.RELEASE_ARCHIVE.read_bytes())
            with zipfile.ZipFile(tampered, "a") as archive:
                archive.writestr("unexpected-debug.txt", b"debug")

            with self.assertRaisesRegex(AssertionError, "archive parity failed"):
                verify_release.verify_archive_matches_disk(
                    tampered, ("docs/images", "examples", "game_mod")
                )


if __name__ == "__main__":
    unittest.main()
