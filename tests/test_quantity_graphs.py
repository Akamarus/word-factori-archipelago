import importlib
import json
from pathlib import Path
import unittest

from word_factori.recipe_checks import RECIPE_CHECKS


class QuantityGraphTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('word_factori.quantity_graphs'),
                             'Constructive quantity graphs are missing')
        self.g = importlib.import_module('word_factori.quantity_graphs')
        self.source = self.g.Node('oIFactory', 'I', ())
        self.c = self.g.FactoryGraph((self.source, self.g.Node('oBend', 'C', (0,))), (1,))
        self.v = self.g.FactoryGraph((self.source, self.g.Node('oMerger2', 'V', (0,0))), (1,))
        self.edges = frozenset({('oBend', ('I',), 'C'), ('oMerger2', ('I','I'), 'V')})

    def test_repeated_letters_share_a_producer_not_a_target_port(self):
        merged = self.g.merge_graphs((self.c, self.c))
        self.assertEqual((1,0,0,0,0,0), self.g.graph_budget(merged))
        self.assertEqual((1,1), merged.roots)
        self.g.validate_graph(merged, self.edges)

    def test_distinct_producers_are_not_replaced_by_maximum_budget(self):
        merged = self.g.merge_graphs((self.c, self.v))
        self.assertEqual((1,0,0,1,0,0), self.g.graph_budget(merged))
        self.assertEqual(('C','V'), tuple(merged.nodes[i].output for i in merged.roots))
        self.assertEqual(3, len(merged.nodes))

    def test_validate_rejects_wrong_native_transition(self):
        bad = self.g.FactoryGraph((self.source, self.g.Node('oBend','A',(0,))), (1,))
        with self.assertRaises(ValueError):
            self.g.validate_graph(bad, self.edges)

    def test_validate_rejects_forward_cycle_wrong_arity_and_injected_letter(self):
        cases = (
            self.g.FactoryGraph((self.source,self.g.Node('oBend','C',(1,))), (1,)),
            self.g.FactoryGraph((self.source,self.g.Node('oMerger2','V',(0,))), (1,)),
            self.g.FactoryGraph((self.g.Node('oIFactory','C',()),), (0,)),
        )
        for graph in cases:
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                self.g.validate_graph(graph, self.edges)

    def test_same_output_from_different_operations_is_not_auto_shared(self):
        other = self.g.FactoryGraph((self.source, self.g.Node('oRotate_cw','C',(0,))), (1,))
        merged = self.g.merge_graphs((self.c, other))
        self.assertEqual((1,1,0,0,0,0), self.g.graph_budget(merged))

    def test_catalog_preserves_all_recipe_identities_and_validates_every_graph(self):
        catalog = self.g.load_catalog()
        self.assertEqual({check.code for check in RECIPE_CHECKS}, set(catalog.recipes))
        self.assertEqual(set('ABCDEFGHIJKLMNOPQRSTUVWXYZ()#%$@+=&0123456789🔑🚪~'), set(catalog.alphabet))
        for alternatives in (*catalog.recipes.values(), *catalog.alphabet.values()):
            self.assertTrue(alternatives)
            for graph in alternatives:
                self.g.validate_graph(graph, catalog.transitions)

    def test_catalog_rejects_corruption_even_with_valid_json(self):
        raw = json.loads(Path(self.g.__file__).with_name('data').joinpath('quantity_recipes.json').read_text())
        raw['alphabet']['C'][0]['nodes'][-1]['output'] = 'A'
        with self.assertRaises(ValueError):
            self.g.catalog_from_payload(raw)


if __name__ == '__main__':
    unittest.main()
