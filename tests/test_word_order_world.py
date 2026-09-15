import dataclasses
import random
import unittest

from tests import test_world_layout as fixtures

import word_factori
from word_factori.campaign import campaign_for_level_set
from word_factori.client_core import resolve_room_campaign, state_identity
from word_factori.layout import build_layout, layout_slot_data
from word_factori.recipe_checks import RECIPE_CATALOG_DIGEST
from word_factori.word_orders import (
    FIRST_WORD_ORDER_CODE,
    WORD_ORDER_NAME_TO_ID,
    WordOrder,
    orders_slot_data,
)


TWENTY_WORDS = tuple(f"A{letter}" for letter in "ABCDEFGHIJKLMNOPQRST")


class _MachineState:
    def __init__(self, owned=(), reachable_locations=()):
        self.owned = set(owned)
        self.reachable_locations = set(reachable_locations)

    def has(self, name, player):
        return name in self.owned

    def has_all(self, names, player):
        return set(names) <= self.owned

    def can_reach_location(self, name, player):
        return name in self.reachable_locations


class WordOrderWorldTests(unittest.TestCase):
    def make_world(self, seed=17, **options):
        return fixtures.WorldLayoutTests().make_world(seed, **options)

    def test_options_default_off_with_bounded_count_and_empty_word_list(self):
        options = fixtures.world_options
        fields = {field.name for field in dataclasses.fields(options.WordFactoriOptions)}

        self.assertEqual(0, options.TypeAWordChecks.default)
        self.assertEqual((1, 20, 5), (
            options.TypeAWordCount.range_start,
            options.TypeAWordCount.range_end,
            options.TypeAWordCount.default,
        ))
        self.assertEqual((), options.TypeAWordWords.default)
        self.assertTrue({"type_a_word_checks", "type_a_word_count", "type_a_word_words"} <= fields)

    def test_word_list_conversion_rejects_non_sequence_yaml_shapes(self):
        invalid_values = (None, True, 7, "JACK", {"JACK": True}, {"JACK"})
        for value in invalid_values:
            for label, convert in (
                ("from_any", fixtures.world_options.TypeAWordWords.from_any),
                ("direct", fixtures.world_options.TypeAWordWords),
            ):
                with self.subTest(label=label, value=value):
                    try:
                        convert(value)
                    except ValueError as error:
                        self.assertRegex(
                            str(error), r"type_a_word_words.*\[JACK, ISLAND\]"
                        )
                    except Exception as error:
                        self.fail(f"wrong exception type: {type(error).__name__}: {error}")
                    else:
                        self.fail("invalid word-list shape was accepted")

    def test_word_list_conversion_accepts_lists_tuples_and_empty_default(self):
        for value, expected in (
            (["JACK", "ISLAND"], ("JACK", "ISLAND")),
            (("JACK", "ISLAND"), ("JACK", "ISLAND")),
            (fixtures.world_options.TypeAWordWords.default, ()),
        ):
            with self.subTest(value=value):
                converted = fixtures.world_options.TypeAWordWords.from_any(value)
                self.assertEqual(expected, tuple(converted.value))

    def test_disabled_orders_ignore_an_invalid_semantic_or_empty_local_word_list(self):
        world = self.make_world(type_a_word_checks=False, type_a_word_words=["not-a-word"])
        world.create_regions()

        self.assertEqual((), world.word_orders)
        self.assertNotIn("Word Order 01", {
            location.name
            for region in world.multiworld.regions
            for location in region.locations
        })
        self.assertEqual({"type_a_word_checks": False}, {
            key: value for key, value in world.fill_slot_data().items()
            if key.startswith("type_a_word")
        })

    def test_enabled_option_errors_name_the_option_and_player(self):
        for count, words in ((2, ["JACK"]), (1, ["straße"]), (21, TWENTY_WORDS), (True, ["JACK"])):
            with self.subTest(count=count, words=words), self.assertRaisesRegex(
                ValueError, r"Type-a-Word options for player 1.*invalid"
            ):
                self.make_world(
                    type_a_word_checks=True,
                    type_a_word_count=count,
                    type_a_word_words=words,
                )

    def test_twenty_orders_are_selected_once_with_static_ids_for_both_recipe_settings(self):
        for recipe_checks in (False, True):
            with self.subTest(recipe_checks=recipe_checks):
                world = self.make_world(
                    104729,
                    recipe_checks=recipe_checks,
                    type_a_word_checks=True,
                    type_a_word_count=20,
                    type_a_word_words=TWENTY_WORDS,
                )
                selected = world.word_orders
                for _ in range(20):
                    world.random.random()
                world.create_regions()

                self.assertEqual(selected, world.word_orders)
                self.assertEqual(20, len(selected))
                self.assertEqual("machines_enhanced_words_v1", world.fill_slot_data()["progression_model"])
                self.assertEqual(
                    list(range(FIRST_WORD_ORDER_CODE, FIRST_WORD_ORDER_CODE + 20)),
                    [world.get_location(f"Word Order {number:02d}").address for number in range(1, 21)],
                )
                self.assertEqual(WORD_ORDER_NAME_TO_ID, {
                    name: world.location_name_to_id[name] for name in WORD_ORDER_NAME_TO_ID
                })

    def test_order_regions_are_independent_and_locations_use_machine_alternatives_only(self):
        world = self.make_world(
            type_a_word_checks=True,
            type_a_word_count=2,
            type_a_word_words=["JACK", "II"],
        )
        world.create_regions()
        by_target = {
            order.word: world.get_location(order.name)
            for order in world.word_orders
        }
        start_state = _MachineState()

        self.assertTrue(by_target["JACK"].parent.can_reach(start_state))
        self.assertFalse(by_target["JACK"].can_reach(start_state))
        self.assertTrue(by_target["JACK"].can_reach(_MachineState({"Merger2 Access", "Rotation Access"})))
        self.assertTrue(by_target["II"].can_reach(start_state))
        self.assertIn("JACK", by_target["JACK"].parent.name)

    def test_orders_add_only_one_filler_per_location(self):
        disabled = self.make_world(23, recipe_checks=True)
        enabled = self.make_world(
            23,
            recipe_checks=True,
            type_a_word_checks=True,
            type_a_word_count=3,
            type_a_word_words=["JACK", "ISLAND", "FACTORY"],
        )
        disabled.create_items()
        enabled.create_items()

        self.assertEqual(len(disabled.multiworld.itempool) + 3, len(enabled.multiworld.itempool))
        self.assertEqual(
            [item.name for item in disabled.multiworld.itempool if item.classification == "progression"],
            [item.name for item in enabled.multiworld.itempool if item.classification == "progression"],
        )
        self.assertEqual(
            sum(item.name == "I Sticker" for item in disabled.multiworld.itempool) + 3,
            sum(item.name == "I Sticker" for item in enabled.multiworld.itempool),
        )

    def test_order_checks_neither_unlock_pages_nor_count_for_campaign_victory(self):
        world = self.make_world(
            29,
            type_a_word_checks=True,
            type_a_word_count=3,
            type_a_word_words=["JACK", "ISLAND", "FACTORY"],
        )
        world.create_regions()
        locations = {location.name: location for region in world.multiworld.regions for location in region.locations}
        order_names = {order.name for order in world.word_orders}
        first_second_page = world.selected_locations()[6].name
        state = _MachineState(word_factori.MACHINE_ITEMS, order_names)

        self.assertFalse(locations[first_second_page].access_rule(state))
        self.assertFalse(locations["Victory"].access_rule(state))

    def test_tracker_restores_authoritative_orders_despite_conflicting_yaml_and_rng(self):
        original = self.make_world(
            31,
            type_a_word_checks=True,
            type_a_word_count=3,
            type_a_word_words=["JACK", "ISLAND", "FACTORY"],
        )
        slot_data = original.fill_slot_data()
        restored = self.make_world(
            37,
            type_a_word_checks=True,
            type_a_word_count=1,
            type_a_word_words=["WRONG"],
            passthrough={word_factori.GAME: slot_data},
        )

        self.assertEqual(original.word_orders, restored.word_orders)
        self.assertEqual(slot_data, restored.fill_slot_data())
        self.assertEqual(random.Random(37).getstate(), restored.random.getstate())

    def test_room_validation_requires_word_model_and_complete_enabled_metadata(self):
        world = self.make_world(
            type_a_word_checks=True,
            type_a_word_count=2,
            type_a_word_words=["JACK", "ISLAND"],
        )
        slot = world.fill_slot_data()
        self.assertEqual(world.word_orders, resolve_room_campaign(slot).word_orders)

        for change in (
            {"progression_model": "machines_enhanced_four_of_six_v1"},
            {"type_a_word_checks": False},
            {"alphabet_logic_digest": "bad"},
        ):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "Type-a-Word|word"):
                resolve_room_campaign({**slot, **change})

        without_metadata = {
            key: value for key, value in slot.items()
            if key not in {"type_a_word_checks", "word_orders", "alphabet_logic_version", "alphabet_logic_digest"}
        }
        with self.assertRaisesRegex(ValueError, "Type-a-Word|word"):
            resolve_room_campaign(without_metadata)

    def test_state_identity_changes_with_authoritative_words_but_preserves_recipe_identity(self):
        world = self.make_world(
            41,
            recipe_checks=True,
            type_a_word_checks=True,
            type_a_word_count=2,
            type_a_word_words=["JACK", "ISLAND", "FACTORY"],
        )
        slot = world.fill_slot_data()
        changed_orders = orders_slot_data((WordOrder(1, "FACTORY"), WordOrder(2, "ISLAND")))

        first = state_identity("Words", 0, 1, "Player", slot)
        self.assertNotEqual(first, state_identity("Words", 0, 1, "Player", {**slot, **changed_orders}))

        manifest = campaign_for_level_set("discovery_labs")
        recipe_layout = build_layout(
            manifest,
            "discovery_labs",
            "shuffled_pages",
            random.Random(7),
            integration_mode="enhanced",
            machine_only=True,
            recipe_checks=True,
        )
        recipe_slot = {
            **layout_slot_data(recipe_layout),
            "level_set": "discovery_labs",
            "campaign_id": manifest.campaign_id,
            "manifest_version": manifest.version,
            "manifest_digest": recipe_layout.digest,
            "level_count": len(manifest.levels),
            "goal": 0,
            "campaign_count": 25,
            "recipe_checks": True,
            "recipe_catalog_digest": RECIPE_CATALOG_DIGEST,
        }
        self.assertEqual(
            "Recipe-team-0-slot-1-Player-contract-2deb738a2ff458131bebfefdef9f469c01a32b556d3b6bd8c28a7d7d61e40e44",
            state_identity("Recipe", 0, 1, "Player", recipe_slot),
        )


if __name__ == "__main__":
    unittest.main()
