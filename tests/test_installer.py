from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.ps1"
WORLD_SOURCE = ROOT / "word_factori.apworld"
MOD_SOURCE = ROOT / "game_mod" / "word factori archipelago"


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.program_data = root / "ProgramData"
        self.local_app_data = root / "LocalAppData"
        self.world_target = self.program_data / "Archipelago" / "custom_worlds" / "word_factori.apworld"
        self.mod_target = self.local_app_data / "factori" / "mods" / "word factori archipelago"

    def run_installer(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        executable = shutil.which("powershell.exe")
        if executable is None:
            self.skipTest("Windows PowerShell is required for installer integration tests")
        environment = os.environ.copy()
        environment["ProgramData"] = str(self.program_data)
        environment["LOCALAPPDATA"] = str(self.local_app_data)
        return subprocess.run(
            [
                executable, "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(INSTALLER), *arguments,
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def assert_installed_copy_matches_sources(self) -> None:
        self.assertEqual(WORLD_SOURCE.read_bytes(), self.world_target.read_bytes())
        for source in MOD_SOURCE.glob("*.json"):
            self.assertEqual(source.read_bytes(), (self.mod_target / source.name).read_bytes())

    def test_clean_install_copies_only_the_integration_payload(self):
        completed = self.run_installer()

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assert_installed_copy_matches_sources()

    def test_existing_install_refuses_update_without_force(self):
        self.assertEqual(0, self.run_installer().returncode)

        completed = self.run_installer()

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("already installed", completed.stderr)
        self.assert_installed_copy_matches_sources()

    def test_force_replaces_an_existing_install_transactionally(self):
        self.assertEqual(0, self.run_installer().returncode)
        self.world_target.write_bytes(b"not an apworld")
        (self.mod_target / "levels.json").write_text("[]", encoding="utf-8")

        completed = self.run_installer("-Force")

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assert_installed_copy_matches_sources()

    def test_uninstall_removes_only_owned_targets_and_preserves_neighbors(self):
        self.assertEqual(0, self.run_installer().returncode)
        neighboring_world = self.world_target.parent / "neighbor.apworld"
        neighboring_world.write_bytes(b"neighbor")
        neighboring_mod = self.mod_target.parent / "another mod" / "keep.txt"
        neighboring_mod.parent.mkdir()
        neighboring_mod.write_text("keep", encoding="utf-8")

        completed = self.run_installer("-Uninstall")

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertFalse(self.world_target.exists())
        self.assertFalse(self.mod_target.exists())
        self.assertEqual(b"neighbor", neighboring_world.read_bytes())
        self.assertEqual("keep", neighboring_mod.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
