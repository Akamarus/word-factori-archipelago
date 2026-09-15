import math
from pathlib import Path
import tempfile
import unittest

from word_factori.bridge import BridgeState, reconcile
from word_factori import client_core
from word_factori.client_core import resolve_game_slot_binding
from word_factori.save import ActiveSlot, parse_active_slot, read_active_slot
from word_factori.word_orders import WordOrder


def active_slot(words):
    return parse_active_slot({"slots": {"0": {
        "slot_is_active": 1,
        "random_id": "game-slot-A",
        "beaten_levels": {},
        "words": words,
    }}})


class CompletedWordJournalTests(unittest.TestCase):
    def test_native_integer_valued_scores_and_zero_cycles_complete_normalized_words(self):
        import json
        payload = {"slots": {"0": {
            "slot_is_active": 1, "random_id": "game-slot-A", "beaten_levels": {},
            "words": {
                "II": {"buildings": 2.0, "cycles": 0.0, "extra_letters": 0.0},
            },
        }}}
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "save.json"
            fixture.write_text(json.dumps(payload), encoding="utf-8")

            self.assertEqual(read_active_slot(fixture).completed_words, frozenset({"II"}))

    def test_native_hard_and_unknown_score_identities_are_retained_but_do_not_match_orders(self):
        score = {"buildings": 4, "cycles": 10, "extra_letters": 2}
        completed = active_slot({"II_hard": score, "UNKNOWN!": score}).completed_words
        orders = (WordOrder(1, "II"),)

        self.assertEqual(frozenset({"II_hard", "UNKNOWN!"}), completed)
        self.assertEqual(frozenset(), client_core.word_order_codes(completed, orders))

    def test_empty_native_journal_is_valid(self):
        self.assertEqual(frozenset(), active_slot({}).completed_words)

    def test_missing_or_malformed_journal_is_unavailable(self):
        missing = parse_active_slot({"slots": {"0": {
            "slot_is_active": 1, "random_id": "r", "beaten_levels": {},
        }}})
        self.assertIsNone(missing.completed_words)

        invalid_scores = (
            True, -1, 0.5, math.inf, 9007199254740992,
        )
        for value in invalid_scores:
            with self.subTest(value=value):
                self.assertIsNone(active_slot({
                    "II": {"buildings": value, "cycles": 1, "extra_letters": 0},
                }).completed_words)
        for journal in (
            [],
            {"I" * 65: {"buildings": 1, "cycles": 1, "extra_letters": 0}},
            {"II": {"buildings": 1, "cycles": 1}},
            {"II": {"buildings": 1, "cycles": 1, "extra_letters": 0, "rank": 1}},
        ):
            with self.subTest(journal=journal):
                self.assertIsNone(active_slot(journal).completed_words)

    def test_native_journal_entry_count_is_bounded(self):
        score = {"buildings": 1, "cycles": 1, "extra_letters": 0}
        boundary = {f"UNKNOWN_{index}": score for index in range(10000)}
        journal = {f"UNKNOWN_{index}": score for index in range(10001)}

        self.assertEqual(10000, len(active_slot(boundary).completed_words))
        self.assertIsNone(active_slot(journal).completed_words)


class WordOrderBridgeTests(unittest.TestCase):
    def test_only_authoritative_selected_targets_map_to_static_order_codes(self):
        orders = (WordOrder(1, "II"), WordOrder(2, "JACK"))

        self.assertEqual(
            frozenset({orders[0].code}),
            client_core.word_order_codes(frozenset({"II", "UNKNOWN"}), orders),
        )

    def test_duplicate_reconciliation_is_idempotent(self):
        order = WordOrder(1, "II")
        first = reconcile(BridgeState.empty(), (), {order.code}, set())
        second = reconcile(first.state, (), {order.code}, {order.code})

        self.assertEqual(second.new_checks, frozenset())

    def test_fresh_order_binding_rejects_any_prior_word_and_unavailable_journal(self):
        with self.assertRaisesRegex(ValueError, "prior completions"):
            resolve_game_slot_binding(
                None,
                ActiveSlot("0", "r", frozenset(), frozenset(), frozenset({"UNKNOWN"})),
                word_checks=True,
            )
        with self.assertRaisesRegex(ValueError, "word journal"):
            resolve_game_slot_binding(
                None,
                ActiveSlot("0", "r", frozenset(), frozenset(), None),
                word_checks=True,
            )

    def test_old_or_orders_off_binding_does_not_require_word_journal(self):
        active = ActiveSlot("0", "r", frozenset(), frozenset(), None)

        self.assertEqual("r", resolve_game_slot_binding(None, active, word_checks=False))


if __name__ == "__main__":
    unittest.main()
