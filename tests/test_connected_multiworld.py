"""Guard the connected acceptance runner against vacuous success and unsafe staging."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


class ConnectedRunnerTests(unittest.TestCase):
    def runner(self):
        spec = importlib.util.find_spec("tools.verify_connected_multiworld")
        self.assertIsNotNone(spec, "Connected multiworld runner is not implemented")
        from tools import verify_connected_multiworld
        return verify_connected_multiworld

    def test_existing_output_is_never_reused_or_overwritten(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "existing"
            destination.mkdir()
            sentinel = destination / "keep.txt"
            sentinel.write_text("user data")
            with self.assertRaises(FileExistsError):
                runner.create_run_directory(destination)
            self.assertEqual("user data", sentinel.read_text())

    def test_staging_never_copies_user_settings_worlds_or_saves(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as temp:
            source, dest = Path(temp) / "source", Path(temp) / "run"
            (source / "worlds" / "generic").mkdir(parents=True)
            (source / "rule_builder").mkdir()
            for name in ("Utils.py", "Generate.py", "Main.py", "MultiServer.py", "CommonClient.py"):
                (source / name).write_text("# fixture core")
            (source / "worlds" / "__init__.py").write_text("# framework")
            (source / "worlds" / "generic" / "Rules.py").write_text("# rules")
            (source / "host.yaml").write_text("password: private")
            (source / "custom_worlds").mkdir()
            (source / "custom_worlds" / "private.apworld").write_text("private")
            (source / "worlds" / "unrelated").mkdir()
            (source / "worlds" / "unrelated" / "__init__.py").write_text("raise RuntimeError()")
            runner.create_run_directory(dest)
            runner.stage_core(source, dest / "ap")
            self.assertTrue((dest / "ap" / "MultiServer.py").exists())
            self.assertTrue((dest / "ap" / "worlds" / "generic" / "Rules.py").exists())
            self.assertFalse((dest / "ap" / "host.yaml").exists())
            self.assertFalse((dest / "ap" / "custom_worlds").exists())
            self.assertFalse((dest / "ap" / "worlds" / "unrelated").exists())

    def test_report_rejects_missing_coverage_even_when_marked_pass(self):
        runner = self.runner()
        with self.assertRaisesRegex(ValueError, "coverage"):
            runner.validate_report({"status": "pass", "players": []})

    def test_report_requires_real_delivery_replay_and_page_observations(self):
        import copy
        runner = self.runner()
        complete = {"status": "pass", "coverage": ["offline_completion", "client_restart",
                    "duplicate_checks", "item_replay", "tracker_reconstruction", "page_gates",
                    "victory", "cross_player_delivery"],
                    "players": [{"checked": 33, "expected": 33, "goal": True},
                                {"checked": 230, "expected": 230, "goal": True}],
                    "cross_player_deliveries": 5, "tracker_comparisons": 20,
                    "page_gate_observations": 10, "replay_rounds": 9}
        runner.validate_report(complete)
        for field in ("cross_player_deliveries", "tracker_comparisons", "page_gate_observations", "replay_rounds"):
            with self.subTest(field=field):
                invalid = copy.deepcopy(complete)
                invalid[field] = 0
                with self.assertRaisesRegex(ValueError, "coverage"):
                    runner.validate_report(invalid)
        for field, value in (("checked", 229), ("goal", False), ("expected", 0)):
            with self.subTest(field=field):
                invalid = copy.deepcopy(complete)
                invalid["players"][1][field] = value
                with self.assertRaisesRegex(ValueError, "coverage"):
                    runner.validate_report(invalid)

    def test_wait_reports_timeout_instead_of_hanging(self):
        import asyncio
        runner = self.runner()
        with self.assertRaisesRegex(TimeoutError, "never connected"):
            asyncio.run(runner.wait_until(lambda: False, "never connected", timeout=.01))

    @unittest.skipUnless(os.environ.get("WF_AP_SOURCE"), "opt-in real AP 0.6.7 connected test")
    def test_real_two_client_room_finishes_without_cheats(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "run"
            command = [sys.executable, str(Path(runner.__file__)),
                       "--ap-source", os.environ["WF_AP_SOURCE"], "--output", str(output)]
            if os.environ.get("WF_AP_DEPS"):
                command += ["--dependency-path", os.environ["WF_AP_DEPS"]]
            result = subprocess.run(command, capture_output=True, text=True, timeout=240)
            log = (output / "worker.log").read_text(encoding="utf-8", errors="replace") if (output / "worker.log").exists() else ""
            self.assertEqual(0, result.returncode, result.stdout + result.stderr + log[-8000:])
            report = json.loads((output / "report.json").read_text())
            self.assertEqual("pass", report["status"])
            self.assertEqual("0.6.7", report["ap_version"])
            self.assertEqual([33, 230], [p["checked"] for p in report["players"]])
            self.assertTrue(all(p["goal"] for p in report["players"]))
            self.assertGreater(report["cross_player_deliveries"], 0)
            self.assertGreater(report["tracker_comparisons"], 2)

    @unittest.skipUnless(os.environ.get("WF_AP_SOURCE"), "opt-in real AP 0.6.7 fault test")
    def test_connected_runner_catches_premature_victory(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mutant = root / "word_factori.apworld"
            with zipfile.ZipFile(runner.ROOT / "word_factori.apworld") as source, zipfile.ZipFile(mutant, "w") as target:
                for entry in source.infolist():
                    data = source.read(entry)
                    if entry.filename == "word_factori/client.py":
                        old = b"goal_reached(goal, target, combined, locations)"
                        self.assertEqual(1, data.count(old), "update the fault injection for this client version")
                        data = data.replace(old, b"True  # acceptance fault: victory without completions")
                    target.writestr(entry, data)
            output = root / "run"
            command = [sys.executable, str(Path(runner.__file__)), "--ap-source", os.environ["WF_AP_SOURCE"],
                       "--apworld", str(mutant), "--output", str(output)]
            if os.environ.get("WF_AP_DEPS"):
                command += ["--dependency-path", os.environ["WF_AP_DEPS"]]
            result = subprocess.run(command, capture_output=True, text=True, timeout=240)
            self.assertNotEqual(0, result.returncode, "runner accepted a client that goals before playing")
            report = json.loads((output / "report.json").read_text())
            self.assertEqual("fail", report["status"])
            self.assertIn("premature victory", report["error"])


if __name__ == "__main__":
    unittest.main()
