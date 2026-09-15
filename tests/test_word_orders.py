import copy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from word_factori.data import LOCATION_NAME_TO_ID
from word_factori.recipe_checks import RECIPE_CATALOG_DIGEST, RECIPE_CHECKS
from word_factori.recipe_graph import RecipeGraph, physical_recipe_payload
from word_factori.word_orders import (
    ALPHABET_LOGIC_DIGEST,
    ALPHABET_LOGIC_VERSION,
    FIRST_WORD_ORDER_CODE,
    WORD_ORDER_NAME_TO_ID,
    WordOrder,
    checks_contract_digest,
    choose_word_orders,
    missing_machine_options,
    normalize_word_list,
    orders_from_slot_data,
    orders_slot_data,
    word_requirement_options,
)
import word_factori.word_orders as word_orders_module


ROOT = Path(__file__).resolve().parents[1]


class WordListTests(unittest.TestCase):
    def test_normalization_is_ascii_only_bounded_deduplicated_and_sorted(self):
        self.assertEqual(
            normalize_word_list([" jack ", "JACK", "ISLAND", "aa", "abcdefghijkl"]),
            ("AA", "ABCDEFGHIJKL", "ISLAND", "JACK"),
        )
        for invalid in (["I"], ["ABCDEFGHIJKLM"], ["TWO WORDS"], ["WORD2"], ["straße"], [3]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_word_list(invalid)

    def test_raw_entry_limit_is_checked_before_deduplication(self):
        with self.assertRaises(ValueError):
            normalize_word_list(["JACK"] * 201)

    def test_non_list_like_inputs_are_rejected(self):
        for invalid in (None, "JACK", b"JACK", {"JACK": True}, 12):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_word_list(invalid)

    def test_selection_is_deterministic_after_normalization(self):
        first = choose_word_orders(
            ["charlie", " alpha ", "BRAVO", "ALPHA"], 2, random.Random(1234)
        )
        second = choose_word_orders(
            ["BRAVO", "CHARLIE", "alpha"], 2, random.Random(1234)
        )
        self.assertEqual(("BRAVO", "ALPHA"), tuple(order.word for order in first))
        self.assertEqual(first, second)
        self.assertEqual((1, 2), tuple(order.number for order in first))

    def test_selection_rejects_bad_counts_and_insufficient_distinct_words(self):
        for count in (True, False, 0, 21, 1.0, "1"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                choose_word_orders(["JACK"], count, random.Random(1))
        with self.assertRaises(ValueError):
            choose_word_orders(["JACK", "jack"], 2, random.Random(1))


class AlphabetRequirementTests(unittest.TestCase):
    def test_starting_i_and_alternate_routes_are_preserved(self):
        self.assertEqual((frozenset(),), word_requirement_options("II"))
        self.assertEqual(
            (
                frozenset({"Merger2 Access", "Rotation Access"}),
                frozenset({"Bender Access", "Merger2 Access", "Reflection Access"}),
            ),
            word_requirement_options("JACK"),
        )

    def test_missing_options_subtract_owned_families_without_quantity_claims(self):
        self.assertEqual(
            (
                frozenset({"Merger2 Access", "Rotation Access"}),
                frozenset({"Merger2 Access", "Reflection Access"}),
            ),
            missing_machine_options("JACK", {"Bender Access"}),
        )
        self.assertEqual((frozenset(),), missing_machine_options("II", ()))
        with self.assertRaises(ValueError):
            missing_machine_options("JACK", {"Future Machine"})

    def test_packaged_catalog_has_expected_independent_evidence_digest(self):
        self.assertEqual(1, ALPHABET_LOGIC_VERSION)
        self.assertEqual(
            "f6365423fb5a75a61ae42d9b0fe00d1c1051c7335236e4ef59d33fb64ac8d397",
            ALPHABET_LOGIC_DIGEST,
        )

    def test_shared_physical_filter_excludes_wrong_arity_intermediates(self):
        payload = {
            "oIFactory": {"I": "I"},
            "oMerger3": {"I I": "M", "I I I": "N"},
            "oBend": {"M": "A", "N": "C"},
        }
        filtered = physical_recipe_payload(payload)
        self.assertEqual({"I I I": "N"}, filtered["oMerger3"])
        reachable = RecipeGraph.from_payload(filtered).reachable(
            {"Merger3 Access", "Bender Access"}
        )
        self.assertNotIn("A", reachable)
        self.assertIn("C", reachable)

    def test_catalog_validation_rejects_bad_capabilities_minimality_and_digest(self):
        original = json.loads(
            (ROOT / "word_factori" / "data" / "alphabet_requirements.json").read_text(
                encoding="utf-8"
            )
        )

        def replace_capability(payload):
            payload["alphabet"]["A"][0][0] = "Future Machine"

        def add_nonminimal_route(payload):
            payload["alphabet"]["I"].append(["Bender Access"])

        for mutate in (replace_capability, add_nonminimal_route):
            payload = copy.deepcopy(original)
            mutate(payload)
            canonical = json.dumps(
                payload["alphabet"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            payload["digest"] = hashlib.sha256(canonical).hexdigest()
            with tempfile.TemporaryDirectory() as directory:
                catalog_path = Path(directory) / "alphabet_requirements.json"
                catalog_path.write_text(json.dumps(payload), encoding="utf-8")
                resource = type(
                    "Resource", (), {"joinpath": lambda self, name: catalog_path}
                )()
                with self.subTest(mutation=mutate.__name__), patch.object(
                    word_orders_module, "files", return_value=resource
                ):
                    with self.assertRaises(ValueError):
                        word_orders_module._load_alphabet_catalog()

        bad_digest = copy.deepcopy(original)
        bad_digest["digest"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "alphabet_requirements.json"
            catalog_path.write_text(json.dumps(bad_digest), encoding="utf-8")
            resource = type(
                "Resource", (), {"joinpath": lambda self, name: catalog_path}
            )()
            with patch.object(word_orders_module, "files", return_value=resource):
                with self.assertRaises(ValueError):
                    word_orders_module._load_alphabet_catalog()

    def test_catalog_loads_from_a_zipped_archipelago_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "test.apworld"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("worlds/__init__.py", "")
                package.writestr("worlds/word_factori/__init__.py", "")
                for relative in ("recipe_graph.py", "word_orders.py"):
                    package.write(
                        ROOT / "word_factori" / relative,
                        f"worlds/word_factori/{relative}",
                    )
                package.write(
                    ROOT / "word_factori" / "data" / "alphabet_requirements.json",
                    "worlds/word_factori/data/alphabet_requirements.json",
                )
            script = (
                "import sys; "
                f"sys.path.insert(0, {str(archive)!r}); "
                "from worlds.word_factori.word_orders import ALPHABET_LOGIC_DIGEST; "
                f"assert ALPHABET_LOGIC_DIGEST == {ALPHABET_LOGIC_DIGEST!r}"
            )
            completed = subprocess.run(
                [sys.executable, "-I", "-c", script],
                cwd=ROOT.parent,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(0, completed.returncode, completed.stderr)


class WordOrderContractTests(unittest.TestCase):
    def setUp(self):
        self.orders = (WordOrder(1, "JACK"), WordOrder(2, "ISLAND"))
        self.enabled = orders_slot_data(self.orders)

    def test_static_order_identity_and_ranges_do_not_collide(self):
        self.assertEqual(975303000, FIRST_WORD_ORDER_CODE)
        self.assertEqual(FIRST_WORD_ORDER_CODE, self.orders[0].code)
        self.assertEqual("Word Order 01", self.orders[0].name)
        self.assertEqual(20, len(WORD_ORDER_NAME_TO_ID))
        self.assertEqual(975303019, WORD_ORDER_NAME_TO_ID["Word Order 20"])
        order_ids = set(WORD_ORDER_NAME_TO_ID.values())
        self.assertFalse(order_ids & set(LOCATION_NAME_TO_ID.values()))
        self.assertFalse(order_ids & {check.code for check in RECIPE_CHECKS})
        self.assertFalse(set(WORD_ORDER_NAME_TO_ID) & set(LOCATION_NAME_TO_ID))
        self.assertFalse(set(WORD_ORDER_NAME_TO_ID) & {check.name for check in RECIPE_CHECKS})
        self.assertEqual(word_requirement_options("JACK"), self.orders[0].requirements)
        with self.assertRaises(FrozenInstanceError):
            self.orders[0].word = "ISLAND"

    def test_enabled_contract_round_trips_authoritative_order_metadata(self):
        self.assertEqual(
            {
                "type_a_word_checks": True,
                "word_orders": [
                    {"id": 975303000, "name": "Word Order 01", "word": "JACK"},
                    {"id": 975303001, "name": "Word Order 02", "word": "ISLAND"},
                ],
                "alphabet_logic_version": 1,
                "alphabet_logic_digest": ALPHABET_LOGIC_DIGEST,
            },
            self.enabled,
        )
        self.assertEqual(self.orders, orders_from_slot_data({"goal": 1, **self.enabled}))
        self.assertEqual({"type_a_word_checks": False}, orders_slot_data(()))

    def test_old_or_explicitly_disabled_contract_is_off_without_metadata(self):
        self.assertEqual((), orders_from_slot_data({"goal": 1}))
        self.assertEqual((), orders_from_slot_data({"type_a_word_checks": False}))
        for field in ("word_orders", "alphabet_logic_version", "alphabet_logic_digest"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                orders_from_slot_data({"type_a_word_checks": False, field: self.enabled[field]})

    def test_enabled_contract_rejects_bad_flags_fields_and_targets(self):
        malformed = []
        for value in (1, "true", None):
            malformed.append({**self.enabled, "type_a_word_checks": value})
        for field in ("word_orders", "alphabet_logic_version", "alphabet_logic_digest"):
            candidate = copy.deepcopy(self.enabled)
            del candidate[field]
            malformed.append(candidate)
        malformed.append({**self.enabled, "alphabet_logic_version": True})
        malformed.append({**self.enabled, "alphabet_logic_version": 2})
        malformed.append({**self.enabled, "alphabet_logic_digest": "0" * 64})
        for candidate in malformed:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                orders_from_slot_data(candidate)

    def test_enabled_contract_rejects_bad_ids_names_order_and_duplicates(self):
        mutations = []
        for field, value in (("id", 975303009), ("id", True), ("name", "Word Order 02"), ("word", "jack")):
            candidate = copy.deepcopy(self.enabled)
            candidate["word_orders"][0][field] = value
            mutations.append(candidate)
        duplicate = copy.deepcopy(self.enabled)
        duplicate["word_orders"][1]["word"] = "JACK"
        mutations.append(duplicate)
        reversed_orders = copy.deepcopy(self.enabled)
        reversed_orders["word_orders"].reverse()
        mutations.append(reversed_orders)
        empty = copy.deepcopy(self.enabled)
        empty["word_orders"] = []
        mutations.append(empty)
        extra = copy.deepcopy(self.enabled)
        extra["word_orders"][0]["extra"] = 1
        mutations.append(extra)
        for candidate in mutations:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                orders_from_slot_data(candidate)

    def test_contract_digest_uses_only_validated_check_identity(self):
        self.assertEqual(
            "29cb5faef0d82914d0d7fcf146548725b0facd12eb648a805ad98fcd1e9abdd6",
            checks_contract_digest({}),
        )
        enabled_recipe = {
            **self.enabled,
            "recipe_checks": True,
            "recipe_catalog_digest": RECIPE_CATALOG_DIGEST,
        }
        self.assertEqual(
            checks_contract_digest(enabled_recipe),
            checks_contract_digest({"goal": 99, "local_yaml_word_list": ["WRONG"], **enabled_recipe}),
        )
        self.assertNotEqual(checks_contract_digest({}), checks_contract_digest(self.enabled))
        for invalid in (
            {"recipe_checks": 1},
            {"recipe_checks": True},
            {"recipe_checks": True, "recipe_catalog_digest": "0" * 64},
            {"recipe_checks": False, "recipe_catalog_digest": RECIPE_CATALOG_DIGEST},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                checks_contract_digest(invalid)


if __name__ == "__main__":
    unittest.main()
