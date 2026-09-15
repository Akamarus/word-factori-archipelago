import importlib
import unittest

from word_factori.bridge import BridgeState, ReceivedItem, reconcile


class QuantityTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('word_factori.quantities'),
                             'The shared quantity implementation is missing')
        self.q = importlib.import_module('word_factori.quantities')

    def test_tiers_and_unlimited_saturate(self):
        for received, expected in ((0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, -1), (6, -1)):
            with self.subTest(received=received):
                self.assertEqual((0, expected, 0, 0, 0, 0), self.q.limits_for_counts(
                    {'Progressive Rotation Access': received}))

    def test_bootstrap_is_explicit_not_double_counted(self):
        self.assertEqual((1, 0, 0, 0, 0, 0), self.q.limits_for_counts({}, bootstrap=True))
        self.assertEqual((1, 0, 0, 0, 0, 0), self.q.limits_for_counts({'Progressive Bender Access': 1}))
        self.assertEqual((2, 0, 0, 0, 0, 0), self.q.limits_for_counts(
            {'Progressive Bender Access': 1}, bootstrap=True))

    def test_legacy_items_do_not_grant_progressive_tiers(self):
        self.assertEqual((0, 0, 0, 0, 0, 0), self.q.limits_for_counts({'Bender Access': 1}))

    def test_invalid_inventory_does_not_grant_access(self):
        for invalid in (-1, True, 1.5, '5', None, 2**53):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.q.limits_for_counts({'Progressive Bender Access': invalid})

    def test_affordability_uses_whole_vector(self):
        self.assertFalse(self.q.affords((1, 2, 0, 0, 0, 0), (2, 1, 0, 0, 0, 0)))
        self.assertTrue(self.q.affords((2, 1, 0, 0, 0, 0), (2, 1, 0, 0, 0, 0)))
        self.assertTrue(self.q.affords((-1, 0, 0, 0, 0, 0), (500, 0, 0, 0, 0, 0)))
        self.assertFalse(self.q.affords((4, 0, 0, 0, 0, 0), (5, 0, 0, 0, 0, 0)))

    def test_malformed_vectors_fail_closed(self):
        for invalid in ((1,), (True,0,0,0,0,0), (5,0,0,0,0,0), (-2,0,0,0,0,0)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.q.affords(invalid, (0,0,0,0,0,0))
        with self.assertRaises(ValueError):
            self.q.affords((-1,0,0,0,0,0), (-1,0,0,0,0,0))

    def test_missing_upgrade_counts_include_unlimited_tier(self):
        self.assertEqual((1, 2, 0, 0, 0, 0), self.q.missing_tiers(
            (4, 1, -1, 0, 0, 0), (12, 3, 20, 0, 0, 0)))

    def test_direction_variants_share_placement_budget(self):
        self.assertEqual((0,2,2,0,0,0), self.q.placed_counts(
            ['Rotate_cw', 'oRotate_ccw', 'Reflect_hor', 'oReflect_vert']))

    def test_source_and_receiver_are_free_but_unknown_modules_rejected(self):
        self.assertEqual((1,0,0,1,0,0), self.q.placed_counts(
            ['IFactory', 'oFinalWord', 'Bend', 'Merger2']))
        with self.assertRaises(ValueError):
            self.q.placed_counts(['CustomBuilding'])

    def test_duplicate_deliveries_and_reconnect_do_not_increment_tiers(self):
        name = 'Progressive Merger2 Access'
        first = reconcile(BridgeState.empty(), [ReceivedItem(0,name), ReceivedItem(1,name)], set(), set()).state
        replay = reconcile(first, [ReceivedItem(1,name)], set(), set()).state
        reconnect = reconcile(replay, [ReceivedItem(0,name), ReceivedItem(1,name)], set(), set(), authoritative=True).state
        for state in (first,replay,reconnect):
            self.assertEqual((0,0,0,2,0,0), self.q.limits_for_counts(state.item_counts))


if __name__ == '__main__':
    unittest.main()
