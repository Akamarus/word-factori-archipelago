import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows installer")
class InstallerSafetyTests(unittest.TestCase):
    def test_windows_powershell_refuses_unknown_game_without_any_writes(self):
        script = Path(__file__).resolve().parents[1] / "tools/install_enhanced.ps1"
        for restore in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                game = root / "data.win"
                game.write_bytes(b"unknown game build")
                mod = root / "mod"
                mod.mkdir()
                command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-GameData", str(game), "-ModFolder", str(mod)]
                if restore: command.append("-Restore")
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("unknown build" if restore else "Unsupported", result.stdout + result.stderr)
                self.assertEqual(b"unknown game build", game.read_bytes())
                self.assertEqual({"data.win", "mod"}, {p.name for p in root.iterdir()})
                self.assertEqual([], list(mod.iterdir()))
