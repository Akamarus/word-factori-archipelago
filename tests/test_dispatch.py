import json
from pathlib import Path
import tempfile
import unittest

from word_factori.dispatch import DispatchDirection, DispatchEvent, received_event, sent_event


def make_received(index: int, *, self_item: bool = False) -> DispatchEvent:
    return received_event("room", index, index + 1, f"Received {index}", 2, "Alex", "Game",
                          index + 100, f"Location {index}", None, self_item)


def make_sent(index: int, *, self_item: bool = False) -> DispatchEvent:
    return sent_event("room", index + 100, index + 1, f"Sent {index}", 3, "Sam", "Game",
                      f"Location {index}", self_item, None)


class DispatchEventTests(unittest.TestCase):
    def test_received_key_uses_room_and_receive_index(self):
        event = received_event(
            identity="Seed-A-team-0-slot-1-Factory",
            receive_index=4,
            item_id=7001,
            item_name="Rotation Access",
            source_slot=2,
            source_name="Alex",
            source_game="Celeste",
            location_id=9001,
            location_name="Forsaken City",
            observed_at="2026-08-23T12:00:00Z",
        )
        self.assertEqual(event.key, "Seed-A-team-0-slot-1-Factory:receive:4")
        self.assertIs(event.direction, DispatchDirection.RECEIVED)

    def test_sent_and_self_events_have_stable_location_keys(self):
        sent = sent_event("room", 975301000, 42, "Hookshot", 3, "Sam", "Ocarina of Time", "Complete I", False, None)
        own = sent_event("room", 975301000, 7001, "Rotation Access", 1, "Factory", "Word Factori", "Complete I", True, None)
        self.assertEqual(sent.key, "room:send:975301000:42:3")
        self.assertIs(sent.direction, DispatchDirection.SENT)
        self.assertIs(own.direction, DispatchDirection.SELF)

    def test_dispatch_event_is_immutable(self):
        event = sent_event("room", 975301000, 42, "Hookshot", 3, "Sam", "Ocarina of Time", "Complete I", False, None)
        with self.assertRaises((AttributeError, TypeError)):
            event.item_name = "Changed"

    def test_event_constructors_reject_invalid_identity_and_index(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            received_event("", 0, 1, "Item", 2, "Alex", "Game", 3, "Location", None)
        with self.assertRaisesRegex(ValueError, "receive index"):
            received_event("room", -1, 1, "Item", 2, "Alex", "Game", 3, "Location", None)

    def test_event_constructors_reject_blank_display_text(self):
        with self.assertRaisesRegex(ValueError, "item_name"):
            sent_event("room", 3, 1, " ", 2, "Alex", "Game", "Location", False, None)
        with self.assertRaisesRegex(ValueError, "recipient_name"):
            sent_event("room", 3, 1, "Item", 2, "", "Game", "Location", False, None)

    def test_event_constructors_reject_negative_integer_fields(self):
        with self.assertRaisesRegex(ValueError, "item_id"):
            sent_event("room", 3, -1, "Item", 2, "Alex", "Game", "Location", False, None)
        with self.assertRaisesRegex(ValueError, "location_id"):
            sent_event("room", -3, 1, "Item", 2, "Alex", "Game", "Location", False, None)
        with self.assertRaisesRegex(ValueError, "slot"):
            sent_event("room", 3, 1, "Item", -2, "Alex", "Game", "Location", False, None)

    def test_received_event_accepts_archipelago_synthetic_location_sentinel(self):
        try:
            event = received_event(
                "room", 0, 1, "Rotation Access", 0, "Cheat Console", "Archipelago",
                -2, "Cheat Console", "2026-08-23T13:43:30Z",
            )
        except ValueError as error:
            self.fail(f"synthetic Archipelago locations must be accepted: {error}")

        self.assertEqual(-2, event.location_id)
        self.assertEqual("Cheat Console", event.location_name)


class DispatchLedgerTests(unittest.TestCase):
    def test_first_authoritative_sync_is_historical_and_silent(self):
        from word_factori.dispatch_store import DispatchLedger, reconcile_received
        events = (make_received(0), make_received(1))
        update = reconcile_received(DispatchLedger.empty("room"), events)
        self.assertEqual(update.historical_count, 2)
        self.assertEqual(update.notify, ())
        self.assertTrue(update.state.initialized)
        self.assertTrue(all(event.historical for event in update.state.events))
        self.assertTrue(all(event.observed_at is None for event in update.state.events))

    def test_reconciliation_retains_stored_observation_for_matching_key(self):
        from word_factori.dispatch_store import DispatchLedger, reconcile_received
        stored = received_event(
            "room", 0, 1, "Received 0", 2, "Alex", "Game", 100, "Location 0",
            "2026-08-23T12:00:00Z",
        )
        state = DispatchLedger("room", (stored,), frozenset(), True, 0)
        replay = received_event(
            "room", 0, 1, "Received 0", 2, "Alex", "Game", 100, "Location 0",
            "2026-08-23T13:00:00Z",
        )
        update = reconcile_received(state, (replay,))
        self.assertIs(stored, update.state.events[0])
        self.assertEqual("2026-08-23T12:00:00Z", update.state.events[0].observed_at)

    def test_incremental_receive_notifies_once(self):
        from word_factori.dispatch_store import DispatchLedger, reconcile_received
        first = reconcile_received(DispatchLedger.empty("room"), (make_received(0),)).state
        update = reconcile_received(first, (make_received(0), make_received(1)))
        self.assertEqual(tuple(event.receive_index for event in update.notify), (1,))
        again = reconcile_received(update.state, (make_received(0), make_received(1)))
        self.assertEqual(again.notify, ())

    def test_identical_authoritative_duplicates_collapse_on_incremental_and_replay(self):
        from word_factori.dispatch_store import DispatchLedger, reconcile_received
        first = reconcile_received(DispatchLedger.empty("room"), (make_received(0), make_received(0)))
        self.assertEqual(tuple(event.receive_index for event in first.state.events), (0,))
        self.assertEqual(first.historical_count, 1)
        update = reconcile_received(first.state, (make_received(0), make_received(1), make_received(1)))
        self.assertEqual(tuple(event.receive_index for event in update.notify), (1,))
        replay = reconcile_received(update.state, (make_received(0), make_received(0), make_received(1)))
        self.assertEqual(replay.notify, ())

    def test_conflicting_authoritative_duplicate_receive_is_rejected(self):
        from word_factori.dispatch_store import DispatchLedger, reconcile_received
        conflict = received_event("room", 1, 999, "Different", 2, "Alex", "Game", 101, "Location 1", None)
        with self.assertRaisesRegex(ValueError, "conflicting authoritative"):
            reconcile_received(DispatchLedger.empty("room"), (make_received(1), conflict))

    def test_record_event_deduplicates_and_caps_history(self):
        from word_factori.dispatch_store import DispatchLedger, record_event
        state = DispatchLedger.empty("room")
        for index in range(205):
            state = record_event(state, make_sent(index), notify=True).state
        self.assertEqual(len(state.events), 200)
        duplicate = record_event(state, state.events[-1], notify=True)
        self.assertEqual(duplicate.notify, ())

    def test_mark_all_read_clears_only_unread_keys(self):
        from word_factori.dispatch_store import DispatchLedger, mark_all_read, record_event
        state = record_event(DispatchLedger.empty("room"), make_sent(1), notify=True).state
        self.assertEqual(mark_all_read(state).unread_keys, frozenset())
        self.assertEqual(mark_all_read(state).events, state.events)

    def test_authoritative_self_receive_replaces_live_self_row(self):
        from word_factori.dispatch_store import DispatchLedger, reconcile_received, record_event
        live = record_event(DispatchLedger.empty("room"), make_sent(7, self_item=True), notify=True).state
        update = reconcile_received(live, (make_received(7, self_item=True),))
        self.assertEqual(tuple(event.key for event in update.state.events), ("room:receive:7",))
        self.assertEqual(update.state.events[0].direction, DispatchDirection.SELF)

    def test_authoritative_receive_removes_stale_rows(self):
        from word_factori.dispatch_store import DispatchLedger, reconcile_received
        initial = reconcile_received(DispatchLedger.empty("room"), (make_received(0), make_received(1))).state
        update = reconcile_received(initial, (make_received(1),))
        self.assertEqual(tuple(event.receive_index for event in update.state.events), (1,))

    def test_unread_keys_track_retained_events_after_reconciliation_and_trimming(self):
        from word_factori.dispatch_store import DispatchLedger, reconcile_received, record_event
        initial = reconcile_received(DispatchLedger.empty("room"), (make_received(0),)).state
        notified = reconcile_received(initial, (make_received(0), make_received(1))).state
        reconciled = reconcile_received(notified, (make_received(0),)).state
        self.assertEqual(reconciled.unread_keys, frozenset())

        state = DispatchLedger.empty("room")
        for index in range(201):
            state = record_event(state, make_sent(index), notify=True).state
        self.assertEqual(state.unread_keys, frozenset(event.key for event in state.events))

    def test_shorter_authoritative_replay_never_lowers_high_water_or_rearms_notifications(self):
        from word_factori.dispatch_store import DispatchLedger, reconcile_received
        initial = reconcile_received(DispatchLedger.empty("room"), tuple(make_received(index) for index in range(6))).state
        shorter = reconcile_received(initial, tuple(make_received(index) for index in range(4))).state
        replay = reconcile_received(shorter, tuple(make_received(index) for index in range(6)))
        self.assertEqual(shorter.received_high_water, 5)
        self.assertEqual(replay.notify, ())
        self.assertEqual(replay.state.received_high_water, 5)

    def test_ledger_round_trip_and_corruption_recovery(self):
        from word_factori.dispatch_store import DispatchLedger, load_ledger, reconcile_received, record_event, save_ledger
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            received = reconcile_received(DispatchLedger.empty("room"), (make_received(1),)).state
            state = record_event(received, make_sent(2), notify=True).state
            save_ledger(path, state)
            self.assertEqual(load_ledger(path, "room"), state)
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ledger"):
                load_ledger(path, "room")

    def test_synthetic_received_location_survives_ledger_round_trip(self):
        from word_factori.dispatch_store import DispatchLedger, load_ledger, save_ledger
        event = received_event(
            "room", 0, 1, "Rotation Access", 0, "Cheat Console", "Archipelago",
            -2, "Cheat Console", "2026-08-23T13:43:30Z",
        )
        state = DispatchLedger("room", (event,), frozenset((event.key,)), True, 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"

            save_ledger(path, state)

            try:
                restored = load_ledger(path, "room")
            except ValueError as error:
                self.fail(f"synthetic received locations must persist: {error}")
            self.assertEqual(state, restored)

    def test_ledger_rejects_unknown_version_and_wrong_room_identity(self):
        from word_factori.dispatch_store import DispatchLedger, load_ledger, save_ledger
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            save_ledger(path, DispatchLedger.empty("room"))
            with self.assertRaisesRegex(ValueError, "identity"):
                load_ledger(path, "another-room")
            path.write_text(json.dumps({"version": 2, "identity": "room", "events": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "version"):
                load_ledger(path, "room")

    def test_corrupt_persisted_schema_is_rejected(self):
        from word_factori.dispatch_store import DispatchLedger, load_ledger, reconcile_received, record_event, save_ledger
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            received = reconcile_received(DispatchLedger.empty("room"), (make_received(2),)).state
            state = record_event(received, make_sent(3), notify=True).state
            save_ledger(path, state)
            valid_payload = json.loads(path.read_text(encoding="utf-8"))

            for version in (True, 1.0):
                payload = json.loads(json.dumps(valid_payload))
                payload["version"] = version
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "ledger"):
                    load_ledger(path, "room")

            payload = json.loads(json.dumps(valid_payload))
            payload["events"].append(dict(payload["events"][0]))
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ledger"):
                load_ledger(path, "room")

            payload = json.loads(json.dumps(valid_payload))
            payload["events"][0]["key"] = "room:receive:99"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ledger"):
                load_ledger(path, "room")

            payload = json.loads(json.dumps(valid_payload))
            payload["events"][1]["receive_index"] = 3
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ledger"):
                load_ledger(path, "room")

            payload = json.loads(json.dumps(valid_payload))
            payload["unread_keys"].append("room:missing")
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ledger"):
                load_ledger(path, "room")

            payload = json.loads(json.dumps(valid_payload))
            payload["received_high_water"] = 1
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ledger"):
                load_ledger(path, "room")


if __name__ == "__main__":
    unittest.main()
