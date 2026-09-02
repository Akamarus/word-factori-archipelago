from dataclasses import replace
import unittest

from word_factori.campaign import campaign_digest, campaign_for_level_set
from word_factori.layout import (
    FIXED_ALGORITHM, PROGRESSION_MODEL, fixed_layout, layout_entries,
    layout_from_slot_data, layout_slot_data, validate_layout,
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
