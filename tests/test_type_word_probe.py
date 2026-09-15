"""Real filesystem safety checks for the development-only native probe."""
import importlib
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
