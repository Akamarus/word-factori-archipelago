import unittest

from word_factori.dispatch import DispatchDirection, DispatchEvent, received_event, sent_event


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
            received_event("room", 0, 1, "Item", 2, "Alex", "Game", -3, "Location", None)
        with self.assertRaisesRegex(ValueError, "slot"):
            sent_event("room", 3, 1, "Item", -2, "Alex", "Game", "Location", False, None)


if __name__ == "__main__":
    unittest.main()
