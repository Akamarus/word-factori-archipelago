"""Run the shipped PowerShell against isolated synthetic game bytes only."""
import gzip
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.enhanced_delta import build_delta


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = b"controlled original game fixture " * 400
PATCHED = ORIGINAL[:4096] + b"native integration fixture" + ORIGINAL[5000:]


class InstallerFixture(unittest.TestCase):
    def setUp(self):
        if not shutil.which("powershell.exe"):
            self.skipTest("Windows PowerShell is required")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.distribution = self.root / "distribution"
        self.distribution.mkdir()
        for name in ("install.ps1", "word_factori.apworld", "Install Word Factori Archipelago.cmd", "Restore Original Game.cmd"):
            shutil.copy2(ROOT / name, self.distribution / name)
        shutil.copytree(ROOT / "game_mod", self.distribution / "game_mod")
        (self.distribution / "tools").mkdir()
        script = (ROOT / "tools/install_enhanced.ps1").read_text(encoding="utf-8-sig")
        # Test-only copies replace exact supported hashes; production has no bypass.
        for field, data in (("originalHash", ORIGINAL), ("patchedHash", PATCHED)):
            script, count = re.subn(rf"(\${field} = ')[0-9a-f]{{64}}(')",
                                   lambda match: match[1] + hashlib.sha256(data).hexdigest() + match[2], script)
            self.assertEqual(1, count)
        (self.distribution / "tools/install_enhanced.ps1").write_text(script, encoding="utf-8")
        self.patch = self.distribution / "tools/enhanced.patch.gz"
        self.patch.write_bytes(gzip.compress(json.dumps(build_delta(ORIGINAL, PATCHED)).encode()))
        self.game_dir = self.root / "game"
        self.game_dir.mkdir()
        self.game = self.game_dir / "data.win"
        self.game.write_bytes(ORIGINAL)
        self.backup = self.game_dir / "data.wf-ap-original.win"
        self.program_data = self.root / "ProgramData"
        self.local_app_data = self.root / "LocalAppData"
        self.world_target = self.program_data / "Archipelago/custom_worlds/word_factori.apworld"
        self.mod_target = self.local_app_data / "factori/mods/word factori archipelago"
        self.receipt = self.mod_target / "archipelago_enhanced_install.json"

    def run_script(self, relative, *args):
        env = os.environ.copy()
        env.update(ProgramData=str(self.program_data), LOCALAPPDATA=str(self.local_app_data))
        return subprocess.run([shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive",
                               "-ExecutionPolicy", "Bypass", "-File", str(self.distribution / relative),
                               "-GameData", str(self.game), *map(str, args)], cwd=self.distribution,
                              env=env, capture_output=True, text=True, timeout=45)

    def install(self, *args):
        return self.run_script("install.ps1", *args)

    def install_with_game_starting_during_preflight(self):
        # Only the volatile process query is controlled; file validation and writes are real.
        script = """
$ErrorActionPreference = 'Stop'
$global:processChecks = 0
function Get-Process {
    param($Name, $ErrorAction)
    $global:processChecks++
    if ($global:processChecks -ge 2) { [pscustomobject]@{ ProcessName = 'word factori' } }
}
& './install.ps1' -GameData './data.win'
"""
        # Relative paths resolve inside this isolated distribution.
        shutil.copy2(self.game, self.distribution / "data.win")
        env = os.environ.copy()
        env.update(ProgramData=str(self.program_data), LOCALAPPDATA=str(self.local_app_data))
        return subprocess.run([shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive",
                               "-ExecutionPolicy", "Bypass", "-Command", script],
                              cwd=self.distribution, env=env, capture_output=True, text=True, timeout=45)

    def run_cmd(self, name):
        env = os.environ.copy()
        env.update(ProgramData=str(self.program_data), LOCALAPPDATA=str(self.local_app_data))
        command = f'"{os.environ["COMSPEC"]}" /d /s /c ""{self.distribution / name}" -GameData "{self.game}" < nul"'
        return subprocess.run(command, cwd=self.root, env=env, capture_output=True, text=True, timeout=45)

    @contextmanager
    def running_game_process(self):
        """An isolated harmless process with the game's executable name."""
        executable = self.root / "word factori.exe"
        shutil.copy2(os.environ["COMSPEC"], executable)
        process = subprocess.Popen([str(executable), "/d", "/c", "echo ready & set /p fixture_wait="],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            self.assertEqual("ready", process.stdout.readline().strip())
            yield
        finally:
            process.communicate(input="\n", timeout=10)

    def native(self, *args):
        return self.run_script("tools/install_enhanced.ps1", "-ModFolder", self.mod_target, *args)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() if p.is_file() else None
                for p in self.root.rglob("*") if self.distribution not in p.parents and p != self.distribution}

    def assert_success(self, result):
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def assert_installed(self):
        self.assertEqual((self.distribution / "word_factori.apworld").read_bytes(), self.world_target.read_bytes())
        for source in (self.distribution / "game_mod/word factori archipelago").glob("*.json"):
            self.assertEqual(source.read_bytes(), (self.mod_target / source.name).read_bytes())
        self.assertEqual(PATCHED, self.game.read_bytes())
        self.assertEqual(ORIGINAL, self.backup.read_bytes())
        # PowerShell expands Windows 8.3 aliases (for example RUNNER~1).
        # The receipt must identify the same absolute file, not the same spelling.
        recorded_game = Path(json.loads(self.receipt.read_text())["game_data"])
        self.assertTrue(recorded_game.is_absolute())
        self.assertTrue(self.game.samefile(recorded_game))
