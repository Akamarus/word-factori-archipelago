import unittest
from word_factori.word_orders import normalize_word_list, WordOrder, orders_slot_data, orders_from_slot_data, word_requirement_options
from word_factori.quantity_logic import graphs_for_word, budgets_for_word
from word_factori.quantity_graphs import validate_graph, load_catalog
from word_factori.client_core import word_order_codes
from word_factori.save import _completed_words
from word_factori.quantities import affords

SPECIALS = "()#%$@+=&0123456789🔑🚪~"


class SymbolOrderTests(unittest.TestCase):
    def normalized(self, word):
        try:
            return normalize_word_list([word])
        except ValueError as error:
            self.fail(f"Supported native symbol rejected: {error}")

    def test_all_native_specials_and_letters_normalize_without_losing_symbols(self):
        for symbol in SPECIALS:
            with self.subTest(symbol=symbol):
                self.assertEqual(("I"+symbol,), self.normalized("i"+symbol))
        self.assertEqual(("A9🔑🚪",), self.normalized(" a9🔑🚪 "))

    def test_unknown_unicode_whitespace_and_unknown_recipe_are_rejected(self):
        for word in ("A?", "A!", "Aé", "A😀", "A B", "A\nB", "ßI", "I"*13):
            with self.subTest(word=word), self.assertRaises(ValueError):
                normalize_word_list([word])

    def test_every_symbol_has_verified_complete_factory_candidates(self):
        self.normalized("I=")
        catalog = load_catalog()
        for symbol in SPECIALS:
            with self.subTest(symbol=symbol):
                graphs = graphs_for_word("I"+symbol)
                self.assertTrue(graphs)
                self.assertTrue(word_requirement_options("I"+symbol))
                for graph in graphs:
                    validate_graph(graph, catalog.transitions)
                    self.assertEqual(2, len(graph.roots))

    def test_equal_sign_requires_rotation_and_merger_and_repeats_share(self):
        self.normalized("==")
        self.assertEqual((frozenset({"Rotation Access", "Merger2 Access"}),), word_requirement_options("=="))
        self.assertIn((0,1,0,1,0,0), budgets_for_word("=="))
        self.assertEqual(budgets_for_word("I="), budgets_for_word("=="))
        self.assertFalse(any(affords((4,0,4,4,4,4),b) for b in budgets_for_word("==")))
        self.assertFalse(any(affords((4,4,4,0,4,4),b) for b in budgets_for_word("==")))

    def test_missing_or_wrong_alias_witness_is_rejected(self):
        import copy
        import json
        from pathlib import Path
        from word_factori.quantity_graphs import catalog_from_payload, payload_digest
        payload = json.loads((Path(__file__).parents[1]/"word_factori/data/quantity_recipes.json").read_text())
        # Both cases retain a valid digest, so this checks the content validation.
        for change in ("missing", "wrong"):
            candidate = copy.deepcopy(payload)
            if change == "missing":
                del candidate["alphabet"]["9"]
            else:
                candidate["alphabet"]["9"] = candidate["alphabet"]["6"]
            candidate["digest"] = payload_digest({k:v for k,v in candidate.items() if k!="digest"})
            with self.subTest(change=change), self.assertRaises(ValueError):
                catalog_from_payload(candidate)

    def test_symbol_metadata_and_journal_round_trip_idempotently(self):
        self.normalized("A9🔑")
        orders = (WordOrder(1,"A9🔑"), WordOrder(2,"(=)"))
        self.assertEqual(orders, orders_from_slot_data(orders_slot_data(orders)))
        scores = {"buildings":10,"cycles":30,"extra_letters":0}
        completed = _completed_words({"A9🔑":scores,"(=)":scores})
        self.assertEqual(frozenset({975303000,975303001}), word_order_codes(completed, orders))
        self.assertEqual(word_order_codes(completed, orders), word_order_codes(completed, orders))
