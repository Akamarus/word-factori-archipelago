import random
import unittest

from word_factori.campaign import campaign_for_level_set
from word_factori.client_core import goal_reached, resolve_room_campaign
from word_factori.layout import RECIPE_MODEL, build_layout, layout_slot_data
from word_factori.recipe_checks import RECIPE_CATALOG_DIGEST, RECIPE_CHECKS
from word_factori.save import parse_active_slot


class RecipeIntegrationTests(unittest.TestCase):
    def slot(self, enabled=True):
        manifest = campaign_for_level_set("discovery_labs")
        layout = build_layout(manifest, "discovery_labs", "shuffled_pages", random.Random(7),
                              integration_mode="enhanced", machine_only=True,
                              recipe_checks=enabled)
        return {
            **layout_slot_data(layout), "level_set": "discovery_labs",
            "campaign_id": manifest.campaign_id, "manifest_version": manifest.version,
            "manifest_digest": layout.digest, "level_count": len(manifest.levels),
            "goal": 0, "campaign_count": 25,
            **({"recipe_checks": True, "recipe_catalog_digest": RECIPE_CATALOG_DIGEST} if enabled else {}),
        }

    def test_default_is_enabled_and_layout_uses_recipe_protocol(self):
        self.assertEqual(RECIPE_MODEL, self.slot()["progression_model"])
        self.assertNotEqual(RECIPE_MODEL, self.slot(False)["progression_model"])

    def test_room_recipe_contract_requires_exact_boolean_and_digest(self):
        resolve_room_campaign(self.slot())
        for change in ({"recipe_checks": 1}, {"recipe_checks": True, "recipe_catalog_digest": "bad"},
                       {"progression_model": RECIPE_MODEL, "recipe_checks": False},
                       {"recipe_checks": False, "recipe_catalog_digest": RECIPE_CATALOG_DIGEST}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                resolve_room_campaign({**self.slot(), **change})

    def test_legacy_room_cannot_bypass_recipe_contract_validation(self):
        manifest = campaign_for_level_set("discovery_labs")
        legacy = {"campaign_id": manifest.campaign_id, "manifest_version": manifest.version,
                  "manifest_digest": __import__("word_factori.campaign", fromlist=["campaign_digest"]).campaign_digest(manifest),
                  "level_count": len(manifest.levels)}
        for change in ({"recipe_checks": True, "recipe_catalog_digest": RECIPE_CATALOG_DIGEST},
                       {"recipe_checks": 1}, {"recipe_catalog_digest": RECIPE_CATALOG_DIGEST}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                resolve_room_campaign({**legacy, **change})

    def test_recipe_ids_are_not_native_slots_or_victory(self):
        recipe_ids = {check.code for check in RECIPE_CHECKS}
        self.assertFalse(goal_reached(0, 25, recipe_ids))

    def test_active_slot_exposes_validated_recipe_journal(self):
        active = parse_active_slot({"slots": {"0": {"slot_is_active": 1, "random_id": "r",
            "beaten_levels": {}, "recipes": {"oBend": {"I": "C"}}}}})
        self.assertEqual({next(check.code for check in RECIPE_CHECKS if check.machine == "oBend" and check.inputs == ("I",) and check.output == "C")}, set(active.recipe_codes))

    def test_prior_recipe_discoveries_block_fresh_recipe_binding(self):
        active = parse_active_slot({"slots": {"0": {"slot_is_active": 1, "random_id": "r",
            "beaten_levels": {}, "recipes": {"oBend": {"I": "C"}}}}})
        from word_factori.client_core import resolve_game_slot_binding
        with self.assertRaisesRegex(ValueError, "prior"):
            resolve_game_slot_binding(None, active, recipe_checks=True)

    def test_malformed_journal_is_ignored_when_recipe_checks_are_off(self):
        active = parse_active_slot({"slots": {"0": {"slot_is_active": 1, "random_id": "r",
            "beaten_levels": {}, "recipes": {"oBend": []}}}})
        from word_factori.client_core import resolve_game_slot_binding
        self.assertIsNone(active.recipe_codes)
        self.assertEqual("r", resolve_game_slot_binding(None, active, recipe_checks=False))


if __name__ == "__main__":
    unittest.main()
