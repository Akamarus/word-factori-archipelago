from dataclasses import replace
import unittest

from tools.derive_requirements import validate_discovery_routes
from word_factori.campaign import (
    CampaignManifest,
    CampaignRecord,
    campaign_digest,
    load_campaign,
    validate_campaign,
    available_level_sets,
    campaign_for_level_set,
)
from word_factori.recipe_graph import RecipeGraph
from word_factori.data import BASE_ID, ITEM_POOL, LOCATIONS, MACHINE_ITEMS


class CampaignManifestTests(unittest.TestCase):
    def test_curated_level_sets_are_versioned_stable_and_share_the_core_campaign(self):
        self.assertEqual(("core_campaign", "discovery_labs"), available_level_sets())
        core = campaign_for_level_set("core_campaign")
        discovery = campaign_for_level_set("discovery_labs")

        self.assertEqual("word-factori-core", core.campaign_id)
        self.assertEqual("word-factori-hybrid", discovery.campaign_id)
        self.assertEqual("1.2.0", core.version)
        self.assertEqual("1.2.0", discovery.version)
        self.assertEqual(30, len(core.levels))
        self.assertEqual(40, len(discovery.levels))
        self.assertEqual(core.levels, discovery.levels[:30])
        self.assertNotEqual(campaign_digest(core), campaign_digest(discovery))

    def test_unknown_or_tampered_level_set_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "level set"):
            campaign_for_level_set("workshop-download")

    def test_hybrid_has_stable_campaign_and_appended_labs(self):
        manifest = load_campaign()
        self.assertEqual("word-factori-hybrid", manifest.campaign_id)
        self.assertEqual("1.1.0", manifest.version)
        self.assertEqual(list(range(40)), [record.index for record in manifest.levels])
        self.assertEqual("complete-i", manifest.levels[0].stable_key)
        self.assertEqual("pitchfork-final", manifest.levels[29].stable_key)
        self.assertEqual("discover-c-bending", manifest.levels[30].stable_key)
        self.assertEqual("discover-r-master-reflection", manifest.levels[39].stable_key)
        self.assertEqual(10, sum(record.kind == "discovery" for record in manifest.levels))

    def test_digest_is_canonical_and_validation_rejects_duplicate_index(self):
        manifest = load_campaign()
        self.assertEqual(campaign_digest(manifest), campaign_digest(load_campaign()))
        duplicate = replace(
            manifest,
            levels=manifest.levels[:-1] + (replace(manifest.levels[-1], index=38),),
        )
        with self.assertRaisesRegex(ValueError, "indices must be contiguous"):
            validate_campaign(duplicate)

    def test_invalid_discovery_route_names_the_offending_stable_key(self):
        record = CampaignRecord(
            stable_key="discover-c-bending",
            index=0,
            name="Discover C",
            target="C",
            region="Starter Workshop",
            world_tier=0,
            kind="discovery",
            required_route=frozenset({"Merger2 Access"}),
        )
        manifest = CampaignManifest("test", "1", (record,))
        graph = RecipeGraph.from_payload({"oIFactory": {"I": "I"}, "oBend": {"I": "C"}})
        with self.assertRaisesRegex(ValueError, "discover-c-bending"):
            validate_discovery_routes(graph, manifest)

    def test_full_collection_covers_every_declared_rule_and_preserves_ids(self):
        full = set(MACHINE_ITEMS)
        self.assertEqual(40, len(LOCATIONS))
        self.assertEqual(BASE_ID + 1000, LOCATIONS[0].code)
        self.assertEqual(BASE_ID + 1029, LOCATIONS[29].code)
        for location in LOCATIONS:
            self.assertLessEqual(location.world_tier, 5)
            self.assertTrue(location.required_route <= full)
        self.assertEqual(len(LOCATIONS), len(ITEM_POOL))


if __name__ == "__main__":
    unittest.main()
