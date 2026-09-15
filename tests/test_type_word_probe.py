"""Real filesystem safety checks for the development-only native probe."""
import importlib
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class TypeWordProbePaths(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.cli = self.tmp / "cli.exe"
        self.cli.write_bytes(b"not executed")
        self.runtime = self.tmp / "runtime"
        self.runtime.mkdir()
        (self.runtime / "discovered-game.exe").write_bytes(b"not executed")
        self.original = self.runtime / "original.win"
        self.original.write_bytes(b"unsupported original")
        self.scratch = self.tmp / "scratch"
        self.scratch.mkdir()
        self.output = self.scratch / "fresh"
        try:
            self.probe = importlib.import_module("tools.run_type_word_native_probe")
        except ModuleNotFoundError:
            self.fail("native probe runner is not implemented")

    def validate(self, output=None):
        return self.probe.validate_probe_paths(self.cli, self.original, self.runtime,
                                               output or self.output)

    def test_new_scratch_output_is_valid_without_creating_it(self):
        self.validate()
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.validate()
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_runtime_descendant_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(self.runtime / "probe")

    def test_original_parent_descendant_is_rejected(self):
        separate = self.tmp / "originals"
        separate.mkdir()
        self.original = separate / "original.win"
        self.original.write_bytes(b"invalid")
        with self.assertRaises(ValueError):
            self.validate(separate / "probe")

    def test_output_parent_must_exist(self):
        with self.assertRaises(ValueError):
            self.validate(self.scratch / "missing" / "probe")

    def test_output_inside_another_repository_is_rejected_without_writes(self):
        checkout = self.tmp / "another-checkout"
        (checkout / ".git").mkdir(parents=True)
        nested = checkout / "nested"
        nested.mkdir()
        destination = nested / "new-probe"
        with self.assertRaises(ValueError):
            self.validate(destination)
        self.assertFalse(destination.exists())
        self.assertTrue((checkout / ".git").is_dir())

    def test_output_inside_gitfile_worktree_is_rejected_without_writes(self):
        checkout = self.tmp / "another-worktree"
        checkout.mkdir()
        gitfile = checkout / ".git"
        gitfile.write_text("gitdir: ../main/.git/worktrees/another-worktree\n", encoding="utf-8")
        nested = checkout / "nested"
        nested.mkdir()
        destination = nested / "new-probe"
        with self.assertRaises(ValueError):
            self.validate(destination)
        self.assertFalse(destination.exists())
        self.assertEqual(gitfile.read_text(encoding="utf-8"),
                         "gitdir: ../main/.git/worktrees/another-worktree\n")

    def test_missing_input_is_rejected(self):
        self.cli = self.tmp / "missing.exe"
        with self.assertRaises(ValueError):
            self.validate()

    def test_symlink_ancestor_is_rejected(self):
        link = self.tmp / "alias"
        try:
            link.symlink_to(self.scratch, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(ValueError):
            self.validate(link / "probe")

    def test_unsupported_original_fails_before_writes_or_subprocess(self):
        with patch("subprocess.run", side_effect=AssertionError("subprocess reached")):
            with self.assertRaises(ValueError):
                self.probe.build_probe(self.cli, self.original, self.runtime, self.output)
        self.assertFalse(self.output.exists())

    def test_executable_is_discovered_and_ambiguity_rejected(self):
        self.assertEqual(self.probe.discover_executable(self.runtime).name, "discovered-game.exe")
        (self.runtime / "ambiguous.exe").write_bytes(b"not executed")
        with self.assertRaises(ValueError):
            self.probe.discover_executable(self.runtime)

    def test_cli_timeout_preserves_captured_stdout_and_stderr(self):
        fixture_hash = hashlib.sha256(self.original.read_bytes()).hexdigest()
        timeout = subprocess.TimeoutExpired([str(self.cli), "dump"], 180,
                                            output=b"partial native dump\n",
                                            stderr=b"native warning\n")
        with patch("tools.enhanced_hooks.ORIGINAL_SHA256", fixture_hash), \
                patch("subprocess.run", side_effect=timeout):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.probe.build_probe(self.cli, self.original, self.runtime, self.output)
        log = self.output / "build.log"
        self.assertTrue(log.is_file(), "timeout discarded native CLI diagnostics")
        self.assertIn("partial native dump", log.read_text(encoding="utf-8"))
        self.assertIn("native warning", log.read_text(encoding="utf-8"))

    def test_function_extraction_preserves_nested_body_and_rejects_missing(self):
        extract = getattr(self.probe, "extract_function", None)
        self.assertIsNotNone(extract, "native function extraction missing")
        source = 'before();\nfunction wanted(a) { if (a) { return "}"; } }\nafter();'
        self.assertEqual(extract(source, "wanted"), 'function wanted(a) { if (a) { return "}"; } }')
        with self.assertRaises(ValueError):
            extract(source, "missing")

    def test_result_transport_rejects_stale_nonce(self):
        parser = getattr(self.probe, "parse_native_result", None)
        self.assertIsNotNone(parser, "nonce-bound result parser missing")
        with self.assertRaises(ValueError):
            parser('WF_TYPEWORD_RESULT:old:{"schema":1}', "new")

    def test_result_transport_returns_observed_failure_without_inventing_tests(self):
        parser = getattr(self.probe, "parse_native_result", None)
        self.assertIsNotNone(parser, "nonce-bound result parser missing")
        result = parser('noise\nWF_TYPEWORD_RESULT:new:{"schema":1,"tests":[],"failure":"native error"}\n', "new")
        self.assertEqual(result, {"schema":1,"tests":[],"failure":"native error"})

    def test_enforcement_cli_dispatches_and_keeps_original_verification(self):
        parser = getattr(self.probe, "argument_parser", None)
        self.assertIsNotNone(parser, "enforcement CLI dispatch missing")
        args = parser().parse_args(["--cli", str(self.cli), "--original", str(self.original),
                                   "--runtime", str(self.runtime), "--output", str(self.output), "--enforcement"])
        self.assertTrue(args.enforcement)
        with patch("subprocess.run", side_effect=AssertionError("subprocess reached")):
            with self.assertRaises(ValueError):
                self.probe.build_probe(args.cli, args.original, args.runtime, args.output, enforcement=True)
        self.assertFalse(self.output.exists())

    def enforcement_sources(self):
        return {
            "gml_GlobalScript_LevelFuncs": "function get_level_module_counts(arg0) { return original_counts(); }\n"
                "function get_current_module_count(arg0) { if (current_level_mode != UnknownEnum.Value_1 || missing()) return -1; return native_count(); }\nfunction untouched() { return 9; }",
            "gml_GlobalScript_Building": "\n".join("static " + name + " = function(" + args + ")\n{\n    native_" + name + "();\n};"
                for name, args in [("consume", ""), ("getRecipe", "arg0, arg1 = false"),
                                   ("produce", "arg0 = undefined"), ("getTicksTillProduce", "arg0")]),
            "gml_GlobalScript_Misc": "function getModuleRecipe(arg0, arg1, arg2, arg3 = false, arg4 = true) { return native_recipe(); }",
            "unrelated": "function unrelated() { return original(); }",
        }

    def test_enforcement_transform_preserves_native_bodies_and_unrelated_entries(self):
        transform = getattr(self.probe, "transform_enforcement", None)
        self.assertIsNotNone(transform, "enforcement source transform missing")
        source = self.enforcement_sources()
        output = transform(source, "// authored helper")
        self.assertEqual(source, self.enforcement_sources())
        self.assertEqual(output["unrelated"], source["unrelated"])
        self.assertIn("function untouched() { return 9; }", output["gml_GlobalScript_LevelFuncs"])
        self.assertIn("if ((!wf_tw_active() && current_level_mode != UnknownEnum.Value_1) || missing())", output["gml_GlobalScript_LevelFuncs"])
        self.assertIn("if (!wf_tw_allowed(module, tag)) return new Letter(\"?\");\n    native_getRecipe();", output["gml_GlobalScript_Building"])
        self.assertIn("if (!wf_tw_allowed(module, tag)) { queued_produce_letter = undefined; return undefined; }\n    native_produce();", output["gml_GlobalScript_Building"])

    def test_enforcement_transform_rejects_missing_duplicate_and_already_hooked_sources(self):
        transform = getattr(self.probe, "transform_enforcement", None)
        self.assertIsNotNone(transform, "enforcement source transform missing")
        for mutation in ("missing", "duplicate", "already"):
            source = self.enforcement_sources()
            if mutation == "missing":
                source["gml_GlobalScript_Building"] = ""
            elif mutation == "duplicate":
                source["gml_GlobalScript_Misc"] *= 2
            else:
                source["gml_GlobalScript_LevelFuncs"] += "function wf_tw_active() {}"
            with self.assertRaises(ValueError):
                transform(source, "// helper")

    def test_enforcement_result_cannot_pass_with_missing_or_false_gate(self):
        validate = getattr(self.probe, "validate_native_assertions", None)
        self.assertIsNotNone(validate, "enforcement result validation missing")
        for gate in (None, False, "true"):
            with self.assertRaises(RuntimeError):
                validate({"tests": [{"passed": True}], "enforcement_supported": gate}, enforcement=True)
        validate({"tests": [{"passed": True}], "enforcement_supported": True}, enforcement=True)
        validate({"tests": [{"passed": True}]}, enforcement=False)


if __name__ == "__main__":
    unittest.main()
