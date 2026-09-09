import random
import unittest

from word_factori.campaign import campaign_for_level_set
from word_factori.capabilities import requirements_for_record
from word_factori.data import locations_for_layout
from word_factori.layout import build_layout, layout_from_slot_data, layout_slot_data
from word_factori.requirements import access_rule_for


class EnhancedLayoutTests(unittest.TestCase):
    def layout(self, seed=1, level_set="core_campaign"):
        manifest = campaign_for_level_set(level_set)
        return manifest, build_layout(manifest, level_set, "shuffled_pages", random.Random(seed), integration_mode="enhanced")

    def test_first_page_has_two_bootstrap_four_early_and_varies_membership(self):
        for level_set in ("core_campaign", "discovery_labs"):
            memberships, positions = set(), set()
            for seed in range(20):
                manifest, layout = self.layout(seed, level_set)
                records = {r.stable_key: r for r in manifest.levels}
                first = [records[k] for k in layout.ordered_stable_keys[:6]]
                bootstrap = {"Bender Access"}
                early = bootstrap | {"Merger2 Access", "Rotation Access"}
                for owned, minimum in ((bootstrap, 2), (early, 4)):
                    self.assertGreaterEqual(sum(r.region == "Starter Workshop" and any(route <= owned for route in requirements_for_record(r)) for r in first), minimum)
                self.assertEqual(sum(r.region != "Starter Workshop" for r in first), 2)
                self.assertFalse(any(r.kind in {"challenge", "final"} for r in first))
                memberships.add(frozenset(layout.ordered_stable_keys[:6]))
                positions.add(layout.ordered_stable_keys[:6])
                self.assertEqual(layout, layout_from_slot_data(manifest, level_set, layout_slot_data(layout)))
                self.assertEqual(layout, self.layout(seed, level_set)[1])
            self.assertGreater(len(memberships), 5)
            self.assertGreater(len(positions), 5)

    def test_all_first_page_rules_are_independent_and_four_open_second_page(self):
        manifest, layout = self.layout()
        locations = locations_for_layout(manifest, layout)
        class State:
            reachable = set()
            def has_all(self, needs, player): return True
            def can_reach_location(self, name, player): return name in self.reachable
        state = State()
        for location in locations[:6]:
            self.assertTrue(access_rule_for(location, locations, 1, integration_mode="enhanced")(state))
        rule = access_rule_for(locations[6], locations, 1, integration_mode="enhanced")
        state.reachable = {loc.name for loc in locations[:3]}
        self.assertFalse(rule(state))
        state.reachable.add(locations[4].name)
        self.assertTrue(rule(state))

    def test_supported_still_uses_six_ordered_tutorials(self):
        manifest = campaign_for_level_set("core_campaign")
        layout = build_layout(manifest, "core_campaign", "shuffled_pages", random.Random(1))
        self.assertEqual(layout.ordered_stable_keys[:6], ("complete-i", "complete-c", "complete-v", "complete-l", "complete-o", "complete-a"))
        self.assertEqual(layout.tutorial_page_unlock_count, 6)


if __name__ == "__main__": unittest.main()
