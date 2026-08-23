import json
import unittest
from pathlib import Path
import tempfile

from word_factori.dispatch import DispatchDirection, DispatchEvent
from word_factori.overlay_model import (
    OverlayAction,
    OverlayFilter,
    OverlayState,
    apply_action,
    apply_events,
    snapshot,
)


def make_event(index: int, direction: DispatchDirection = DispatchDirection.RECEIVED) -> DispatchEvent:
    return DispatchEvent(
        key=str(index), direction=direction, item_id=index, item_name=f"Item {index}",
        other_slot=2, other_player="Alex", other_game="Example", location_id=index,
        location_name=f"Location {index}", receive_index=index, observed_at=None,
    )


class OverlayReducerTests(unittest.TestCase):
    def test_notification_queue_caps_visible_and_preserves_order(self):
        state = OverlayState.closed(max_visible=3)
        state = apply_events(state, tuple(make_event(index) for index in range(5)))
        self.assertEqual([event.key for event in snapshot(state).visible_notifications], ["0", "1", "2"])
        self.assertEqual([event.key for event in state.waiting_notifications], ["3", "4"])

    def test_opening_ledger_marks_read_and_dismisses_toasts(self):
        state = apply_events(OverlayState.closed(), (make_event(1),))
        state = apply_action(state, OverlayAction("open"))
        self.assertTrue(state.is_open)
        self.assertEqual(state.unread_count, 0)
        self.assertEqual(snapshot(state).visible_notifications, ())

    def test_filtering_includes_self_once_and_preserves_connection_state(self):
        events = (
            make_event(1, DispatchDirection.RECEIVED),
            make_event(2, DispatchDirection.SELF),
            make_event(3, DispatchDirection.SENT),
        )
        state = apply_events(OverlayState.closed(), events)
        state = apply_action(state, OverlayAction("connection-status", "connected"))
        state = apply_action(state, OverlayAction("reload-required", "true"))
        received = snapshot(apply_action(state, OverlayAction("filter", "received")), events)
        sent = snapshot(apply_action(state, OverlayAction("filter", "sent")), events)
        all_rows = snapshot(apply_action(state, OverlayAction("filter", "all")), events)
        self.assertEqual([row.key for row in received.ledger_rows], ["1", "2"])
        self.assertEqual([row.key for row in sent.ledger_rows], ["3"])
        self.assertEqual([row.key for row in all_rows.ledger_rows], ["1", "2", "3"])
        self.assertEqual(received.connection_status, "connected")
        self.assertTrue(received.reload_required)

    def test_focus_loss_hides_then_restore_preserves_toast_order(self):
        state = apply_events(OverlayState.closed(max_visible=2), tuple(make_event(index) for index in range(3)))
        hidden = snapshot(apply_action(state, OverlayAction("focus-lost")))
        restored = snapshot(apply_action(apply_action(state, OverlayAction("focus-lost")), OverlayAction("focus-returned")))
        self.assertEqual(hidden.visible_notifications, ())
        self.assertEqual([row.key for row in restored.visible_notifications], ["0", "1"])
        self.assertEqual([row.key for row in restored.waiting_notifications], ["2"])

    def test_expiring_named_toast_promotes_next_waiting_toast(self):
        state = apply_events(OverlayState.closed(max_visible=2), tuple(make_event(index) for index in range(3)))
        state = apply_action(state, OverlayAction("expire", "0"))
        current = snapshot(state)
        self.assertEqual([row.key for row in current.visible_notifications], ["1", "2"])
        self.assertEqual(current.waiting_notifications, ())

    def test_unknown_action_or_filter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "action"):
            apply_action(OverlayState.closed(), OverlayAction("execute"))
        with self.assertRaisesRegex(ValueError, "filter"):
            apply_action(OverlayState.closed(), OverlayAction("filter", "other"))


class OverlayProtocolTests(unittest.TestCase):
    def test_snapshot_message_round_trip_and_unknown_type_rejection(self):
        from word_factori.overlay_protocol import decode_parent_message, encode_parent_message, snapshot_message

        encoded = encode_parent_message(snapshot_message(snapshot(OverlayState.closed())))
        self.assertEqual(decode_parent_message(encoded).kind, "snapshot")
        with self.assertRaisesRegex(ValueError, "message type"):
            decode_parent_message('{"type":"execute"}')

    def test_protocol_rejects_extra_fields_bad_scalars_and_long_strings(self):
        from word_factori.overlay_protocol import decode_child_action, decode_parent_message

        with self.assertRaisesRegex(ValueError, "top-level"):
            decode_parent_message('{"version":1,"type":"shutdown","payload":{},"execute":true}')
        with self.assertRaisesRegex(ValueError, "payload"):
            decode_parent_message('{"version":1,"type":"shutdown","payload":{"value":1}}')
        with self.assertRaisesRegex(ValueError, "version"):
            decode_parent_message('{"version":true,"type":"shutdown","payload":{}}')
        with self.assertRaisesRegex(ValueError, "string"):
            decode_child_action('{"version":1,"type":"action","payload":{"kind":"open","value":"' + "x" * 8193 + '"}}')
        with self.assertRaisesRegex(ValueError, "action"):
            decode_child_action('{"version":1,"type":"action","payload":{"kind":"execute","value":null}}')

    def test_snapshot_payload_rejects_wrong_scalar_types(self):
        from word_factori.overlay_protocol import decode_parent_message, snapshot_message

        payload = dict(snapshot_message(snapshot(OverlayState.closed())).payload)
        payload["unread_count"] = True
        encoded = json.dumps({"version": 1, "type": "snapshot", "payload": payload})
        with self.assertRaisesRegex(ValueError, "unread_count"):
            decode_parent_message(encoded)


class OverlayPreferencesTests(unittest.TestCase):
    def test_preferences_round_trip_and_clamp_documented_ranges(self):
        from word_factori.overlay_preferences import OverlayPreferences, load_preferences, save_preferences

        preferences = OverlayPreferences(
            enabled=False, interface_scale=9.0, left_offset=-9999,
            notification_duration=0.25, reduced_motion=True, max_visible=99,
        )
        self.assertEqual(preferences.interface_scale, 2.0)
        self.assertEqual(preferences.left_offset, -2000)
        self.assertEqual(preferences.notification_duration, 1.0)
        self.assertEqual(preferences.max_visible, 10)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlay.json"
            save_preferences(path, preferences)
            self.assertEqual(load_preferences(path), preferences)
            self.assertEqual(tuple(path.parent.glob(f".{path.name}.*.tmp")), ())

    def test_preferences_reject_bad_types_and_load_recovers_defaults(self):
        from word_factori.overlay_preferences import OverlayPreferences, load_preferences

        with self.assertRaisesRegex(ValueError, "interface_scale"):
            OverlayPreferences(interface_scale=float("nan"))
        with self.assertRaisesRegex(ValueError, "left_offset"):
            OverlayPreferences(left_offset=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlay.json"
            path.write_text('{"version":2}', encoding="utf-8")
            self.assertEqual(load_preferences(path), OverlayPreferences())
            path.write_text('{"version":1,"preferences":{"enabled":"yes"}}', encoding="utf-8")
            self.assertEqual(load_preferences(path), OverlayPreferences())


if __name__ == "__main__":
    unittest.main()
