import random
import unittest
from types import SimpleNamespace

from tests import test_world_layout as world_fixtures
from word_factori.campaign import campaign_for_level_set
from word_factori.client_core import resolve_room_campaign
from word_factori.data import locations_for_layout
from word_factori.layout import build_layout, fixed_layout, shuffled_layout, layout_slot_data
from word_factori.mod import render_levels
from word_factori.requirements import access_rule_for


class MachineProgressionTests(unittest.TestCase):
    def test_sphere_replay_accepts_j_with_machines_but_no_world_access(self):
        from tools.verify_generation_matrix import ProgressionSphere, SphereEntry, replay_progression_choices
        records = list(campaign_for_level_set("discovery_labs").levels)
        index = next(i for i, r in enumerate(records) if r.stable_key == "discover-j-joining")
        records[0], records[index] = records[index], records[0]
        identity = SimpleNamespace(level_set="discovery_labs", integration_mode="enhanced",
            progression_model="machines_enhanced_four_of_six_v1",
            level_order=tuple(r.stable_key for r in records),
            location_names=tuple(r.name for r in records))
        spheres = (ProgressionSphere(0, (SphereEntry(None, "Bender Access"), SphereEntry(None, "Merger2 Access"))),
                   ProgressionSphere(1, (SphereEntry(records[0].name, "Reflection Access"),)))
        result = replay_progression_choices(spheres, identity)
        self.assertEqual(1, result.total_pre_goal_spheres)

    def world(self, *, enhanced=1, level_set=1):
        return world_fixtures.WorldLayoutTests().make_world(23000, integration_mode=enhanced, level_set=level_set)

    def test_new_rooms_have_i_in_every_level_without_world_access(self):
        for mode in (0, 1):
            world = self.world(enhanced=mode)
            resolved = resolve_room_campaign(world.fill_slot_data())
            rendered = render_levels({"Bender Access"}, 0, locations=resolved.locations)
            self.assertTrue(all(entry["module_counts"].get("IFactory", -1) != 0 for entry in rendered))

    def test_new_region_entrances_do_not_require_world_access(self):
        world = self.world()
        world.create_regions()
        class NoItems:
            def has(self, *args): return False
        for region in world.multiworld.regions:
            for entrance in region.exits:
                self.assertTrue(entrance.access_rule(NoItems()), entrance.name)

    def test_new_pool_replaces_world_access_without_losing_checks_or_machines(self):
        for level_set, size in ((0, 30), (1, 40)):
            world = self.world(level_set=level_set)
            world.create_items()
            names = [item.name for item in world.multiworld.itempool]
            self.assertEqual(size, len(names))
            self.assertNotIn("Progressive World Access", names)
            for name in ("Rotation Access", "Reflection Access", "Merger2 Access", "Merger3 Access", "Merger4 Access"):
                self.assertEqual(1, names.count(name))

    def test_new_m_lab_still_requires_merger3_and_keeps_lab_limits(self):
        world = self.world()
        locations = world.selected_locations()
        lab = next(loc for loc in locations if loc.stable_key == "discover-m-triple-merge")
        class State:
            owned = {"Bender Access", "Merger2 Access", "Rotation Access"}
            def has_all(self, needs, player): return needs <= self.owned
            def can_reach_location(self, name, player): return True
        state = State()
        rule = access_rule_for(lab, locations, 1, integration_mode="enhanced")
        self.assertFalse(rule(state))
        state.owned = state.owned | {"Merger3 Access"}
        self.assertTrue(rule(state))
        counts = render_levels(state.owned, 0, locations=(lab,))[0]["module_counts"]
        self.assertNotIn("IFactory", counts)
        self.assertNotIn("Merger3", counts)
        self.assertEqual(0, counts["Merger2"])

    def test_old_contracts_keep_tiers_and_digest_on_reconnect(self):
        manifest = campaign_for_level_set("discovery_labs")
        for layout in (fixed_layout(manifest, "discovery_labs"), shuffled_layout(manifest, "discovery_labs", random.Random(23)),
                       build_layout(manifest, "discovery_labs", "shuffled_pages", random.Random(23), integration_mode="enhanced")):
            slot = self.world().fill_slot_data()
            slot.update(layout_slot_data(layout), manifest_digest=layout.digest)
            resolved = resolve_room_campaign(slot)
            self.assertEqual(layout.digest, resolved.layout.digest)
            lab = next(loc for loc in resolved.locations if loc.stable_key == "discover-j-joining")
            self.assertEqual(2, lab.world_tier)
            self.assertEqual(0, render_levels({"Bender Access", "Merger2 Access"}, 1, locations=(lab,))[0]["module_counts"]["IFactory"])

    def test_changing_new_contract_to_old_model_without_digest_is_rejected(self):
        slot = self.world().fill_slot_data()
        slot["progression_model"] = "enhanced_four_of_six_v1"
        with self.assertRaises(ValueError):
            resolve_room_campaign(slot)


if __name__ == "__main__": unittest.main()
