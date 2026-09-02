from dataclasses import replace
import random
import unittest

from word_factori.campaign import campaign_digest, campaign_for_level_set
from word_factori.capabilities import FULL, unavoidable_nonbootstrap_machines
from word_factori.layout import (
    FIXED_ALGORITHM, PROGRESSION_MODEL, build_layout, fixed_layout, layout_entries,
    layout_from_slot_data, layout_slot_data, shuffled_layout, validate_layout,
)


class FixedLayoutTests(unittest.TestCase):
    def test_fixed_layout_preserves_canonical_order_but_has_layout_identity(self):
        manifest = campaign_for_level_set("discovery_labs")
        layout = fixed_layout(manifest, "discovery_labs")
        entries = layout_entries(manifest, layout)
        self.assertEqual(FIXED_ALGORITHM, layout.algorithm)
        self.assertEqual(PROGRESSION_MODEL, layout.progression_model)
        self.assertEqual(tuple(x.stable_key for x in manifest.levels), layout.ordered_stable_keys)
        self.assertEqual(list(range(40)), [entry.slot_index for entry in entries])
        self.assertEqual(list(range(40)), [entry.record.index for entry in entries])
        self.assertNotEqual(campaign_digest(manifest), layout.digest)

    def test_slot_data_round_trip_recalculates_digest(self):
        manifest = campaign_for_level_set("core_campaign")
        original = fixed_layout(manifest, "core_campaign")
        restored = layout_from_slot_data(manifest, "core_campaign", layout_slot_data(original))
        self.assertEqual(original, restored)

    def test_duplicate_order_and_tampered_digest_are_rejected(self):
        manifest = campaign_for_level_set("core_campaign")
        layout = fixed_layout(manifest, "core_campaign")
        duplicate = replace(layout, ordered_stable_keys=(layout.ordered_stable_keys[0],) * 30)
        with self.assertRaisesRegex(ValueError, "stable keys"):
            validate_layout(manifest, duplicate)
        payload = layout_slot_data(layout)
        payload["layout_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest"):
            layout_from_slot_data(manifest, "core_campaign", payload)


class ShuffledLayoutTests(unittest.TestCase):
    def test_build_layout_dispatches_only_supported_modes(self):
        manifest = campaign_for_level_set("core_campaign")
        self.assertEqual(
            fixed_layout(manifest, "core_campaign"),
            build_layout(manifest, "core_campaign", "fixed_pages", random.Random(9)),
        )
        self.assertEqual(
            shuffled_layout(manifest, "core_campaign", random.Random(9)),
            build_layout(manifest, "core_campaign", "shuffled_pages", random.Random(9)),
        )
        with self.assertRaisesRegex(ValueError, "mode"):
            build_layout(manifest, "core_campaign", "unknown", random.Random(9))

    def test_same_seed_is_identical_and_different_seeds_vary(self):
        manifest = campaign_for_level_set("discovery_labs")
        first = shuffled_layout(manifest, "discovery_labs", random.Random(1408))
        repeat = shuffled_layout(manifest, "discovery_labs", random.Random(1408))
        other = shuffled_layout(manifest, "discovery_labs", random.Random(1409))
        self.assertEqual(first, repeat)
        self.assertNotEqual(first.ordered_stable_keys, other.ordered_stable_keys)

    def test_constraints_hold_for_both_sets_across_200_seeds(self):
        for level_set in ("core_campaign", "discovery_labs"):
            manifest = campaign_for_level_set(level_set)
            records = {record.stable_key: record for record in manifest.levels}
            for seed in range(200):
                layout = shuffled_layout(manifest, level_set, random.Random(seed))
                pages = [layout.ordered_stable_keys[i:i + 6] for i in range(0, len(layout.ordered_stable_keys), 6)]
                self.assertTrue({"complete-i", "complete-c"} <= set(pages[0]))
                self.assertIn("pitchfork-final", pages[-1])
                self.assertFalse(any(records[key].kind in {"challenge", "discovery", "final"} for key in pages[0]))
                self.assertGreaterEqual(
                    sum(
                        "Merger2 Access"
                        not in unavoidable_nonbootstrap_machines(records[key])
                        for key in pages[0]
                    ),
                    4,
                )
                for page_index, page in enumerate(pages):
                    self.assertFalse(page_index < 2 and any(records[key].kind == "challenge" for key in page))
                    if len(page) == 6:
                        profiles = {unavoidable_nonbootstrap_machines(records[key]) for key in page}
                        self.assertGreaterEqual(len(profiles), 3)
                        for machine in FULL - {"Bender Access", "Merger2 Access"}:
                            count = sum(machine in unavoidable_nonbootstrap_machines(records[key]) for key in page)
                            self.assertLess(count, 4)
