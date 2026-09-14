import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from word_factori.platform_paths import (
    InstallationPaths, config_path, discover_installations, load_installation,
    resolve_proton_path, save_installation, selected_proton_mod,
    validate_installation,
)


MOD = "word factori archipelago"
APP = "2072840"


class PlatformPathsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)

    def installation(self, library=None, user="Player", game_dir="Word Factori"):
        library = library or self.home / "Steam"
        game_data = library / "steamapps" / "common" / game_dir / "data.win"
        game_data.parent.mkdir(parents=True, exist_ok=True)
        game_data.write_bytes(b"game")
        prefix = library / "steamapps" / "compatdata" / APP / "pfx"
        factori = prefix / "drive_c" / "users" / user / "AppData" / "Local" / "factori"
        factori.mkdir(parents=True, exist_ok=True)
        (factori / "mods" / MOD).mkdir(parents=True, exist_ok=True)
        return InstallationPaths(game_data, prefix, factori)

    def manifest(self, library, game_dir="Word Factori"):
        steamapps = library / "steamapps"
        steamapps.mkdir(parents=True, exist_ok=True)
        (steamapps / f"appmanifest_{APP}.acf").write_text(
            f'"AppState" {{ "appid" "{APP}" "installdir" "{game_dir}" }}',
            encoding="utf-8",
        )

    def directory_alias(self, target, alias):
        alias.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(target, alias, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            if os.name != "nt":
                self.skipTest(f"directory symlinks unavailable: {error}")
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(target)],
                                    capture_output=True, text=True)
            if result.returncode:
                self.skipTest(f"directory aliases unavailable: {result.stderr}")

    def test_round_trip_descriptor_and_derived_folders(self):
        paths = self.installation()
        config = self.home / "config" / "installation.json"
        self.assertEqual(validate_installation(paths), paths)
        self.assertEqual(paths.local_app_data, paths.factori_root.parent)
        self.assertEqual(paths.mod_folder, paths.factori_root / "mods" / MOD)
        save_installation(paths, config)
        self.assertEqual(load_installation(config), paths)
        self.assertEqual(json.loads(config.read_text(encoding="utf-8")), {
            "schema": 1,
            "game_data": str(paths.game_data),
            "prefix": str(paths.prefix),
            "factori_root": str(paths.factori_root),
        })

    def test_relative_xdg_does_not_redirect_config(self):
        actual = config_path({"XDG_CONFIG_HOME": "relative"}, self.home)
        self.assertEqual(actual, self.home / ".config/word-factori-archipelago/installation.json")

    def test_absolute_xdg_config_home(self):
        xdg = self.home / "XDG config"
        self.assertEqual(config_path({"XDG_CONFIG_HOME": str(xdg)}, self.home),
                         xdg / "word-factori-archipelago" / "installation.json")

    def test_invalid_descriptors_and_configuration_fail_closed(self):
        paths = self.installation()
        for bad in (
            InstallationPaths(Path("relative/data.win"), paths.prefix, paths.factori_root),
            InstallationPaths(paths.game_data.with_name("other.win"), paths.prefix, paths.factori_root),
            InstallationPaths(paths.game_data, paths.prefix, paths.factori_root.parent / "other"),
            InstallationPaths(paths.game_data, paths.prefix, self.home / "outsider"),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_installation(bad)
        config = self.home / "bad.json"
        for payload in (
            {"schema": 2, "game_data": str(paths.game_data), "prefix": str(paths.prefix), "factori_root": str(paths.factori_root)},
            {"schema": 1, "game_data": "relative/data.win", "prefix": str(paths.prefix), "factori_root": str(paths.factori_root)},
            {"schema": 1, "game_data": str(paths.game_data), "prefix": str(paths.prefix), "factori_root": str(paths.factori_root), "password": "secret"},
        ):
            config.write_text(json.dumps(payload), encoding="utf-8")
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                load_installation(config)
        config.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_installation(config)

    def test_missing_and_ambiguous_users_are_not_guessed(self):
        paths = self.installation()
        # A second user's valid factori directory must not be silently selected.
        other = paths.prefix / "drive_c/users/Other/AppData/Local/factori"
        other.mkdir(parents=True)
        self.manifest(self.home / "Steam")
        self.assertEqual(len(discover_installations([self.home / "Steam"])), 2)
        missing = self.home / "missing-prefix"
        with self.assertRaises(ValueError):
            validate_installation(InstallationPaths(paths.game_data, missing, paths.factori_root))

    def test_native_and_flatpak_roots_and_spaced_additional_library(self):
        native = self.home / ".local/share/Steam"
        flatpak = self.home / ".var/app/com.valvesoftware.Steam/.local/share/Steam"
        additional = self.home / "Extra Steam Library"
        for root in (native, flatpak):
            paths = self.installation(root)
            self.manifest(root)
            self.assertIn(paths, discover_installations([root]))
        extra_paths = self.installation(additional, game_dir="Word Factori Deluxe")
        self.manifest(additional, "Word Factori Deluxe")
        (native / "steamapps/libraryfolders.vdf").write_text(
            '"libraryfolders" { "0" { "path" "' + str(native).replace("\\", "\\\\") +
            '" } "1" { "path" "' + str(additional).replace("\\", "\\\\") +
            '" "apps" { "2072840" "123" } } }', encoding="utf-8")
        self.assertIn(extra_paths, discover_installations([native]))

    def test_missing_prefix_malformed_vdf_and_duplicate_roots(self):
        root = self.home / "Steam"
        paths = self.installation(root)
        self.manifest(root)
        self.assertEqual(discover_installations([root, root]), [paths])
        (root / "steamapps/libraryfolders.vdf").write_text('"libraryfolders" { "1" { "path"', encoding="utf-8")
        self.assertEqual(discover_installations([root]), [paths])
        other = self.home / "No Prefix"
        self.manifest(other)
        game = other / "steamapps/common/Word Factori/data.win"
        game.parent.mkdir(parents=True)
        game.write_bytes(b"game")
        self.assertEqual(discover_installations([other]), [])

    def test_manifest_rejects_wrong_app_and_traversal(self):
        root = self.home / "Steam"
        self.installation(root)
        manifest = root / f"steamapps/appmanifest_{APP}.acf"
        for body in ('"AppState" { "appid" "123" "installdir" "Word Factori" }',
                     '"AppState" { "appid" "2072840" "installdir" "../Word Factori" }'):
            manifest.write_text(body, encoding="utf-8")
            self.assertEqual(discover_installations([root]), [])

    def test_explicit_descriptor_does_not_require_steam_metadata(self):
        paths = self.installation(self.home / "Custom Game")
        self.assertEqual(validate_installation(paths), paths)

    def test_windows_drive_paths_and_mod_selection(self):
        paths = self.installation()
        expected = paths.mod_folder
        self.assertEqual(resolve_proton_path(r"C:\Users\Player\AppData\Local\factori\mods\word factori archipelago", paths.prefix), expected)
        self.assertEqual(resolve_proton_path("C:/Users/Player/AppData/Local/factori/mods/word factori archipelago", paths.prefix), expected)
        for value in (MOD, "mods/" + MOD, "mods\\" + MOD,
                      r"C:\Users\Player\AppData\Local\factori\mods\word factori archipelago"):
            with self.subTest(value=value):
                self.assertTrue(selected_proton_mod({"folder": value}, paths))
        for value in ("other/" + MOD, "mods/nested/" + MOD, "another mod",
                      r"C:\Users\Other\AppData\Local\factori\mods\word factori archipelago",
                      r"C:\elsewhere\word factori archipelago", None):
            with self.subTest(value=value):
                self.assertFalse(selected_proton_mod({"folder": value}, paths))

    def test_relative_selection_requires_installed_mod_directory(self):
        paths = self.installation()
        paths.mod_folder.rmdir()
        self.assertFalse(selected_proton_mod({"folder": MOD}, paths))

    def test_relative_windows_selection_is_case_insensitive(self):
        paths = self.installation()
        self.assertTrue(selected_proton_mod({"folder": "Mods/Word Factori Archipelago"}, paths))

    def test_unmapped_drive_and_traversal_are_refused(self):
        paths = self.installation()
        for value in (r"Z:\Users\Player\AppData\Local\factori\mods\word factori archipelago",
                      r"C:\Users\Player\..\Other\AppData\Local\factori\mods\word factori archipelago",
                      r"C:\Users\Player\AppData\Local\factori\mods\..\word factori archipelago",
                      r"\\server\share\mod", "mods/../" + MOD):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    resolve_proton_path(value, paths.prefix)
                self.assertFalse(selected_proton_mod({"folder": value}, paths))

    def test_alias_from_another_account_cannot_select_mod(self):
        paths = self.installation()
        alias = paths.prefix / "drive_c/users/Other/AppData/Local/factori/mods/alias"
        alias.parent.mkdir(parents=True)
        try:
            os.symlink(paths.mod_folder, alias, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            if os.name != "nt":
                self.skipTest(f"directory symlinks unavailable: {error}")
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(paths.mod_folder)],
                                    capture_output=True, text=True)
            if result.returncode:
                self.skipTest(f"directory aliases unavailable: {result.stderr}")
        value = r"C:\Users\Other\AppData\Local\factori\mods\alias"
        with self.assertRaises(ValueError):
            resolve_proton_path(value, paths.prefix)
        self.assertFalse(selected_proton_mod({"folder": value}, paths))

    def test_aliased_prefix_is_not_an_explicit_installation(self):
        paths = self.installation()
        alias = self.home / "another-prefix"
        try:
            os.symlink(paths.prefix, alias, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            if os.name != "nt":
                self.skipTest(f"directory symlinks unavailable: {error}")
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(paths.prefix)],
                                    capture_output=True, text=True)
            if result.returncode:
                self.skipTest(f"directory aliases unavailable: {result.stderr}")
        aliased = InstallationPaths(paths.game_data, alias,
                                    alias / "drive_c/users/Player/AppData/Local/factori")
        with self.assertRaises(ValueError):
            validate_installation(aliased)

    def test_aliased_game_directory_is_not_a_mutation_target(self):
        paths = self.installation()
        alias = self.home / "linked-game"
        try:
            os.symlink(paths.game_data.parent, alias, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            if os.name != "nt":
                self.skipTest(f"directory symlinks unavailable: {error}")
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(paths.game_data.parent)],
                                    capture_output=True, text=True)
            if result.returncode:
                self.skipTest(f"directory aliases unavailable: {result.stderr}")
        with self.assertRaises(ValueError):
            validate_installation(InstallationPaths(alias / "data.win", paths.prefix, paths.factori_root))

    def test_deeper_game_and_prefix_ancestors_cannot_be_aliased(self):
        paths = self.installation(self.home / "Real Steam")
        steamapps = paths.game_data.parents[2]
        for name, target, suffix, game_alias in (
            ("common", steamapps / "common", "steamapps/common/Word Factori/data.win", True),
            ("steamapps", steamapps, "steamapps/common/Word Factori/data.win", True),
            ("compatdata", steamapps / "compatdata", f"steamapps/compatdata/{APP}/pfx", False),
            ("app-id", steamapps / "compatdata" / APP, f"steamapps/compatdata/{APP}/pfx", False),
        ):
            with self.subTest(name=name):
                alias_root = self.home / f"Alias {name}"
                alias = alias_root / ("steamapps" if name == "steamapps" else
                                      "steamapps/common" if name == "common" else
                                      "steamapps/compatdata" if name == "compatdata" else
                                      f"steamapps/compatdata/{APP}")
                self.directory_alias(target, alias)
                aliased = alias_root / suffix
                if game_alias:
                    candidate = InstallationPaths(aliased, paths.prefix, paths.factori_root)
                else:
                    candidate = InstallationPaths(paths.game_data, aliased,
                                                  aliased / "drive_c/users/Player/AppData/Local/factori")
                with self.assertRaises(ValueError):
                    validate_installation(candidate)

    def test_discovery_canonicalizes_steam_root_alias(self):
        root = self.home / "Canonical Steam"
        paths = self.installation(root)
        self.manifest(root)
        alias = self.home / "Steam Shortcut"
        self.directory_alias(root, alias)
        self.assertEqual(discover_installations([alias]), [paths])

    def test_discovery_reports_library_limit_instead_of_partial_results(self):
        roots = [self.home / f"Steam {number:02d}" for number in range(65)]
        for root in roots:
            root.mkdir()
        with self.assertRaisesRegex(ValueError, "libraries"):
            discover_installations(roots)

    def test_discovery_reports_user_limit_instead_of_partial_results(self):
        root = self.home / "Steam"
        paths = self.installation(root)
        self.manifest(root)
        users = paths.prefix / "drive_c/users"
        for number in range(32):
            (users / f"Player {number:02d}/AppData/Local/factori").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "users"):
            discover_installations([root])


if __name__ == "__main__":
    unittest.main()
