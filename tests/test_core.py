import json
import random
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from word_factori.bridge import BridgeState, ReceivedItem, bind_game_slot, load_state, reconcile, save_state
from word_factori.client_core import (
    campaign_compatible,
    game_font_path,
    goal_reached,
    inventory_view,
    location_codes_for_native_slots,
    mod_is_selected,
    native_slots_for_location_codes,
    parse_connection_url,
    resolve_game_slot_binding,
    resolve_room_campaign,
    state_identity,
)
from word_factori.data import CAMPAIGN_DIGEST, ITEM_POOL, LOCATIONS, MACHINE_ITEMS
from word_factori.layout import fixed_layout, layout_slot_data, shuffled_layout
from word_factori.mod import render_levels, write_campaign_identity
from word_factori.campaign import campaign_digest, campaign_for_level_set, load_campaign
from word_factori.data import locations_for_level_set
from word_factori.capabilities import requirements_for_record, unavoidable_nonbootstrap_machines
from word_factori.requirements import WORD_REQUIREMENT_OPTIONS, access_rule_for, previous_page_names
from word_factori.save import ActiveSlot, parse_active_slot, parse_save


class CapabilityTests(unittest.TestCase):
    def test_challenges_are_keyed_by_stable_identity(self):
        records = {record.stable_key: record for record in load_campaign().levels}
        cat = requirements_for_record(records["challenge-cat-compact"])
        phone = requirements_for_record(records["challenge-phone-no-waste"])
        self.assertEqual(4, len(cat[0]))
        self.assertIn("Merger4 Access", phone[0])

    def test_unavoidable_profile_intersects_every_valid_route(self):
        record = next(x for x in load_campaign().levels if x.stable_key == "complete-v")
        expected = set.intersection(*map(set, requirements_for_record(record)))
        expected.discard("Bender Access")
        self.assertEqual(
            frozenset(expected), unavoidable_nonbootstrap_machines(record),
        )


class State:
    def __init__(self, items, reachable):
        self.items = set(items)
        self.reachable = set(reachable)

    def has_all(self, names, player):
        return set(names) <= self.items

    def can_reach_location(self, name, player):
        return name in self.reachable


class DataTests(unittest.TestCase):
    def test_world_has_forty_stable_indices_and_pool_items(self):
        self.assertEqual(list(range(40)), [location.canonical_index for location in LOCATIONS])
        self.assertEqual(list(range(40)), [location.slot_index for location in LOCATIONS])
        self.assertEqual([index // 6 for index in range(40)], [location.page_index for location in LOCATIONS])
        self.assertEqual(40, len({location.name for location in LOCATIONS}))
        self.assertEqual(40, len(ITEM_POOL))
        self.assertEqual(5, ITEM_POOL.count("Progressive World Access"))
        self.assertNotIn("Progressive Word Length", ITEM_POOL)
        self.assertFalse(any(name.endswith("Permit") for name in ITEM_POOL))

    def test_derived_recipe_requirements_cover_every_target(self):
        expected = {location.target for location in LOCATIONS if location.kind in {"word", "final"}}
        self.assertEqual(expected, set(WORD_REQUIREMENT_OPTIONS))

    def test_distributable_mod_has_matching_forty_level_indices(self):
        path = Path(__file__).parents[1] / "game_mod" / "word factori archipelago" / "levels.json"
        levels = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([location.target for location in LOCATIONS], [level["text"] for level in levels])

    def test_first_native_page_has_no_sibling_frontier(self):
        rule = access_rule_for(LOCATIONS[2], LOCATIONS, player=1)
        self.assertTrue(rule(State({"Merger2 Access"}, set())))

    def test_later_native_page_requires_four_reachable_predecessor_slots(self):
        rule = access_rule_for(LOCATIONS[6], LOCATIONS, player=1)
        all_machines = set(MACHINE_ITEMS)
        page_one = [location.name for location in LOCATIONS[:6]]
        self.assertFalse(rule(State(all_machines, page_one[:3])))
        self.assertTrue(rule(State(all_machines, page_one[:4])))

    def test_recipe_requirements_remain_closed_when_frontier_is_open(self):
        rule = access_rule_for(LOCATIONS[6], LOCATIONS, player=1)
        page_one = [location.name for location in LOCATIONS[:6]]
        self.assertFalse(rule(State(set(), page_one[:4])))

    def test_third_native_page_uses_only_immediately_preceding_page(self):
        rule = access_rule_for(LOCATIONS[12], LOCATIONS, player=1)
        all_machines = set(MACHINE_ITEMS)
        page_one = [location.name for location in LOCATIONS[:6]]
        page_two = [location.name for location in LOCATIONS[6:12]]
        self.assertEqual(tuple(page_two), previous_page_names(LOCATIONS[12], LOCATIONS))
        self.assertFalse(rule(State(all_machines, page_one)))
        self.assertTrue(rule(State(all_machines, page_two[:4])))


class ModTests(unittest.TestCase):
    def test_world_access_disables_input_without_shifting_level(self):
        levels = render_levels({"Bender Access"}, world_access=0)
        self.assertEqual(40, len(levels))
        self.assertEqual("I", levels[0]["text"])
        self.assertEqual("C", levels[30]["text"])
        self.assertEqual(0, levels[32]["module_counts"]["IFactory"])

    def test_core_custom_level_set_renders_only_its_stable_sequential_levels(self):
        locations = locations_for_level_set("core_campaign")
        levels = render_levels({"Bender Access"}, world_access=0, locations=locations)
        self.assertEqual(30, len(levels))
        self.assertEqual("I", levels[0]["text"])
        self.assertEqual("PITCHFORK", levels[-1]["text"])

    def test_missing_machine_is_zero_and_received_machine_is_unlimited(self):
        locked = render_levels({"Bender Access"}, 5)
        unlocked = render_levels({"Bender Access", "Rotation Access"}, 5)
        self.assertEqual(0, locked[0]["module_counts"]["Rotate_cw"])
        self.assertNotIn("Rotate_cw", unlocked[0]["module_counts"])

    def test_challenge_limits_remain_after_unlock(self):
        levels = render_levels(set(MACHINE_ITEMS), 5)
        self.assertEqual(1, levels[26]["module_counts"]["Bend"])
        self.assertEqual(4, levels[26]["module_counts"]["Merger2"])

    def test_discovery_lab_disables_unlisted_routes(self):
        levels = render_levels(set(MACHINE_ITEMS), 5)
        self.assertNotIn("Bend", levels[30]["module_counts"])
        self.assertEqual(0, levels[30]["module_counts"]["Merger2"])
        self.assertNotIn("Merger4", levels[33]["module_counts"])
        self.assertEqual(0, levels[33]["module_counts"]["Merger2"])

    def test_campaign_identity_matches_runtime_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archipelago_campaign.json"
            write_campaign_identity(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("word-factori-hybrid", payload["campaign_id"])
        self.assertEqual("1.2.0", payload["manifest_version"])
        self.assertEqual(CAMPAIGN_DIGEST, payload["manifest_digest"])
        self.assertEqual(40, payload["level_count"])

    def test_campaign_identity_can_be_written_for_selected_curated_set(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archipelago_campaign.json"
            write_campaign_identity(path, campaign_for_level_set("core_campaign"))
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("word-factori-core", payload["campaign_id"])
        self.assertEqual(30, payload["level_count"])

    def test_campaign_identity_for_layout_includes_full_progression_identity(self):
        manifest = campaign_for_level_set("core_campaign")
        layout = fixed_layout(manifest, "core_campaign")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archipelago_campaign.json"
            write_campaign_identity(path, manifest, layout)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(layout.digest, payload["manifest_digest"])
        self.assertEqual(layout.digest, payload["layout_digest"])
        self.assertEqual(campaign_for_level_set("core_campaign").campaign_id, payload["campaign_id"])
        self.assertEqual(manifest.version, payload["manifest_version"])
        self.assertEqual(campaign_digest(manifest), payload["base_manifest_digest"])
        self.assertEqual(layout.progression_model, payload["progression_model"])
        self.assertEqual(layout.algorithm, payload["layout_algorithm"])
        self.assertEqual(layout.page_size, payload["page_size"])
        self.assertEqual(layout.page_unlock_count, payload["page_unlock_count"])
        self.assertEqual(len(manifest.levels), payload["level_count"])


class SaveTests(unittest.TestCase):
    def test_active_slot_exposes_stable_random_id_and_completion_set(self):
        payload = {"slots": {
            "0": {"slot_is_active": 0, "random_id": "blank-slot", "beaten_levels": {}},
            "1": {"slot_is_active": 1, "random_id": "ap-slot", "beaten_levels": {"0": 1, "30": 1}},
        }}
        active = parse_active_slot(payload)
        self.assertEqual("1", active.key)
        self.assertEqual("ap-slot", active.random_id)
        self.assertEqual(frozenset({0, 30}), active.beaten_levels)

    def test_active_slot_beaten_keys_become_indices(self):
        payload = {"slots": {"0": {"slot_is_active": 0, "random_id": "inactive-slot", "beaten_levels": {"9": 1}}, "1": {"slot_is_active": 1, "random_id": "active-slot", "beaten_levels": {"0": 1, "29": 1}}}, "lock_number": 0}
        self.assertEqual(frozenset({0, 29}), parse_save(payload))

    def test_multiple_active_slots_are_rejected(self):
        payload = {"slots": {"0": {"slot_is_active": 1, "beaten_levels": {}}, "1": {"slot_is_active": 1, "beaten_levels": {}}}}
        with self.assertRaisesRegex(ValueError, "exactly one active"):
            parse_save(payload)

    def test_stale_active_flag_is_disambiguated_by_game_previous_save(self):
        payload = {"slots": {
            "2": {
                "slot_is_active": 1,
                "previous_save": -1.0,
                "random_id": "stale-slot",
                "beaten_levels": {"0": 1},
            },
            "0": {
                "slot_is_active": True,
                "previous_save": 0.0,
                "random_id": "selected-slot",
                "beaten_levels": {},
            },
        }}
        active = parse_active_slot(payload)
        self.assertEqual("0", active.key)
        self.assertEqual("selected-slot", active.random_id)
        self.assertEqual(frozenset(), active.beaten_levels)


class BridgeTests(unittest.TestCase):
    def test_game_slot_binding_survives_sidecar_round_trip(self):
        state = bind_game_slot(BridgeState.empty(), "game-slot-A")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bridge-state.json"
            save_state(path, state)
            loaded = load_state(path)
        self.assertEqual("game-slot-A", loaded.game_slot_id)
        self.assertEqual(state, loaded)

    def test_receive_indices_are_idempotent_but_distinct_copies_count(self):
        state = BridgeState.empty()
        result = reconcile(state, [ReceivedItem(2, "Progressive World Access"), ReceivedItem(2, "Progressive World Access"), ReceivedItem(8, "Progressive World Access")], {3}, set())
        self.assertEqual(2, result.state.item_counts["Progressive World Access"])
        self.assertEqual((2, 8), result.applied_indices)
        self.assertEqual(frozenset({3}), result.new_checks)

    def test_server_known_checks_are_not_resent(self):
        result = reconcile(BridgeState.empty(), [], {3, 5}, {5})
        self.assertEqual(frozenset({3}), result.new_checks)

    def test_authoritative_reconnect_drops_stale_sidecar_deliveries(self):
        stale = BridgeState({0: "Rotation Access", 1: "Reflection Access"}, {"Rotation Access": 1, "Reflection Access": 1})
        result = reconcile(stale, [ReceivedItem(0, "Rotation Access")], set(), set(), authoritative=True)
        self.assertEqual({0: "Rotation Access"}, result.state.applied)
        self.assertNotIn("Reflection Access", result.state.item_counts)

    def test_state_round_trip_survives_reconnect(self):
        state = reconcile(
            BridgeState.empty(),
            [ReceivedItem(0, "Bender Access"), ReceivedItem(4, "Progressive World Access")],
            set(),
            set(),
        ).state
        state = BridgeState(state.applied, state.item_counts, frozenset({975301000}))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bridge-state.json"
            save_state(path, state)
            self.assertEqual(state, load_state(path))

    def test_malformed_sidecar_is_rejected_without_partial_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bridge-state.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "object"):
                load_state(path)


class ClientCoreTests(unittest.TestCase):
    def shuffled_slot_data(self):
        manifest = campaign_for_level_set("discovery_labs")
        layout = shuffled_layout(manifest, "discovery_labs", random.Random(9173))
        return {
            **layout_slot_data(layout),
            "level_set": "discovery_labs",
            "campaign_id": manifest.campaign_id,
            "manifest_version": manifest.version,
            "manifest_digest": layout.digest,
            "level_count": len(manifest.levels),
        }

    def test_shuffled_room_reconstructs_slot_order_and_translates_save_indices(self):
        resolved = resolve_room_campaign(self.shuffled_slot_data())
        expected = frozenset({resolved.locations[0].code, resolved.locations[7].code})

        self.assertFalse(resolved.legacy)
        self.assertEqual(
            expected,
            location_codes_for_native_slots({0, 7, 400}, resolved.locations),
        )
        self.assertEqual(
            frozenset({0, 7}),
            native_slots_for_location_codes(expected, resolved.locations),
        )

    def test_translation_rejects_duplicate_native_slots_and_location_codes(self):
        resolved = resolve_room_campaign(self.shuffled_slot_data())
        duplicate_slot = replace(
            resolved.locations[1], slot_index=resolved.locations[0].slot_index,
        )
        duplicate_code = replace(
            resolved.locations[1], canonical_index=resolved.locations[0].canonical_index,
        )

        with self.assertRaisesRegex(ValueError, "duplicate native slot"):
            location_codes_for_native_slots(
                {0}, (resolved.locations[0], duplicate_slot),
            )
        with self.assertRaisesRegex(ValueError, "duplicate location code"):
            native_slots_for_location_codes(
                {resolved.locations[0].code}, (resolved.locations[0], duplicate_code),
            )

    def test_goals_use_canonical_non_discovery_and_final_location_codes(self):
        resolved = resolve_room_campaign(self.shuffled_slot_data())
        campaign_codes = {
            location.code for location in resolved.locations
            if location.kind != "discovery"
        }
        first_twenty = set(sorted(campaign_codes)[:20])
        discovery_code = next(
            location.code for location in resolved.locations
            if location.kind == "discovery"
        )
        final_code = next(
            location.code for location in resolved.locations
            if location.stable_key == "pitchfork-final"
        )

        self.assertTrue(goal_reached(0, 20, first_twenty, resolved.locations))
        self.assertFalse(goal_reached(
            0, 20, set(sorted(first_twenty)[:19]) | {discovery_code}, resolved.locations,
        ))
        self.assertTrue(goal_reached(1, 20, {final_code}, resolved.locations))
        self.assertFalse(goal_reached(
            1, 20, {resolved.locations[29].code} - {final_code}, resolved.locations,
        ))

    def test_room_resolution_rejects_duplicate_layout_keys_and_digest_mismatch(self):
        duplicate = self.shuffled_slot_data()
        duplicate["level_order"][1] = duplicate["level_order"][0]
        with self.assertRaisesRegex(ValueError, "complete and unique"):
            resolve_room_campaign(duplicate)

        mismatch = self.shuffled_slot_data()
        mismatch["manifest_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "manifest digest"):
            resolve_room_campaign(mismatch)

    def test_legacy_room_uses_canonical_order(self):
        manifest = campaign_for_level_set("discovery_labs")
        resolved = resolve_room_campaign({
            "implementation_version": "1.2.2",
            "level_set": "discovery_labs",
            "campaign_id": manifest.campaign_id,
            "manifest_version": manifest.version,
            "manifest_digest": campaign_digest(manifest),
            "level_count": len(manifest.levels),
        })

        self.assertTrue(resolved.legacy)
        self.assertIsNone(resolved.layout)
        self.assertEqual(
            list(range(len(manifest.levels))),
            [location.slot_index for location in resolved.locations],
        )

    def test_game_font_is_resolved_only_when_neighboring_file_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "word factori.exe"
            executable.touch()
            font = executable.with_name("FredokaOne.ttf")
            self.assertIsNone(game_font_path(executable))
            font.touch()
            self.assertEqual(font, game_font_path(executable))

    def test_game_font_rejects_directory_named_like_font(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "word factori.exe"
            executable.touch()
            executable.with_name("FredokaOne.ttf").mkdir()
            self.assertIsNone(game_font_path(executable))

    def test_empty_unbound_game_slot_is_safe_to_bind(self):
        active = ActiveSlot("0", "game-slot-A", frozenset())
        self.assertEqual("game-slot-A", resolve_game_slot_binding(None, active))

    def test_unbound_game_slot_with_prior_progress_is_rejected(self):
        active = ActiveSlot("1", "old-slot", frozenset({0, 29}))
        with self.assertRaisesRegex(ValueError, "prior completions"):
            resolve_game_slot_binding(None, active)

    def test_switching_away_from_bound_game_slot_is_rejected(self):
        active = ActiveSlot("0", "game-slot-B", frozenset())
        with self.assertRaisesRegex(ValueError, "different Word Factori save"):
            resolve_game_slot_binding("game-slot-A", active)

    def test_inventory_view_translates_received_items_to_mod_unlocks(self):
        received = [
            ReceivedItem(0, "Bender Access"),
            ReceivedItem(1, "Rotation Access"),
            ReceivedItem(2, "Progressive World Access"),
            ReceivedItem(3, "Progressive World Access"),
        ]
        view = inventory_view(received)
        self.assertEqual({"Bender Access", "Rotation Access"}, view.owned_machines)
        self.assertEqual(2, view.world_access)

    def test_campaign_count_and_final_factory_goals(self):
        checked = {location.code for location in LOCATIONS[:25]}
        self.assertTrue(goal_reached(0, 25, checked, LOCATIONS))
        self.assertFalse(goal_reached(0, 25, checked - {LOCATIONS[24].code}, LOCATIONS))
        self.assertTrue(goal_reached(1, 25, {LOCATIONS[29].code}, LOCATIONS))
        self.assertFalse(goal_reached(1, 25, checked, LOCATIONS))

    def test_mod_selection_guard_accepts_only_owned_folder(self):
        expected = r"C:\Users\Player\AppData\Local\factori\mods\word factori archipelago"
        self.assertTrue(mod_is_selected({"folder": expected}, expected))
        self.assertTrue(mod_is_selected({"folder": "word factori archipelago"}, expected))
        self.assertTrue(mod_is_selected({"folder": "mods/word factori archipelago"}, expected))
        self.assertTrue(mod_is_selected({"folder": r"mods\word factori archipelago"}, expected))
        self.assertFalse(mod_is_selected({"folder": r"C:\somewhere\word factori archipelago"}, expected))
        self.assertFalse(mod_is_selected({"folder": r"C:\somewhere\another mod"}, expected))
        self.assertFalse(mod_is_selected({"folder": r"other\word factori archipelago"}, expected))
        self.assertFalse(mod_is_selected({"folder": r"mods\nested\word factori archipelago"}, expected))
        self.assertFalse(mod_is_selected({"folder": None}, expected))

    def test_manifest_mismatch_is_incompatible(self):
        slot = {
            "campaign_id": "word-factori-hybrid",
            "manifest_version": "1.1.0",
            "manifest_digest": "a" * 64,
        }
        installed = {**slot, "manifest_digest": "b" * 64, "level_count": 40}
        self.assertFalse(campaign_compatible(slot, installed))
        installed["manifest_digest"] = slot["manifest_digest"]
        self.assertTrue(campaign_compatible(slot, installed))

    def test_layout_compatibility_compares_every_installed_identity_field(self):
        slot = self.shuffled_slot_data()
        manifest = campaign_for_level_set("discovery_labs")
        layout = shuffled_layout(
            manifest, "discovery_labs", random.Random(9173),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archipelago_campaign.json"
            write_campaign_identity(path, manifest, layout)
            installed = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(campaign_compatible(slot, installed))
        for field in (
            "progression_model",
            "layout_algorithm",
            "page_size",
            "page_unlock_count",
            "base_manifest_digest",
            "layout_digest",
        ):
            with self.subTest(field=field):
                mismatched = dict(installed)
                mismatched[field] = "wrong"
                self.assertFalse(campaign_compatible(slot, mismatched))

    def test_connection_url_separates_credentials_from_server_address(self):
        self.assertEqual(
            ("archipelago.gg:38281", "Factory Player", "secret"),
            parse_connection_url("archipelago://Factory%20Player:secret@archipelago.gg:38281"),
        )

    def test_bridge_identity_is_seed_team_and_slot_scoped(self):
        first = state_identity("Seed-A", 0, 1, "Factory Player")
        self.assertNotEqual(first, state_identity("Seed-B", 0, 1, "Factory Player"))
        self.assertNotEqual(first, state_identity("Seed-A", 1, 1, "Factory Player"))
        self.assertNotEqual(first, state_identity("Seed-A", 0, 2, "Factory Player"))


if __name__ == "__main__":
    unittest.main()
