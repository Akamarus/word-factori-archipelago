import base64
import copy
import hashlib
import json
import subprocess
import sys
import textwrap
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from word_factori.recipe_graph import MACHINE_CAPABILITIES


ROOT = Path(__file__).resolve().parents[1]


class RecipeCheckTests(unittest.TestCase):
    def test_catalog_covers_every_letter_recipe_with_explicit_stable_ids(self):
        from word_factori.recipe_checks import RECIPE_CHECKS

        self.assertEqual(187, len(RECIPE_CHECKS))
        self.assertEqual(
            {"oBend": 24, "oMerger2": 86, "oMerger3": 58, "oMerger4": 19},
            Counter(check.machine for check in RECIPE_CHECKS),
        )
        self.assertTrue(all(len(check.output) == 1 and "A" <= check.output <= "Z" for check in RECIPE_CHECKS))
        self.assertEqual(187, len({check.code for check in RECIPE_CHECKS}))
        self.assertTrue(all(check.code >= 975302000 for check in RECIPE_CHECKS))
        self.assertEqual(187, len({check.name for check in RECIPE_CHECKS}))

    def test_distinct_oriented_bender_discoveries(self):
        from word_factori.recipe_checks import discovered_recipe_codes

        plain = discovered_recipe_codes({"oBend": {"I": "C"}})
        turned = discovered_recipe_codes({"oBend": {"I1": "U"}})
        self.assertEqual(len(plain), 1)
        self.assertEqual(len(turned), 1)
        self.assertFalse(plain & turned)

    def test_merger_preserves_duplicate_inputs_without_confusing_recipes(self):
        from word_factori.recipe_checks import RECIPE_CHECKS, discovered_recipe_codes

        found = discovered_recipe_codes({"oMerger2": {"I I": "V"}})
        expected = {check.code for check in RECIPE_CHECKS if check.machine == "oMerger2" and check.inputs == ("I", "I") and check.output == "V"}
        reversed_input = discovered_recipe_codes({"oMerger2": {"V I": "Y"}})
        self.assertEqual(expected, set(found))
        self.assertEqual(1, len(found))
        self.assertFalse(found & reversed_input)

    def test_builder_uses_native_canonical_aliases_and_sorted_inputs(self):
        from tools.build_recipe_catalog import build_catalog

        payload = {
            "oIFactory": {"I": "I"},
            "aliases": {"(2": ")"},
            "oMerger2": {"I )": "D", "I 3": "__B", "I 0": "E"},
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog = build_catalog(payload, Path(directory) / "catalog.json")
        identities = {(item["machine"], tuple(item["inputs"]), item["output"]) for item in catalog["recipes"]}
        self.assertEqual(
            {("oMerger2", ("(2", "I"), "D"), ("oMerger2", ("3", "I"), "B"), ("oMerger2", ("0", "I"), "E")},
            identities,
        )

    def test_builder_excludes_recipes_that_cannot_fill_the_native_machine(self):
        from tools.build_recipe_catalog import build_catalog

        payload = {
            "oIFactory": {"I": "I"},
            "oMerger3": {"I N": "__M", "I I I": "N"},
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog = build_catalog(payload, Path(directory) / "catalog.json")
        self.assertEqual([("I", "I", "I")], [tuple(item["inputs"]) for item in catalog["recipes"]])

    def test_invalid_arity_recipe_cannot_serve_as_a_reachability_intermediary(self):
        from tools.build_recipe_catalog import build_catalog

        payload = {
            "oIFactory": {"I": "I"},
            "oMerger3": {"I I": "M"},
            "oBend": {"M": "A"},
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog = build_catalog(payload, Path(directory) / "catalog.json")
        downstream = next(item for item in catalog["recipes"] if item["output"] == "A")
        self.assertEqual([], downstream["requirements"])

    def test_unknown_well_formed_recipe_and_output_are_ignored(self):
        from word_factori.recipe_checks import discovered_recipe_codes

        self.assertEqual(frozenset(), discovered_recipe_codes({"oBend": {"NOPE": "C", "I": "?"}}))
        self.assertEqual(frozenset(), discovered_recipe_codes({"futureMachine": {"I": "C"}}))

    def test_malformed_recognized_journal_groups_are_rejected(self):
        from word_factori.recipe_checks import discovered_recipe_codes

        malformed = (
            None,
            [],
            {"oBend": []},
            {"oBend": {1: "C"}},
            {"oBend": {"I": ["C"]}},
        )
        for journal in malformed:
            with self.subTest(journal=journal), self.assertRaises(ValueError):
                discovered_recipe_codes(journal)

    def test_duplicate_observations_are_idempotent(self):
        from word_factori.recipe_checks import discovered_recipe_codes

        journal = {"oBend": {"I": "C"}}
        self.assertEqual(discovered_recipe_codes(journal), discovered_recipe_codes(journal))

    def test_minimal_routes_require_whole_inputs_and_the_own_machine(self):
        from word_factori.recipe_checks import RECIPE_CHECKS

        by_recipe = {(check.machine, check.inputs, check.output): check for check in RECIPE_CHECKS}
        self.assertEqual((frozenset({"Bender Access"}),), by_recipe[("oBend", ("I",), "C")].requirement_options)
        self.assertEqual((frozenset({"Bender Access", "Rotation Access"}),), by_recipe[("oBend", ("I1",), "U")].requirement_options)
        self.assertEqual((frozenset({"Merger2 Access"}),), by_recipe[("oMerger2", ("I", "I"), "V")].requirement_options)
        all_capabilities = frozenset(MACHINE_CAPABILITIES.values())
        for check in RECIPE_CHECKS:
            with self.subTest(check=check.name):
                self.assertTrue(check.requirement_options)
                self.assertTrue(any(option <= all_capabilities for option in check.requirement_options))
                self.assertTrue(all(MACHINE_CAPABILITIES[check.machine] in option for option in check.requirement_options))

    def test_catalog_digest_authenticates_the_packaged_data(self):
        from word_factori.recipe_checks import RECIPE_CATALOG_DIGEST

        self.assertEqual(64, len(RECIPE_CATALOG_DIGEST))
        int(RECIPE_CATALOG_DIGEST, 16)

    def test_valid_digest_does_not_excuse_malformed_recipe_identity(self):
        import word_factori.recipe_checks as recipe_checks

        original = json.loads((ROOT / "word_factori" / "letter_recipes.json").read_text(encoding="utf-8"))

        def bender_with_two_inputs(payload):
            payload["recipes"][0]["inputs"] = ["I", "I"]

        def token_with_embedded_whitespace(payload):
            payload["recipes"][0]["inputs"] = ["I I"]

        def noncanonical_token(payload):
            payload["recipes"][0]["inputs"] = ["I0"]

        def unsorted_merger_inputs(payload):
            entry = next(item for item in payload["recipes"] if item["machine"] == "oMerger2")
            entry["inputs"] = list(reversed(entry["inputs"]))
            if entry["inputs"] == sorted(entry["inputs"]):
                entry["inputs"] = ["Z", "A"]

        def misleading_name(payload):
            payload["recipes"][0]["name"] = "Bender recipe"

        mutations = (
            bender_with_two_inputs,
            token_with_embedded_whitespace,
            noncanonical_token,
            unsorted_merger_inputs,
            misleading_name,
        )
        for mutate in mutations:
            payload = copy.deepcopy(original)
            mutate(payload)
            canonical = json.dumps(payload["recipes"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            payload["digest"] = hashlib.sha256(canonical).hexdigest()
            with tempfile.TemporaryDirectory() as directory:
                catalog_path = Path(directory) / "letter_recipes.json"
                catalog_path.write_text(json.dumps(payload), encoding="utf-8")
                resource = type("Resource", (), {"joinpath": lambda self, name: catalog_path})()
                with self.subTest(mutation=mutate.__name__), patch.object(recipe_checks, "files", return_value=resource):
                    with self.assertRaises(ValueError):
                        recipe_checks._load_catalog()

    def test_builder_reuses_ids_for_unchanged_recipe_identities(self):
        from tools.build_recipe_catalog import build_catalog

        payload = {
            "oIFactory": {"I": "I"},
            "oBend": {"I": "C", "I1": "U"},
            "oMerger2": {"I I": "V"},
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            first = build_catalog(payload, output)
            output.write_text(json.dumps(first), encoding="utf-8")
            changed = {**payload, "oBend": {"H": "A", **payload["oBend"]}}
            second = build_catalog(changed, output)
        first_ids = {(item["machine"], tuple(item["inputs"]), item["output"]): item["code"] for item in first["recipes"]}
        second_ids = {(item["machine"], tuple(item["inputs"]), item["output"]): item["code"] for item in second["recipes"]}
        self.assertEqual(first_ids, {identity: second_ids[identity] for identity in first_ids})

    def test_builder_runs_directly_from_the_project_root(self):
        payload = {"oIFactory": {"I": "I"}, "oBend": {"I": "C"}}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "recipes.data"
            output = Path(directory) / "catalog.json"
            source.write_bytes(base64.b64encode(json.dumps(payload).encode("utf-8")))
            result = subprocess.run(
                [sys.executable, "tools/build_recipe_catalog.py", str(source), str(output)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_recipe_checks_loads_under_archipelago_world_namespace(self):
        script = textwrap.dedent(f"""
            import importlib
            import importlib.util
            import sys
            import types

            package_path = {str(ROOT / 'word_factori')!r}
            worlds = types.ModuleType('worlds')
            worlds.__path__ = []
            spec = importlib.util.spec_from_file_location(
                'worlds.word_factori',
                package_path + '/__init__.py',
                submodule_search_locations=[package_path],
            )
            package = importlib.util.module_from_spec(spec)
            sys.modules['worlds'] = worlds
            sys.modules['worlds.word_factori'] = package
            checks = importlib.import_module('worlds.word_factori.recipe_checks')
            assert len(checks.RECIPE_CHECKS) == 187
        """)
        completed = subprocess.run(
            [sys.executable, "-I", "-c", script],
            cwd=ROOT.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()
