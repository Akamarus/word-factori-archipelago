import json
import unittest
from pathlib import Path
import tempfile
from unittest import mock

from word_factori.dispatch import DispatchDirection, DispatchEvent
from word_factori.overlay_model import (
    OverlayAction,
    OverlayFilter,
    OverlayState,
    OverlayView,
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
    def test_keyboard_focus_exists_only_in_open_input_views(self):
        state = OverlayState.closed()
        self.assertFalse(snapshot(state).accepts_keyboard)

        state = apply_action(state, OverlayAction("open-chat"))
        self.assertTrue(state.is_open)
        self.assertIs(OverlayView.CHAT, state.active_view)
        self.assertTrue(snapshot(state).accepts_keyboard)

        state = apply_action(state, OverlayAction("close"))
        self.assertFalse(state.input_focused)
        self.assertFalse(snapshot(state).accepts_keyboard)

    def test_items_connect_and_password_views_have_explicit_focus_contract(self):
        items = apply_action(OverlayState.closed(), OverlayAction("open-items"))
        connect = apply_action(items, OverlayAction("open-connect"))
        password = apply_action(connect, OverlayAction("request-password"))

        self.assertIs(OverlayView.ITEMS, items.active_view)
        self.assertFalse(snapshot(items).accepts_keyboard)
        self.assertIs(OverlayView.CONNECT, connect.active_view)
        self.assertTrue(snapshot(connect).accepts_keyboard)
        self.assertIs(OverlayView.PASSWORD, password.active_view)
        self.assertTrue(snapshot(password).accepts_keyboard)

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
        with self.assertRaisesRegex(ValueError, "value"):
            apply_action(OverlayState.closed(), OverlayAction("open", "extra"))

    def test_open_snapshot_keeps_reducer_read_state_when_ledger_is_unread(self):
        from word_factori.dispatch_store import DispatchLedger

        event = make_event(1)
        state = apply_action(apply_events(OverlayState.closed(), (event,)), OverlayAction("open"))
        ledger = DispatchLedger("room", (event,), frozenset((event.key,)))
        self.assertEqual(snapshot(state, ledger).unread_count, 0)

    def test_notifications_are_deduplicated_within_batch_and_after_expire_or_open(self):
        event = make_event(1)
        state = apply_events(OverlayState.closed(), (event, event))
        self.assertEqual([row.key for row in snapshot(state).visible_notifications], ["1"])
        expired = apply_action(state, OverlayAction("expire", "1"))
        reopened = apply_action(apply_action(expired, OverlayAction("open")), OverlayAction("close"))
        replay = apply_events(reopened, (event,))
        self.assertEqual(snapshot(replay).visible_notifications, ())
        self.assertEqual(replay.accepted_notification_keys, frozenset(("1",)))

    def test_direct_state_construction_rejects_mutable_or_inconsistent_values(self):
        with self.assertRaisesRegex(ValueError, "visible_notifications"):
            OverlayState(visible_notifications=[make_event(1)])
        with self.assertRaisesRegex(ValueError, "max_visible"):
            OverlayState(max_visible=0)
        with self.assertRaisesRegex(ValueError, "unread_count"):
            OverlayState(unread_count=True)
        with self.assertRaisesRegex(ValueError, "connection_status"):
            OverlayState(connection_status=[])

    def test_snapshot_requires_validated_matching_preferences(self):
        from word_factori.overlay_preferences import OverlayPreferences

        state = OverlayState.closed(max_visible=2)
        with self.assertRaisesRegex(ValueError, "preferences"):
            snapshot(state, preferences=object())
        with self.assertRaisesRegex(ValueError, "max_visible"):
            snapshot(state, preferences=OverlayPreferences(max_visible=3))
        self.assertEqual(snapshot(state, preferences=OverlayPreferences(max_visible=2)).max_visible, 2)

    def test_events_arriving_while_open_are_accepted_but_remain_read_and_unqueued(self):
        state = apply_action(OverlayState.closed(), OverlayAction("open"))
        state = apply_events(state, (make_event(1),))
        self.assertEqual(state.accepted_notification_keys, frozenset(("1",)))
        self.assertEqual(state.unread_count, 0)
        self.assertEqual(state.visible_notifications, ())
        self.assertEqual(state.waiting_notifications, ())

    def test_open_state_rejects_queued_or_unread_presentation(self):
        event = make_event(1)
        with self.assertRaisesRegex(ValueError, "open"):
            OverlayState(is_open=True, visible_notifications=(event,), accepted_notification_keys=frozenset((event.key,)))
        with self.assertRaisesRegex(ValueError, "open"):
            OverlayState(is_open=True, unread_count=1)


class OverlayProtocolTests(unittest.TestCase):
    def test_version_two_decodes_bounded_full_client_intents(self):
        from word_factori.overlay_protocol import (
            ConnectIntent,
            DisconnectIntent,
            PasswordIntent,
            SubmitTextIntent,
            decode_child_action,
        )

        connect = decode_child_action(json.dumps({
            "version": 2,
            "type": "connect",
            "payload": {
                "generation": 4,
                "address": "archipelago.gg:38281",
                "slot": "Factory",
                "password": "secret",
            },
        }))
        self.assertEqual(
            ConnectIntent("archipelago.gg:38281", "Factory", "secret", 4), connect,
        )
        self.assertEqual(
            DisconnectIntent(4),
            decode_child_action('{"version":2,"type":"disconnect","payload":{"generation":4}}'),
        )
        self.assertEqual(
            SubmitTextIntent("hello", 4),
            decode_child_action('{"version":2,"type":"submit-text","payload":{"generation":4,"text":"hello"}}'),
        )
        self.assertEqual(
            PasswordIntent("secret", 4),
            decode_child_action('{"version":2,"type":"submit-password","payload":{"generation":4,"password":"secret"}}'),
        )

    def test_full_client_intents_are_bounded_and_passwords_never_enter_parent_messages(self):
        from word_factori.overlay_protocol import (
            ParentMessage,
            decode_child_action,
            encode_parent_message,
        )

        with self.assertRaisesRegex(ValueError, "address"):
            decode_child_action(json.dumps({
                "version": 2, "type": "connect", "payload": {
                    "generation": 0, "address": "x" * 513, "slot": "Factory", "password": None,
                },
            }))
        with self.assertRaisesRegex(ValueError, "text"):
            decode_child_action(json.dumps({
                "version": 2, "type": "submit-text", "payload": {
                    "generation": 0, "text": "x" * 4097,
                },
            }))
        with self.assertRaisesRegex(ValueError, "password") as caught:
            encode_parent_message(ParentMessage("snapshot", {"password": "do-not-echo"}))
        self.assertNotIn("do-not-echo", str(caught.exception))

    def test_version_one_item_only_action_remains_compatible(self):
        from word_factori.overlay_protocol import (
            decode_child_action,
            decode_parent_message,
            snapshot_message,
        )

        encoded = '{"version":1,"type":"action","payload":{"generation":7,"kind":"open","value":null}}'
        self.assertEqual(OverlayAction("open", generation=7), decode_child_action(encoded))

        legacy_payload = dict(snapshot_message(snapshot(OverlayState.closed())).payload)
        del legacy_payload["active_view"]
        del legacy_payload["accepts_keyboard"]
        legacy_snapshot = json.dumps({
            "version": 1, "type": "snapshot", "payload": legacy_payload,
        })
        self.assertEqual("snapshot", decode_parent_message(legacy_snapshot).kind)

    def test_snapshot_and_child_actions_carry_strict_nonnegative_generation(self):
        from word_factori.overlay_protocol import (
            decode_child_action, decode_parent_message, encode_parent_message, snapshot_message,
        )

        self.assertEqual(4, snapshot(OverlayState.closed(), generation=4).generation)
        with self.assertRaises(ValueError):
            snapshot(OverlayState.closed(), generation=True)
        with self.assertRaises(ValueError):
            snapshot(OverlayState.closed(), generation=-1)

        snapshot_payload = json.loads(encode_parent_message(
            snapshot_message(snapshot(OverlayState.closed(), generation=3)),
        ))
        self.assertEqual(3, snapshot_payload["payload"]["generation"])
        for generation in (None, True, -1):
            invalid_snapshot = json.loads(json.dumps(snapshot_payload))
            if generation is None:
                del invalid_snapshot["payload"]["generation"]
            else:
                invalid_snapshot["payload"]["generation"] = generation
            with self.subTest(snapshot_generation=generation), self.assertRaises(ValueError):
                decode_parent_message(json.dumps(invalid_snapshot))
        invalid_snapshot = json.loads(json.dumps(snapshot_payload))
        invalid_snapshot["payload"]["extra_generation"] = 3
        with self.assertRaises(ValueError):
            decode_parent_message(json.dumps(invalid_snapshot))

        encoded = '{"version":1,"type":"action","payload":{"generation":7,"kind":"open","value":null}}'
        self.assertEqual(OverlayAction("open", generation=7), decode_child_action(encoded))
        invalid = (
            '{"version":1,"type":"action","payload":{"kind":"open","value":null}}',
            '{"version":1,"type":"action","payload":{"generation":true,"kind":"open","value":null}}',
            '{"version":1,"type":"action","payload":{"generation":-1,"kind":"open","value":null}}',
            '{"version":1,"type":"action","payload":{"generation":0,"kind":"open","value":null,"extra":1}}',
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_child_action(value)

    def test_snapshot_message_round_trip_and_unknown_type_rejection(self):
        from word_factori.overlay_protocol import decode_parent_message, encode_parent_message, snapshot_message

        encoded = encode_parent_message(snapshot_message(snapshot(OverlayState.closed())))
        self.assertEqual(decode_parent_message(encoded).kind, "snapshot")
        with self.assertRaisesRegex(ValueError, "message type"):
            decode_parent_message('{"type":"execute"}')

    def test_snapshot_protocol_accepts_synthetic_received_location_sentinel(self):
        from word_factori.overlay_protocol import decode_parent_message, encode_parent_message, snapshot_message
        event = DispatchEvent(
            key="room:receive:0", direction=DispatchDirection.RECEIVED,
            item_id=1, item_name="Rotation Access", other_slot=0,
            other_player="Cheat Console", other_game="Archipelago",
            location_id=-2, location_name="Cheat Console", receive_index=0,
            observed_at="2026-08-23T13:43:30Z",
        )
        state = apply_events(OverlayState.closed(), (event,))

        try:
            message = decode_parent_message(encode_parent_message(snapshot_message(snapshot(state))))
        except ValueError as error:
            self.fail(f"synthetic received locations must reach the renderer: {error}")
        self.assertEqual(-2, message.payload["visible_notifications"][0]["location_id"])

    def test_protocol_rejects_extra_fields_bad_scalars_and_long_strings(self):
        from word_factori.overlay_protocol import decode_child_action, decode_parent_message

        with self.assertRaisesRegex(ValueError, "top-level"):
            decode_parent_message('{"version":1,"type":"shutdown","payload":{},"execute":true}')
        with self.assertRaisesRegex(ValueError, "payload"):
            decode_parent_message('{"version":1,"type":"shutdown","payload":{"value":1}}')
        with self.assertRaisesRegex(ValueError, "version"):
            decode_parent_message('{"version":true,"type":"shutdown","payload":{}}')
        with self.assertRaisesRegex(ValueError, "string"):
            decode_child_action('{"version":1,"type":"action","payload":{"generation":0,"kind":"open","value":"' + "x" * 8193 + '"}}')
        with self.assertRaisesRegex(ValueError, "action"):
            decode_child_action('{"version":1,"type":"action","payload":{"generation":0,"kind":"execute","value":null}}')

    def test_snapshot_payload_rejects_wrong_scalar_types(self):
        from word_factori.overlay_protocol import PROTOCOL_VERSION, decode_parent_message, snapshot_message

        payload = dict(snapshot_message(snapshot(OverlayState.closed())).payload)
        payload["unread_count"] = True
        encoded = json.dumps({"version": PROTOCOL_VERSION, "type": "snapshot", "payload": payload})
        with self.assertRaisesRegex(ValueError, "unread_count"):
            decode_parent_message(encoded)

    def test_child_actions_reject_values_the_reducer_would_reject(self):
        from word_factori.overlay_protocol import decode_child_action

        cases = (
            '{"version":1,"type":"action","payload":{"generation":0,"kind":"open","value":"extra"}}',
            '{"version":1,"type":"action","payload":{"generation":0,"kind":"filter","value":"other"}}',
            '{"version":1,"type":"action","payload":{"generation":0,"kind":"expire","value":" "}}',
            '{"version":1,"type":"action","payload":{"generation":0,"kind":"reload-required","value":"yes"}}',
            '{"version":1,"type":"action","payload":{"generation":0,"kind":"connection-status","value":"offline"}}',
        )
        for encoded in cases:
            with self.subTest(encoded=encoded), self.assertRaisesRegex(ValueError, "action"):
                decode_child_action(encoded)

    def test_action_validation_rejects_unhashable_connection_status_with_value_error(self):
        with self.assertRaisesRegex(ValueError, "connection"):
            apply_action(OverlayState.closed(), OverlayAction("connection-status", []))

    def test_snapshot_protocol_rejects_unknown_connection_status(self):
        from word_factori.overlay_protocol import PROTOCOL_VERSION, decode_parent_message, snapshot_message

        payload = dict(snapshot_message(snapshot(OverlayState.closed())).payload)
        payload["connection_status"] = "offline"
        with self.assertRaisesRegex(ValueError, "connection_status"):
            decode_parent_message(json.dumps({
                "version": PROTOCOL_VERSION, "type": "snapshot", "payload": payload,
            }))


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

    def test_preference_atomic_write_cleans_temporary_file_when_replacement_fails(self):
        from word_factori.overlay_preferences import OverlayPreferences, save_preferences

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlay.json"
            with mock.patch("word_factori.overlay_preferences.os.replace", side_effect=OSError("blocked")):
                with self.assertRaisesRegex(OSError, "blocked"):
                    save_preferences(path, OverlayPreferences())
            self.assertEqual(tuple(path.parent.glob(f".{path.name}.*.tmp")), ())


if __name__ == "__main__":
    unittest.main()
