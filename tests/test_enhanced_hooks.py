import tempfile
import unittest
from pathlib import Path

from tools.build_enhanced_probe import build_probe
from tools.enhanced_hooks import insert_function_guard, transform_sources, verify_original


class EnhancedHookTests(unittest.TestCase):
    # Integration-authored minimal fixtures, not extracted game source.
    def sources(self):
        return {
            "gml_Object_oLevelButton_Create_0": "return (level_index == 0 || native_unlock()) && secret_guard();",
            "gml_GlobalScript_MenuFuncs": "function getPageUnlockThresh(arg0) { return native_threshold(arg0); }",
            "gml_GlobalScript_LevelFuncs": "function get_level_module_counts(arg0) { return native_limits(arg0); }\n"
                "function get_current_module_count(arg0) { if (current_level_mode != UnknownEnum.Value_1 || missing()) return -1; return native_count(); }",
            "gml_GlobalScript_Building": "\n".join("static " + name + " = function() { native_body(); }" for name in ("consume", "getRecipe", "produce", "getTicksTillProduce")),
            "gml_GlobalScript_Misc": "function getModuleRecipe(arg0, arg1) { return native_recipe(); }",
        }

    def test_unknown_binary_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Unsupported game hash"):
            verify_original(b"unrecognized game data")

    def test_probe_refuses_unknown_input_before_creating_or_invoking_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "original.win"
            original.write_bytes(b"unknown data")
            output = root / "new" / "patched.win"
            with self.assertRaisesRegex(ValueError, "Unsupported game hash"):
                build_probe(root / "no-cli.exe", original, output)
            self.assertEqual(b"unknown data", original.read_bytes())
            self.assertFalse(output.parent.exists())

    def test_probe_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "patched.win"
            output.write_bytes(b"keep this")
            with self.assertRaisesRegex(ValueError, "already exists"):
                build_probe(root / "no-cli.exe", root / "no-input.win", output)
            self.assertEqual(b"keep this", output.read_bytes())

    def test_only_target_hook_is_changed_and_native_checks_survive(self):
        source = self.sources()
        output = transform_sources(source, "function wf_ap_context() { return undefined; }")
        self.assertEqual(
            "return (wf_ap_enabled() || level_index == 0 || native_unlock()) && secret_guard();",
            output["gml_Object_oLevelButton_Create_0"],
        )
        self.assertEqual(self.sources(), source)
        self.assertEqual(
            "function getPageUnlockThresh(arg0) {\n    if (wf_ap_enabled()) return 4; return native_threshold(arg0); }",
            output["gml_GlobalScript_MenuFuncs"],
        )

    def test_missing_ambiguous_or_repeated_hooks_fail_closed(self):
        for source in ("function different() {}", "function target() {} function target() {}"):
            with self.assertRaises(ValueError):
                insert_function_guard(source, "target", "return 4;")
        patched = transform_sources(self.sources(), "function wf_ap_context() {}")
        with self.assertRaisesRegex(ValueError, "already present"):
            transform_sources(patched, "")

    def test_every_enforcement_surface_requires_exactly_one_native_occurrence(self):
        targets = (
            ("gml_GlobalScript_LevelFuncs", "function get_level_module_counts"),
            ("gml_GlobalScript_LevelFuncs", "function get_current_module_count"),
            ("gml_GlobalScript_LevelFuncs", "current_level_mode != UnknownEnum.Value_1 ||"),
            ("gml_GlobalScript_Building", "static consume = function"),
            ("gml_GlobalScript_Building", "static getRecipe = function"),
            ("gml_GlobalScript_Building", "static produce = function"),
            ("gml_GlobalScript_Building", "static getTicksTillProduce = function"),
            ("gml_GlobalScript_Misc", "function getModuleRecipe"),
        )
        for entry, target in targets:
            with self.subTest(target=target):
                missing = self.sources()
                missing[entry] = missing[entry].replace(target, "renamed_native_surface")
                with self.assertRaises(ValueError): transform_sources(missing, "// helpers")
                duplicate = self.sources()
                duplicate[entry] += "\n" + duplicate[entry]
                with self.assertRaises(ValueError): transform_sources(duplicate, "// helpers")


if __name__ == "__main__":
    unittest.main()
