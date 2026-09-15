import importlib
import unittest

from word_factori.campaign import campaign_for_level_set
from word_factori.data import locations_for_manifest


class QuantityLogicTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('word_factori.quantity_logic'),
                             'Complete-word quantity logic is missing')
        self.logic = importlib.import_module('word_factori.quantity_logic')

    def test_repeated_c_requires_one_shared_bender(self):
        self.assertIn((1,0,0,0,0,0), self.logic.budgets_for_word('CC'))

    def test_c_and_v_require_both_transformations(self):
        self.assertIn((1,0,0,1,0,0), self.logic.budgets_for_word('CV'))
        self.assertNotIn((1,0,0,0,0,0), self.logic.budgets_for_word('CV'))

    def test_forbidden_family_does_not_produce_a_false_witness(self):
        self.assertEqual((), self.logic.budgets_for_word('A', allowed_families=frozenset({'Bender'})))

    def test_zero_native_module_cap_is_respected(self):
        self.assertEqual((), self.logic.budgets_for_word('C', (('Bend',0),), frozenset({'Bender'})))

    def test_every_campaign_location_has_a_restricted_full_inventory_witness(self):
        for location in locations_for_manifest(campaign_for_level_set('discovery_labs')):
            with self.subTest(location=location.name):
                self.assertTrue(self.logic.graphs_for_location(location), location.name)

    def test_word_roots_keep_order_and_repeated_ports(self):
        for graph in self.logic.graphs_for_word('CVC'):
            self.assertEqual(('C','V','C'), tuple(graph.nodes[i].output for i in graph.roots))

    def test_unknown_characters_fail_instead_of_becoming_free(self):
        for word in ('', 'A?', 'C C', 'c'):
            with self.subTest(word=word), self.assertRaises(ValueError):
                self.logic.budgets_for_word(word)


if __name__ == '__main__':
    unittest.main()
