import importlib
import random
import unittest

from word_factori.campaign import campaign_for_level_set


DEAD_ORDER = ('complete-c','complete-cat','complete-axolotl','complete-l','complete-i','complete-v',
              'complete-owl','complete-bald','complete-chef','complete-hack','complete-ax','complete-dragon',
              'challenge-cat-compact','challenge-book-low-cycles','challenge-phone-no-waste','complete-o','complete-ivy','complete-ox',
              'complete-jewel','complete-face','complete-rabbit','complete-voxel','complete-qi','complete-pixy',
              'complete-phone','complete-a','complete-book','complete-dinosaur','pitchfork-final','complete-doctor')


class QuantityLayoutTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('word_factori.quantity_layout'))
        self.logic=importlib.import_module('word_factori.quantity_layout')

    def test_real_core_seed_with_four_checks_but_no_fifth_is_rejected(self):
        records={r.stable_key:r for r in campaign_for_level_set('core_campaign').levels}
        self.assertIsNone(self.logic.upgrade_path(tuple(records[key] for key in DEAD_ORDER)))

    def test_witness_never_spends_more_upgrades_than_reachable_checks(self):
        records=campaign_for_level_set('core_campaign').levels
        path=self.logic.upgrade_path(records)
        self.assertIsNotNone(path)
        from word_factori.quantities import limits_for_counts, PROGRESSIVE_ITEMS
        from word_factori.quantity_logic import budgets_for_location
        from word_factori.quantities import affords
        counts={PROGRESSIVE_ITEMS[0]:1}
        for spent, item in enumerate(path):
            limits=limits_for_counts(counts); reached=0
            for i in range(0,len(records),6):
                page=sum(any(affords(limits,b) for b in budgets_for_location(r)) for r in records[i:i+6])
                reached+=page
                if page<4: break
            self.assertGreater(reached,spent)
            counts[item]=counts.get(item,0)+1
        self.assertEqual(29,len(path))
        self.assertEqual((-1,)*6,limits_for_counts(counts))

    def test_exhausted_search_is_not_reported_as_viable(self):
        self.assertIsNone(self.logic.upgrade_path(campaign_for_level_set('core_campaign').levels,max_states=0))

    def test_shuffler_accepts_only_viable_quantity_layouts(self):
        from word_factori.layout import build_layout
        for level_set in ('core_campaign','discovery_labs'):
            manifest=campaign_for_level_set(level_set)
            records={r.stable_key:r for r in manifest.levels}
            for seed in range(30):
                layout=build_layout(manifest,level_set,'shuffled_pages',random.Random(seed),
                                    integration_mode='enhanced',machine_only=True,progressive_machines=True)
                with self.subTest(level_set=level_set,seed=seed):
                    self.assertIsNotNone(self.logic.upgrade_path(tuple(records[k] for k in layout.ordered_stable_keys)))
