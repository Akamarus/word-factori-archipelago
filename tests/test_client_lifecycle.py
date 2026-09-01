import argparse
import asyncio
from dataclasses import FrozenInstanceError
from datetime import datetime
import importlib
import json
import logging
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


class _NameLookup:
    def __init__(self, names=None):
        self.names = dict(names or {})

    def lookup_in_game(self, item_id):
        return self.names.get(item_id, str(item_id))

    def lookup_in_slot(self, location_id, slot):
        return self.names.get((location_id, slot), str(location_id))


def make_network_item(*, item, location, player, flags=0):
    return types.SimpleNamespace(item=item, location=location, player=player, flags=flags)


def item_send_packet(*, source, receiving, location, item=7001, flags=0):
    return {
        "type": "ItemSend",
        "item": make_network_item(item=item, location=location, player=source, flags=flags),
        "receiving": receiving,
    }


class _CommonContext:
    def __init__(self, server_address=None, password=None):
        self.server_address = server_address
        self.password = password
        self.auth = None
        self.team = None
        self.slot = None
        self.server = object()
        self.items_received = []
        self.item_names = _NameLookup({7001: "Contraption"})
        self.location_names = _NameLookup({(9001, 2): "Remote Factory"})
        self.slot_info = {
            1: types.SimpleNamespace(name="Factory Player", game="Word Factori"),
            2: types.SimpleNamespace(name="Remote Player", game="Other Game"),
            3: types.SimpleNamespace(name="Third Player", game="Other Game"),
        }
        self.checked_locations = set()
        self.missing_locations = set()
        self.locations_checked = set()
        self.finished_game = False
        self.sent_messages = []
        self.print_json_calls = []
        self.connect_calls = []
        self.disconnect_calls = 0
        self.exit_event = asyncio.Event()

    async def get_username(self):
        return None

    async def send_connect(self):
        return None

    async def connect(self, address=None):
        self.connect_calls.append(address)

    async def disconnect(self, allow_autoreconnect=False):
        self.disconnect_calls += 1

    async def server_auth(self, password_requested=False):
        return self.password

    async def send_msgs(self, messages):
        self.sent_messages.extend(messages)

    async def check_locations(self, locations):
        new = set(locations) & self.missing_locations
        if new:
            await self.send_msgs([{"cmd": "LocationChecks", "locations": tuple(new)}])
        return new

    def slot_concerns_self(self, slot):
        return slot == self.slot

    def on_print_json(self, args):
        self.print_json_calls.append(args)

    def jsontotextparser(self, data):
        return "".join(
            str(part.get("text", ""))
            for part in data
            if isinstance(part, dict)
        )

    async def shutdown(self):
        return None

    async def connection_closed(self):
        self.server = None

    def run_cli(self):
        return None


class _ControlledAsyncLock:
    def __init__(self):
        self.entered = asyncio.Event()
        self.proceed = asyncio.Event()

    async def __aenter__(self):
        self.entered.set()
        await self.proceed.wait()

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    def locked(self):
        return self.entered.is_set() and not self.proceed.is_set()


class _CommandProcessor:
    def __init__(self, ctx):
        self.ctx = ctx
        self.outputs = []

    def output(self, text):
        self.outputs.append(text)


class _FakeOverlaySupervisor:
    def __init__(self, *, publish_succeeds=True, start_succeeds=True):
        self.publish_succeeds = publish_succeeds
        self.start_succeeds = start_succeeds
        self.published = []
        self.started = []
        self.restarted = []
        self.actions = []
        self.stopped = 0
        self.health_checks = 0
        self.disable_on_health_check = False
        self.raise_on_health_check = False
        self.disabled = False
        self.session_generation = 0

    def start(self, config):
        self.started.append(config)
        if self.start_succeeds and self.session_generation == 0:
            self.session_generation += 1
        return self.start_succeeds

    def publish(self, value):
        self.published.append(value)
        return self.publish_succeeds

    def poll_actions(self):
        actions, self.actions = tuple(self.actions), []
        return actions

    def health_check(self):
        self.health_checks += 1
        if self.raise_on_health_check:
            raise OSError("health pipe failed")
        if self.disable_on_health_check:
            self.disabled = True

    def restart(self, config):
        self.restarted.append(config)
        self.disabled = False
        if self.start_succeeds:
            self.session_generation += 1
        return self.start_succeeds

    def stop(self, timeout=2.0):
        self.stopped += 1


common_client = types.ModuleType("CommonClient")
common_client.ClientCommandProcessor = _CommandProcessor
common_client.CommonContext = _CommonContext
common_client.get_base_parser = lambda description=None: argparse.ArgumentParser(description=description)
common_client.gui_enabled = False
common_client.logger = logging.getLogger("WordFactoriTestClient")
common_client.server_loop = lambda ctx: asyncio.sleep(0)
sys.modules.setdefault("CommonClient", common_client)

utils = types.ModuleType("Utils")
utils.init_logging = lambda *args, **kwargs: None
sys.modules.setdefault("Utils", utils)

net_utils = types.ModuleType("NetUtils")
net_utils.ClientStatus = types.SimpleNamespace(CLIENT_GOAL=30)
sys.modules.setdefault("NetUtils", net_utils)

from word_factori.client import WordFactoriCommandProcessor, WordFactoriContext
from word_factori.bridge import BridgeState
from word_factori.client_messages import ClientMessageKind
from word_factori.campaign import campaign_digest, campaign_for_level_set
from word_factori.data import (
    CAMPAIGN_DIGEST, CAMPAIGN_ID, CAMPAIGN_VERSION, ITEM_NAME_TO_ID, LOCATIONS,
    locations_for_level_set,
)
from word_factori.dispatch import DispatchDirection
from word_factori.dispatch_store import DispatchLedger, load_ledger, save_ledger
from word_factori.mod import render_levels
from word_factori.overlay_model import OverlayAction, OverlayFilter, OverlayState, apply_action
from word_factori.overlay_preferences import OverlayPreferences
from word_factori.overlay_protocol import (
    ConnectIntent,
    DisconnectIntent,
    PasswordIntent,
    SubmitTextIntent,
)
from word_factori.overlay_supervisor import OverlayConfig


class ClientLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_core_level_set_is_validated_and_installed_before_play(self):
        manifest = campaign_for_level_set("core_campaign")
        locations = locations_for_level_set("core_campaign")
        self.ctx.slot_data = {
            **self.ctx.slot_data,
            "level_set": "core_campaign",
            "campaign_id": manifest.campaign_id,
            "manifest_version": manifest.version,
            "manifest_digest": campaign_digest(manifest),
            "level_count": len(locations),
        }

        self.assertTrue(self.ctx.prepare_selected_campaign())
        identity = json.loads(self.ctx.campaign_path.read_text(encoding="utf-8"))
        levels = json.loads(self.ctx.levels_path.read_text(encoding="utf-8"))
        self.assertEqual("word-factori-core", identity["campaign_id"])
        self.assertEqual(30, identity["level_count"])
        self.assertEqual(30, len(levels))
        self.assertTrue(self.ctx.compatible_campaign())

    async def test_tampered_curated_level_set_identity_is_never_written(self):
        self.ctx.slot_data = {
            **self.ctx.slot_data,
            "level_set": "core_campaign",
            "manifest_digest": "0" * 64,
            "level_count": 30,
        }
        original = self.ctx.campaign_path.read_text(encoding="utf-8")

        self.assertFalse(self.ctx.prepare_selected_campaign())
        self.assertEqual(original, self.ctx.campaign_path.read_text(encoding="utf-8"))
        self.assertFalse(self.ctx.levels_path.exists())

    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {"LOCALAPPDATA": self.directory.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.overlay = _FakeOverlaySupervisor()
        self.ctx = WordFactoriContext("localhost:38281", None, overlay=self.overlay)
        self.ctx.auth = "Factory Player"
        self.ctx.team = 0
        self.ctx.slot = 1
        self.ctx.room_seed_name = "Seed-A"
        self.ctx.slot_data = {
            "goal": 1,
            "campaign_count": 25,
            "campaign_id": CAMPAIGN_ID,
            "manifest_version": CAMPAIGN_VERSION,
            "manifest_digest": CAMPAIGN_DIGEST,
        }
        self.ctx.connected_identity = self.ctx.current_identity()
        self.ctx.dispatch_ledger = DispatchLedger.empty(self.ctx.connected_identity)
        self.ctx.mod_folder.mkdir(parents=True)
        self.ctx.campaign_path.write_text(json.dumps({
            "campaign_id": CAMPAIGN_ID,
            "manifest_version": CAMPAIGN_VERSION,
            "manifest_digest": CAMPAIGN_DIGEST,
            "level_count": 40,
        }), encoding="utf-8")
        self.account_directory = Path(self.directory.name) / "factori" / "test-account"
        self.account_directory.mkdir(parents=True)
        (Path(self.directory.name) / "factori" / "user_ref.json").write_text(
            json.dumps({"most_recent_steam": "test-account"}), encoding="utf-8"
        )
        self.save_path = self.account_directory / "mods" / "word factori archipelago" / "save.json"
        self.save_path.parent.mkdir(parents=True)
        self.write_active_slot("game-slot-A", set())

    def write_active_slot(self, random_id, beaten_indices):
        self.save_path.write_text(json.dumps({
            "slots": {
                "0": {
                    "slot_is_active": 1,
                    "random_id": random_id,
                    "beaten_levels": {str(index): 1 for index in beaten_indices},
                }
            }
        }), encoding="utf-8")

    def capture_scheduled_task(self, callback):
        before = asyncio.all_tasks()
        callback()
        created = asyncio.all_tasks() - before
        self.assertEqual(1, len(created))
        return created.pop()

    async def test_overlay_connect_uses_common_context_connection_path(self):
        intent = ConnectIntent(
            "localhost:38281", "Factory", "room-password",
            self.ctx._presentation_generation,
        )
        with patch.object(self.ctx, "connect", AsyncMock()) as connect:
            await self.ctx.handle_overlay_intent(intent)

        self.assertEqual("Factory", self.ctx.auth)
        self.assertEqual("room-password", self.ctx.password)
        connect.assert_awaited_once_with("localhost:38281")
        self.assertEqual("connecting", self.ctx.overlay_state.connection_status)

    async def test_overlay_disconnect_uses_common_disconnect(self):
        intent = DisconnectIntent(self.ctx._presentation_generation)
        with patch.object(self.ctx, "disconnect", AsyncMock()) as disconnect:
            await self.ctx.handle_overlay_intent(intent)

        disconnect.assert_awaited_once_with()

    async def test_overlay_submit_routes_through_standard_command_processor(self):
        submitted = []

        class RecordingProcessor:
            def __init__(processor_self, ctx):
                processor_self.ctx = ctx

            def __call__(processor_self, text):
                submitted.append(text)

        self.ctx.command_processor = RecordingProcessor
        await self.ctx.handle_overlay_intent(SubmitTextIntent(
            "hello team", self.ctx._presentation_generation,
        ))
        await self.ctx.handle_overlay_intent(SubmitTextIntent(
            "/wf_status", self.ctx._presentation_generation,
        ))

        self.assertEqual(["hello team", "/wf_status"], submitted)

    async def test_server_auth_requests_password_in_overlay_without_echoing_it(self):
        self.ctx.password = None
        task = asyncio.create_task(self.ctx.server_auth(password_requested=True))
        await asyncio.sleep(0)

        self.assertEqual("password", self.ctx.overlay_state.active_view.value)
        self.assertFalse(task.done())
        await self.ctx.handle_overlay_intent(PasswordIntent(
            "secret", self.ctx._presentation_generation,
        ))
        await task

        self.assertEqual("secret", self.ctx.password)
        self.assertNotIn("secret", repr(self.overlay.published))

    async def test_unavailable_password_prompt_uses_standard_client_fallback(self):
        self.ctx.password = None
        self.overlay.publish_succeeds = False

        with patch.object(_CommonContext, "server_auth", AsyncMock()) as fallback:
            await self.ctx.server_auth(password_requested=True)

        fallback.assert_awaited_once_with(True)
        self.assertNotEqual("password", self.ctx.overlay_state.active_view.value)

    async def test_renderer_failure_after_password_prompt_uses_standard_fallback(self):
        self.ctx.password = None
        with patch.object(_CommonContext, "server_auth", AsyncMock()) as fallback:
            task = asyncio.create_task(self.ctx.server_auth(password_requested=True))
            await asyncio.sleep(0)
            self.assertEqual("password", self.ctx.overlay_state.active_view.value)

            self.overlay.disabled = True
            await asyncio.wait_for(task, timeout=0.75)

        fallback.assert_awaited_once_with(True)
        self.assertNotEqual("password", self.ctx.overlay_state.active_view.value)

    async def test_standard_password_fallback_sends_exactly_one_connect(self):
        self.ctx.password = None
        self.overlay.publish_succeeds = False

        async def standard_auth(password_requested):
            await self.ctx.get_username()
            await self.ctx.send_connect()

        with (
            patch.object(_CommonContext, "server_auth", AsyncMock(side_effect=standard_auth)) as fallback,
            patch.object(self.ctx, "get_username", AsyncMock()) as username,
            patch.object(self.ctx, "send_connect", AsyncMock()) as connect,
        ):
            await self.ctx.server_auth(password_requested=True)

        fallback.assert_awaited_once_with(True)
        username.assert_awaited_once_with()
        connect.assert_awaited_once_with()

    async def test_stale_full_client_intent_is_ignored(self):
        with patch.object(self.ctx, "connect", AsyncMock()) as connect:
            await self.ctx.handle_overlay_intent(ConnectIntent(
                "localhost:38281", "Factory", None,
                self.ctx._presentation_generation + 1,
            ))

        connect.assert_not_awaited()

    async def test_dispatch_received_items_are_idempotent_across_reconnect(self):
        first = make_network_item(item=7001, location=9001, player=2, flags=1)
        self.ctx.items_received = [first]
        self.ctx.connected_identity = None

        self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(1, len(self.ctx.dispatch_ledger.events))
        self.assertEqual((), self.ctx.pending_overlay_events)
        self.assertTrue(self.ctx.dispatch_ledger.events[0].historical)
        self.assertIsNone(self.ctx.dispatch_ledger.events[0].observed_at)
        self.assertEqual(
            frozenset((self.ctx.dispatch_ledger.events[0].key,)),
            self.ctx.overlay_state.accepted_notification_keys,
        )

        self.ctx.on_package("ReceivedItems", {"index": 0, "items": [first]})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(1, len(self.ctx.dispatch_ledger.events))
        self.assertEqual((), self.ctx.pending_overlay_events)

        second = make_network_item(item=7001, location=9001, player=2, flags=1)
        self.ctx.items_received.append(second)
        self.ctx.on_package("ReceivedItems", {"index": 1, "items": [second]})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(2, len(self.ctx.dispatch_ledger.events))
        self.assertEqual((), self.ctx.pending_overlay_events)
        self.assertEqual(1, len(self.ctx.overlay_state.visible_notifications))
        live = self.ctx.dispatch_ledger.events[-1]
        self.assertFalse(live.historical)
        self.assertIsNotNone(live.observed_at)
        self.assertIsNotNone(datetime.fromisoformat(live.observed_at.replace("Z", "+00:00")).tzinfo)

    def test_print_json_reaches_standard_log_and_overlay_transcript(self):
        packet = {
            "type": "Chat",
            "slot": 2,
            "data": [{"text": "Alex: "}, {"text": "hello"}],
        }

        self.ctx.on_print_json(packet)

        self.assertEqual([packet], self.ctx.print_json_calls)
        message = self.ctx.transcript.messages[-1]
        self.assertIs(ClientMessageKind.CHAT, message.kind)
        self.assertEqual("Alex: hello", message.text)
        self.assertEqual("chat", self.overlay.published[-1].transcript_rows[-1].kind)

    async def test_item_send_is_not_duplicated_into_chat_transcript(self):
        self.ctx.on_print_json(item_send_packet(
            source=1, receiving=2, location=LOCATIONS[0].code,
        ))
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        self.assertEqual((), self.ctx.transcript.messages)

    def test_command_output_reaches_standard_output_and_chat_view(self):
        processor = WordFactoriCommandProcessor(self.ctx)

        processor._cmd_wf_status()

        self.assertIn("AP mod", processor.outputs[-1])
        self.assertIs(ClientMessageKind.COMMAND, self.ctx.transcript.messages[-1].kind)
        self.assertEqual(processor.outputs[-1], self.ctx.transcript.messages[-1].text)

    def test_connection_refusal_adds_actionable_notice_without_raw_secret(self):
        self.ctx.on_package("ConnectionRefused", {"errors": ["InvalidPassword"]})

        notice = self.ctx.client_notices[-1]
        self.assertEqual("connection-refused", notice.code)
        self.assertEqual("error", notice.severity)
        self.assertNotIn("InvalidPassword", notice.text)

    async def test_item_send_records_only_local_source_or_recipient(self):
        local_send = item_send_packet(source=1, receiving=2, location=LOCATIONS[0].code)
        unrelated = item_send_packet(source=3, receiving=2, location=123)

        self.ctx.on_print_json(local_send)
        self.ctx.on_print_json(unrelated)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        self.assertEqual(2, len(self.ctx.print_json_calls))
        self.assertEqual(
            [DispatchDirection.SENT],
            [event.direction for event in self.ctx.dispatch_ledger.events],
        )
        sent = self.ctx.dispatch_ledger.events[0]
        self.assertFalse(sent.historical)
        self.assertIsNotNone(sent.observed_at)
        self.assertIsNotNone(datetime.fromisoformat(sent.observed_at.replace("Z", "+00:00")).tzinfo)

    async def test_item_send_serializes_ledger_write_with_dispatch_lock(self):
        lock_states = []

        def observe_lock(path, ledger):
            lock_states.append(self.ctx._dispatch_lock.locked())

        with patch("word_factori.client.save_ledger", side_effect=observe_lock):
            self.ctx.on_print_json(item_send_packet(
                source=1, receiving=2, location=LOCATIONS[0].code,
            ))
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        self.assertEqual([True], lock_states)

    async def test_delayed_item_send_cannot_write_old_ledger_to_new_room_path(self):
        lock = _ControlledAsyncLock()
        self.ctx._dispatch_lock = lock
        task = self.capture_scheduled_task(lambda: self.ctx.on_print_json(item_send_packet(
            source=1, receiving=2, location=LOCATIONS[0].code,
        )))
        await lock.entered.wait()

        self.ctx.room_seed_name = "Seed-B"
        self.ctx.connected_identity = self.ctx.current_identity()
        new_room_path = self.ctx.dispatch_path()
        lock.proceed.set()
        await task

        self.assertFalse(new_room_path.exists())
        self.assertEqual((), self.ctx.pending_overlay_events)

    async def test_delayed_received_items_cannot_reconcile_into_new_room_ledger(self):
        self.ctx.items_received = [make_network_item(
            item=7001, location=9001, player=2, flags=1,
        )]
        lock = _ControlledAsyncLock()
        self.ctx._dispatch_lock = lock
        task = self.capture_scheduled_task(lambda: self.ctx.on_package(
            "ReceivedItems", {"index": 0, "items": tuple(self.ctx.items_received)},
        ))
        await lock.entered.wait()

        self.ctx.room_seed_name = "Seed-B"
        self.ctx.connected_identity = self.ctx.current_identity()
        self.ctx.dispatch_ledger = DispatchLedger.empty(self.ctx.connected_identity)
        new_room_path = self.ctx.dispatch_path()
        lock.proceed.set()
        await task

        self.assertEqual((), self.ctx.dispatch_ledger.events)
        self.assertEqual((), self.ctx.pending_overlay_events)
        self.assertFalse(new_room_path.exists())

    async def test_delayed_location_info_cannot_backfill_new_room_ledger(self):
        checked = LOCATIONS[0].code
        self.ctx.checked_locations = {checked}
        lock = _ControlledAsyncLock()
        self.ctx._dispatch_lock = lock
        packet = {"locations": [make_network_item(
            item=7001, location=checked, player=2, flags=1,
        )]}
        task = self.capture_scheduled_task(lambda: self.ctx.on_package("LocationInfo", packet))
        await lock.entered.wait()

        self.ctx.room_seed_name = "Seed-B"
        self.ctx.connected_identity = self.ctx.current_identity()
        self.ctx.dispatch_ledger = DispatchLedger.empty(self.ctx.connected_identity)
        self.ctx.checked_locations = set()
        new_room_path = self.ctx.dispatch_path()
        lock.proceed.set()
        await task

        self.assertEqual((), self.ctx.dispatch_ledger.events)
        self.assertEqual((), self.ctx.pending_overlay_events)
        self.assertFalse(new_room_path.exists())

    def test_dispatch_item_snapshot_copies_and_freezes_all_packet_fields(self):
        item = make_network_item(item=7001, location=9001, player=2, flags=1)

        snapshot = self.ctx._snapshot_dispatch_item(item)
        item.item = 8001
        item.location = 9002
        item.player = 3
        item.flags = 0

        self.assertEqual((7001, 9001, 2, 1), (
            snapshot.item, snapshot.location, snapshot.player, snapshot.flags,
        ))
        with self.assertRaises(FrozenInstanceError):
            snapshot.flags = 0

    async def test_delayed_received_items_use_callback_time_item_values(self):
        item = make_network_item(item=7001, location=9001, player=2, flags=1)
        self.ctx.items_received = [item]
        lock = _ControlledAsyncLock()
        self.ctx._dispatch_lock = lock
        task = self.capture_scheduled_task(lambda: self.ctx.on_package(
            "ReceivedItems", {"index": 0, "items": (item,)},
        ))
        await lock.entered.wait()

        item.item = 8001
        item.location = 9002
        item.player = 3
        item.flags = 0
        lock.proceed.set()
        await task

        event = self.ctx.dispatch_ledger.events[0]
        self.assertEqual((7001, 9001, 2), (
            event.item_id, event.location_id, event.other_slot,
        ))

    async def test_delayed_location_info_uses_callback_time_item_values(self):
        original_location = LOCATIONS[0].code
        changed_location = LOCATIONS[1].code
        self.ctx.checked_locations = {original_location, changed_location}
        item = make_network_item(
            item=7001, location=original_location, player=2, flags=1,
        )
        lock = _ControlledAsyncLock()
        self.ctx._dispatch_lock = lock
        task = self.capture_scheduled_task(lambda: self.ctx.on_package(
            "LocationInfo", {"locations": (item,)},
        ))
        await lock.entered.wait()

        item.item = 8001
        item.location = changed_location
        item.player = 3
        item.flags = 0
        lock.proceed.set()
        await task

        event = self.ctx.dispatch_ledger.events[0]
        self.assertEqual((7001, original_location, 2), (
            event.item_id, event.location_id, event.other_slot,
        ))

    async def test_item_send_self_item_waits_for_authoritative_receive(self):
        self.ctx.on_print_json(item_send_packet(
            source=1, receiving=1, location=LOCATIONS[0].code,
        ))
        self.assertEqual((), self.ctx.dispatch_ledger.events)

        self.ctx.items_received = [make_network_item(
            item=7001, location=LOCATIONS[0].code, player=1, flags=1,
        )]
        await self.ctx.reconcile_dispatches()

        self.assertEqual(1, len(self.ctx.dispatch_ledger.events))
        self.assertEqual(DispatchDirection.SELF, self.ctx.dispatch_ledger.events[0].direction)

    def test_received_item_missing_metadata_uses_numeric_fallbacks(self):
        def missing(*args):
            raise KeyError(args)

        self.ctx.slot_info.pop(8, None)
        self.ctx.item_names.lookup_in_game = missing
        self.ctx.location_names.lookup_in_slot = missing

        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=8001, location=9002, player=8),
        )

        self.assertEqual("Item 8001", event.item_name)
        self.assertEqual("Player 8", event.other_player)
        self.assertEqual("Unknown Game", event.other_game)
        self.assertEqual("Location 9002", event.location_name)

    async def test_connected_scouts_only_checked_word_factori_locations(self):
        checked = {LOCATIONS[0].code, LOCATIONS[3].code}
        self.ctx.checked_locations = checked | {999999999}
        self.ctx.missing_locations = {LOCATIONS[1].code}

        await self.ctx.request_checked_location_info()

        message = next(msg for msg in self.ctx.sent_messages if msg["cmd"] == "LocationScouts")
        self.assertEqual(checked, set(message["locations"]))
        self.assertEqual(0, message["create_as_hint"])

    async def test_location_info_backfills_checked_sends_silently(self):
        checked = LOCATIONS[0].code
        unchecked = LOCATIONS[1].code
        self.ctx.checked_locations = {checked}
        packet = {"locations": [
            make_network_item(item=7001, location=checked, player=2, flags=1),
            make_network_item(item=7001, location=unchecked, player=2, flags=1),
            make_network_item(item=7001, location=999999999, player=2, flags=1),
        ]}

        self.ctx.on_package("LocationInfo", packet)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        self.assertEqual(1, len(self.ctx.dispatch_ledger.events))
        event = self.ctx.dispatch_ledger.events[0]
        self.assertEqual(DispatchDirection.SENT, event.direction)
        self.assertEqual(checked, event.location_id)
        self.assertTrue(event.historical)
        self.assertIsNone(event.observed_at)
        self.assertEqual((), self.ctx.pending_overlay_events)

        self.ctx.on_package("LocationInfo", packet)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(1, len(self.ctx.dispatch_ledger.events))

    async def test_connected_recovers_from_corrupt_room_ledger(self):
        path = self.ctx.dispatch_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        self.ctx.connected_identity = None

        with self.assertLogs("WordFactoriTestClient", level="WARNING") as messages:
            self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        self.assertEqual(self.ctx.current_identity(), self.ctx.dispatch_ledger.identity)
        self.assertTrue(any("invalid dispatch ledger" in message for message in messages.output))

    async def test_connected_clears_transient_notifications_before_room_baseline(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        self.ctx.pending_overlay_events = (event,)
        self.ctx.room_seed_name = "Seed-B"
        self.ctx.connected_identity = None

        self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        self.assertEqual((), self.ctx.pending_overlay_events)
        self.assertEqual(self.ctx.current_identity(), self.ctx.dispatch_ledger.identity)

    async def test_connected_requests_checked_location_history(self):
        checked = LOCATIONS[2].code
        self.ctx.checked_locations = {checked}
        self.ctx.connected_identity = None

        self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        scouts = [message for message in self.ctx.sent_messages if message["cmd"] == "LocationScouts"]
        self.assertEqual([[checked]], [message["locations"] for message in scouts])

    async def test_bender_access_pseudo_item_is_not_dispatched(self):
        self.ctx.items_received = [make_network_item(
            item=ITEM_NAME_TO_ID["Bender Access"], location=LOCATIONS[0].code,
            player=1,
        )]

        await self.ctx.reconcile_dispatches()

        self.assertEqual((), self.ctx.dispatch_ledger.events)

    async def test_dispatch_write_failure_does_not_block_unlock_rendering(self):
        self.ctx.items_received = [make_network_item(
            item=7001, location=9001, player=2, flags=1,
        )]

        with patch("word_factori.client.save_ledger", side_effect=OSError("disk full")):
            with self.assertLogs("WordFactoriTestClient", level="ERROR"):
                self.ctx.on_package("ReceivedItems", {"index": 0, "items": self.ctx.items_received})
                await asyncio.sleep(0)
                await asyncio.sleep(0)

        self.assertEqual("Contraption", self.ctx.bridge_state.applied[0])
        self.assertTrue(self.ctx.levels_path.is_file())

    async def test_overlay_publish_failure_does_not_block_item_reconcile(self):
        self.ctx.overlay = _FakeOverlaySupervisor(publish_succeeds=False)
        self.ctx.items_received = [make_network_item(
            item=7001, location=9001, player=2, flags=1,
        )]

        await self.ctx.reconcile_received()

        location_id = LOCATIONS[0].code
        self.ctx.missing_locations = {location_id}
        await self.ctx.report_indices({0})

        self.assertTrue(self.ctx.levels_path.exists())
        self.assertEqual("Contraption", self.ctx.bridge_state.applied[0])
        self.assertTrue(any(
            message["cmd"] == "LocationChecks" for message in self.ctx.sent_messages
        ))
        self.assertIn("overlay", self.ctx.status_text().lower())

    async def test_overlay_starts_after_explicit_runtime_start_with_visual_only_config(self):
        executable = Path(self.directory.name) / "ArchipelagoLauncher.exe"
        executable.touch()
        executable.with_name("FredokaOne.ttf").touch()
        self.ctx.overlay_preferences = OverlayPreferences(
            interface_scale=1.25,
            left_offset=-80,
            notification_duration=8.5,
            reduced_motion=True,
            max_visible=4,
        )
        self.ctx.overlay_state = OverlayState.closed(max_visible=4)

        with patch("word_factori.client.sys.executable", str(executable)):
            self.ctx.start_overlay()

        self.assertEqual(1, len(self.overlay.started))
        config = self.overlay.started[0]
        self.assertIsInstance(config, OverlayConfig)
        self.assertIsNone(config.font_path)
        self.assertEqual((1.25, -80, 8.5, True, 4), (
            config.interface_scale,
            config.left_offset,
            config.notification_duration,
            config.reduced_motion,
            config.max_visible,
        ))
        self.assertNotIn("localhost", repr(config))
        self.assertNotIn("password", repr(config).lower())
        self.assertIsNotNone(self.ctx.overlay_action_task)
        await self.ctx.shutdown()

    async def test_disabled_overlay_skips_child_but_keeps_dispatch_ledger(self):
        self.ctx.overlay_preferences = OverlayPreferences(enabled=False)
        self.ctx.overlay_state = OverlayState.closed(
            max_visible=self.ctx.overlay_preferences.max_visible,
        )
        self.ctx.start_overlay()
        self.ctx.items_received = [make_network_item(
            item=7001, location=9001, player=2, flags=1,
        )]

        await self.ctx.reconcile_dispatches()

        self.assertEqual([], self.overlay.started)
        self.assertEqual(1, len(self.ctx.dispatch_ledger.events))

    def test_malformed_overlay_preferences_fall_back_to_valid_defaults(self):
        path = self.ctx.overlay_preferences_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"version":1,"preferences":{"enabled":"yes"}}', encoding="utf-8")

        recovered = WordFactoriContext("localhost:38281", None, overlay=_FakeOverlaySupervisor())

        self.assertEqual(OverlayPreferences(), recovered.overlay_preferences)
        self.assertEqual(3, recovered.overlay_state.max_visible)

    async def test_room_load_seeds_history_then_reduces_new_notifications_once(self):
        first = make_network_item(item=7001, location=9001, player=2, flags=1)
        second = make_network_item(item=7001, location=9002, player=2, flags=1)
        first_event = self.ctx.dispatch_received_event(0, first)
        stored = DispatchLedger(
            self.ctx.connected_identity,
            (first_event,),
            frozenset((first_event.key,)),
            True,
            0,
        )
        save_ledger(self.ctx.dispatch_path(), stored)
        self.ctx.items_received = [first, second]

        await self.ctx._connected_reconcile(
            self.ctx.connected_identity,
            self.ctx._snapshot_dispatch_items(self.ctx.items_received),
            frozenset(),
        )

        self.assertEqual(2, self.ctx.overlay_state.unread_count)
        self.assertEqual((self.ctx.dispatch_ledger.events[-1].key,), tuple(
            event.key for event in self.ctx.overlay_state.visible_notifications
        ))
        self.assertEqual(
            frozenset(event.key for event in self.ctx.dispatch_ledger.events),
            self.ctx.overlay_state.accepted_notification_keys,
        )

        await self.ctx._connected_reconcile(
            self.ctx.connected_identity,
            self.ctx._snapshot_dispatch_items(self.ctx.items_received),
            frozenset(),
        )
        self.assertEqual((), self.ctx.overlay_state.visible_notifications)
        self.assertEqual(2, self.ctx.overlay_state.unread_count)

    async def test_room_switch_replaces_overlay_state_instead_of_merging(self):
        old_event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        old_key = old_event.key
        self.ctx.dispatch_ledger = DispatchLedger(
            self.ctx.connected_identity, (old_event,), frozenset((old_key,)), True, 0,
        )
        self.ctx.overlay_state = OverlayState(
            unread_count=1,
            accepted_notification_keys=frozenset((old_key,)),
        )
        self.overlay.published.clear()
        self.ctx.room_seed_name = "Seed-B"
        self.ctx.connected_identity = self.ctx.current_identity()
        self.ctx.dispatch_ledger = DispatchLedger.empty(self.ctx.connected_identity)
        self.ctx.items_received = []

        await self.ctx._connected_reconcile(
            self.ctx.connected_identity, (), frozenset(),
        )

        self.assertEqual(0, self.ctx.overlay_state.unread_count)
        self.assertEqual(frozenset(), self.ctx.overlay_state.accepted_notification_keys)
        self.assertEqual("connected", self.ctx.overlay_state.connection_status)
        self.assertFalse(any(
            any(row.key == old_key for row in published.ledger_rows)
            for published in self.overlay.published
        ))

    def test_incompatible_room_switch_immediately_replaces_old_cosmetic_history(self):
        old_event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        self.ctx.dispatch_ledger = DispatchLedger(
            self.ctx.connected_identity, (old_event,), frozenset((old_event.key,)), True, 0,
        )
        self.ctx.overlay_state = OverlayState(
            unread_count=1,
            accepted_notification_keys=frozenset((old_event.key,)),
        )
        self.ctx.room_seed_name = "Seed-B"
        self.ctx.connected_identity = None
        incompatible = dict(self.ctx.slot_data, manifest_digest="0" * 64)

        self.ctx.on_package("Connected", {"slot_data": incompatible})

        self.assertEqual(self.ctx.current_identity(), self.ctx.dispatch_ledger.identity)
        self.assertEqual((), self.ctx.dispatch_ledger.events)
        self.assertEqual(frozenset(), self.ctx.overlay_state.accepted_notification_keys)
        self.assertEqual("connected", self.ctx.overlay_state.connection_status)

    async def test_open_action_marks_room_ledger_read_with_one_atomic_save(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        self.ctx.dispatch_ledger = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.overlay_state = OverlayState(
            unread_count=1,
            accepted_notification_keys=frozenset((event.key,)),
        )
        self.overlay.actions = [
            OverlayAction("open", generation=self.ctx._presentation_generation),
            OverlayAction("open", generation=self.ctx._presentation_generation),
        ]

        with patch("word_factori.client.save_ledger", wraps=save_ledger) as persisted:
            await self.ctx.process_overlay_actions_once()

        self.assertTrue(self.ctx.overlay_state.is_open)
        self.assertEqual(0, self.ctx.overlay_state.unread_count)
        self.assertEqual(frozenset(), self.ctx.dispatch_ledger.unread_keys)
        self.assertEqual(1, persisted.call_count)
        self.assertEqual(frozenset(), load_ledger(
            self.ctx.dispatch_path(), self.ctx.connected_identity,
        ).unread_keys)

    async def test_event_received_while_ledger_open_is_read_without_toast(self):
        self.ctx.dispatch_ledger = DispatchLedger(
            self.ctx.connected_identity, (), frozenset(), True, -1,
        )
        self.ctx.overlay_state = apply_action(self.ctx.overlay_state, OverlayAction("open"))
        event = self.ctx.dispatch_sent_event(
            make_network_item(item=7001, location=LOCATIONS[0].code, player=2),
            historical=False,
        )

        await self.ctx._record_dispatch_event_safely(
            self.ctx.connected_identity, event, notify=True,
        )

        self.assertEqual(frozenset(), self.ctx.dispatch_ledger.unread_keys)
        self.assertEqual((), self.ctx.overlay_state.visible_notifications)
        self.assertIn(event.key, self.ctx.overlay_state.accepted_notification_keys)

    async def test_old_same_room_reconcile_cannot_overwrite_new_connection_epoch(self):
        first = make_network_item(item=7001, location=9001, player=2, flags=1)
        second = make_network_item(item=7001, location=9002, player=2, flags=1)
        first_event = self.ctx.dispatch_received_event(0, first)
        second_event = self.ctx.dispatch_received_event(1, second)
        authoritative = DispatchLedger(
            self.ctx.connected_identity,
            (first_event, second_event),
            frozenset((first_event.key, second_event.key)),
            True,
            1,
        )
        save_ledger(self.ctx.dispatch_path(), authoritative)
        old_generation = self.ctx._connection_generation
        controlled = _ControlledAsyncLock()
        self.ctx._dispatch_lock = controlled
        old = asyncio.create_task(self.ctx.reconcile_dispatches(
            self.ctx.connected_identity,
            self.ctx._snapshot_dispatch_items((first,)),
            connection_generation=old_generation,
        ))
        entered = asyncio.create_task(controlled.entered.wait())
        done, _ = await asyncio.wait((old, entered), return_when=asyncio.FIRST_COMPLETED)
        if old in done:
            await old
        self.assertTrue(entered.done())

        incompatible = dict(self.ctx.slot_data, manifest_digest="0" * 64)
        self.ctx.on_package("Connected", {"slot_data": incompatible})
        controlled.proceed.set()
        await old

        self.assertEqual(2, len(self.ctx.dispatch_ledger.events))
        self.assertEqual(2, len(load_ledger(
            self.ctx.dispatch_path(), self.ctx.connected_identity,
        ).events))

    async def test_stale_child_generation_cannot_open_or_mark_room_read(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        stored = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        save_ledger(self.ctx.dispatch_path(), stored)
        stale_generation = self.ctx._presentation_generation
        incompatible = dict(self.ctx.slot_data, manifest_digest="0" * 64)
        self.ctx.on_package("Connected", {"slot_data": incompatible})
        self.overlay.actions = [OverlayAction("open", generation=stale_generation)]

        await self.ctx.process_overlay_actions_once()

        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)

    async def test_room_a_child_open_cannot_clear_room_b_unread(self):
        room_a_generation = self.ctx._presentation_generation
        self.ctx.room_seed_name = "Seed-B"
        room_b_identity = self.ctx.current_identity()
        room_b_event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2), room_b_identity,
        )
        room_b = DispatchLedger(
            room_b_identity, (room_b_event,), frozenset((room_b_event.key,)), True, 0,
        )
        save_ledger(self.ctx.dispatch_path(room_b_identity), room_b)
        incompatible = dict(self.ctx.slot_data, manifest_digest="0" * 64)
        self.ctx.on_package("Connected", {"slot_data": incompatible})
        self.overlay.actions = [OverlayAction("open", generation=room_a_generation)]

        await self.ctx.process_overlay_actions_once()

        self.assertEqual(room_b_identity, self.ctx.dispatch_ledger.identity)
        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((room_b_event.key,)), self.ctx.dispatch_ledger.unread_keys)

    async def test_local_open_waiting_on_lock_cannot_mark_new_room_read(self):
        room_b_identity = self.ctx.current_identity().replace("Seed-A", "Seed-B")
        room_b_event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2), room_b_identity,
        )
        room_b = DispatchLedger(
            room_b_identity, (room_b_event,), frozenset((room_b_event.key,)), True, 0,
        )
        save_ledger(self.ctx.dispatch_path(room_b_identity), room_b)
        controlled = _ControlledAsyncLock()
        self.ctx._dispatch_lock = controlled
        opening = asyncio.create_task(self.ctx.overlay_control("show"))
        entered = asyncio.create_task(controlled.entered.wait())
        done, _ = await asyncio.wait((opening, entered), return_when=asyncio.FIRST_COMPLETED)
        if opening in done:
            await opening
        self.assertTrue(entered.done())

        self.ctx.room_seed_name = "Seed-B"
        incompatible = dict(self.ctx.slot_data, manifest_digest="0" * 64)
        self.ctx.on_package("Connected", {"slot_data": incompatible})
        controlled.proceed.set()
        await opening

        self.assertEqual(room_b_identity, self.ctx.dispatch_ledger.identity)
        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((room_b_event.key,)), self.ctx.dispatch_ledger.unread_keys)

    async def test_open_waiting_on_persistence_lock_preserves_newer_cosmetic_action(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        self.ctx.dispatch_ledger = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.overlay_state = OverlayState(
            unread_count=1, accepted_notification_keys=frozenset((event.key,)),
        )
        controlled = _ControlledAsyncLock()
        self.ctx._dispatch_lock = controlled
        opening = asyncio.create_task(self.ctx._apply_local_overlay_action(OverlayAction("open")))
        entered = asyncio.create_task(controlled.entered.wait())
        done, _ = await asyncio.wait((opening, entered), return_when=asyncio.FIRST_COMPLETED)
        if opening in done:
            await opening
        self.assertTrue(entered.done())

        await self.ctx._apply_local_overlay_action(OverlayAction("filter", "sent"))
        controlled.proceed.set()
        await opening

        self.assertTrue(self.ctx.overlay_state.is_open)
        self.assertEqual(OverlayFilter.SENT, self.ctx.overlay_state.active_filter)

    async def test_disabled_or_unavailable_show_never_clears_unread(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        self.ctx.dispatch_ledger = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.overlay_state = OverlayState(unread_count=1)
        self.ctx.overlay_preferences = OverlayPreferences(enabled=False)

        await self.ctx.overlay_control("show")

        self.assertEqual([], self.overlay.started)
        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)

        self.ctx.overlay_preferences = OverlayPreferences(enabled=True)
        self.overlay.publish_succeeds = False
        await self.ctx.overlay_control("show")
        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)

        self.overlay.publish_succeeds = True
        self.overlay.disabled = True
        await self.ctx.overlay_control("show")
        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)

    async def test_hide_closes_local_panel_without_marking_unread_ledger(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        self.ctx.dispatch_ledger = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.overlay_state = OverlayState(
            is_open=True, unread_count=0,
            accepted_notification_keys=frozenset((event.key,)),
        )

        await self.ctx.overlay_control("hide")

        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)

    async def test_open_mark_read_is_transactional_and_keeps_persistence_diagnostic(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        stored = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.dispatch_ledger = stored
        self.ctx.overlay_state = OverlayState(
            unread_count=1, accepted_notification_keys=frozenset((event.key,)),
        )
        save_ledger(self.ctx.dispatch_path(), stored)
        action = OverlayAction("open", generation=self.ctx._presentation_generation)
        self.overlay.actions = [action]

        with patch("word_factori.client.save_ledger", side_effect=OSError("replace failed")):
            await self.ctx.process_overlay_actions_once()

        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)
        self.assertEqual(frozenset((event.key,)), load_ledger(
            self.ctx.dispatch_path(), self.ctx.connected_identity,
        ).unread_keys)
        self.assertIn("replace failed", self.ctx.last_overlay_persistence_error)
        self.ctx.publish_overlay(self.ctx.connected_identity)
        self.assertIn("replace failed", self.ctx.last_overlay_persistence_error)

        self.overlay.actions = [action]
        await self.ctx.process_overlay_actions_once()
        self.assertTrue(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset(), self.ctx.dispatch_ledger.unread_keys)
        self.assertIsNone(self.ctx.last_overlay_persistence_error)

    async def test_open_event_persistence_failure_leaves_memory_and_disk_unchanged(self):
        empty = DispatchLedger.empty(self.ctx.connected_identity)
        self.ctx.dispatch_ledger = empty
        self.ctx.overlay_state = apply_action(self.ctx.overlay_state, OverlayAction("open"))
        save_ledger(self.ctx.dispatch_path(), empty)
        event = self.ctx.dispatch_sent_event(
            make_network_item(item=7001, location=LOCATIONS[0].code, player=2),
            historical=False,
        )

        with patch("word_factori.client.save_ledger", side_effect=OSError("replace failed")):
            await self.ctx._record_dispatch_event_safely(
                self.ctx.connected_identity, event, notify=True,
                connection_generation=self.ctx._connection_generation,
            )

        self.assertEqual((), self.ctx.dispatch_ledger.events)
        self.assertEqual((), load_ledger(
            self.ctx.dispatch_path(), self.ctx.connected_identity,
        ).events)
        self.assertNotIn(event.key, self.ctx.overlay_state.accepted_notification_keys)
        self.assertIn("replace failed", self.ctx.last_overlay_persistence_error)

    async def test_restart_invalidates_buffered_child_actions(self):
        buffered_generation = self.ctx._presentation_generation
        await self.ctx.overlay_control("restart")
        self.overlay.actions = [OverlayAction("open", generation=buffered_generation)]

        await self.ctx.process_overlay_actions_once()

        self.assertGreater(self.ctx._presentation_generation, buffered_generation)
        self.assertFalse(self.ctx.overlay_state.is_open)

    async def test_explicit_restart_invalidates_child_open_already_waiting_on_lock(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        stored = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.dispatch_ledger = stored
        self.ctx.overlay_state = OverlayState(
            unread_count=1, accepted_notification_keys=frozenset((event.key,)),
        )
        save_ledger(self.ctx.dispatch_path(), stored)
        controlled = _ControlledAsyncLock()
        self.ctx._dispatch_lock = controlled
        self.overlay.actions = [OverlayAction(
            "open", generation=self.ctx._presentation_generation,
        )]
        processing = asyncio.create_task(self.ctx.process_overlay_actions_once())
        entered = asyncio.create_task(controlled.entered.wait())
        done, _ = await asyncio.wait((processing, entered), return_when=asyncio.FIRST_COMPLETED)
        if processing in done:
            await processing
        self.assertTrue(entered.done())

        await self.ctx.overlay_control("restart")
        publications_after_restart = len(self.overlay.published)
        with patch("word_factori.client.save_ledger", wraps=save_ledger) as persisted:
            controlled.proceed.set()
            await processing

        self.assertEqual(0, persisted.call_count)
        self.assertEqual(publications_after_restart, len(self.overlay.published))
        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)
        self.assertEqual(frozenset((event.key,)), load_ledger(
            self.ctx.dispatch_path(), self.ctx.connected_identity,
        ).unread_keys)

    async def test_health_restart_invalidates_child_open_already_waiting_on_lock(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        stored = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.dispatch_ledger = stored
        self.ctx.overlay_state = OverlayState(
            unread_count=1, accepted_notification_keys=frozenset((event.key,)),
        )
        save_ledger(self.ctx.dispatch_path(), stored)
        controlled = _ControlledAsyncLock()
        self.ctx._dispatch_lock = controlled
        self.overlay.actions = [OverlayAction(
            "open", generation=self.ctx._presentation_generation,
        )]
        processing = asyncio.create_task(self.ctx.process_overlay_actions_once())
        entered = asyncio.create_task(controlled.entered.wait())
        done, _ = await asyncio.wait((processing, entered), return_when=asyncio.FIRST_COMPLETED)
        if processing in done:
            await processing
        self.assertTrue(entered.done())

        self.overlay.session_generation += 1
        self.ctx.check_overlay_health()
        publications_after_restart = len(self.overlay.published)
        with patch("word_factori.client.save_ledger", wraps=save_ledger) as persisted:
            controlled.proceed.set()
            await processing

        self.assertEqual(0, persisted.call_count)
        self.assertEqual(publications_after_restart, len(self.overlay.published))
        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)
        self.assertEqual(frozenset((event.key,)), load_ledger(
            self.ctx.dispatch_path(), self.ctx.connected_identity,
        ).unread_keys)

    async def test_closed_toggle_marks_room_read_with_one_transactional_save(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        stored = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.dispatch_ledger = stored
        self.ctx.overlay_state = OverlayState(
            unread_count=1, accepted_notification_keys=frozenset((event.key,)),
        )
        self.overlay.actions = [OverlayAction(
            "toggle", generation=self.ctx._presentation_generation,
        )]

        with patch("word_factori.client.save_ledger", wraps=save_ledger) as persisted:
            await self.ctx.process_overlay_actions_once()

        self.assertEqual(1, persisted.call_count)
        self.assertTrue(self.ctx.overlay_state.is_open)
        self.assertEqual(0, self.ctx.overlay_state.unread_count)
        self.assertEqual(frozenset(), self.ctx.dispatch_ledger.unread_keys)
        self.assertEqual(frozenset(), load_ledger(
            self.ctx.dispatch_path(), self.ctx.connected_identity,
        ).unread_keys)

    async def test_closed_toggle_save_failure_retains_state_ledger_and_disk(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        stored = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.dispatch_ledger = stored
        self.ctx.overlay_state = OverlayState(
            unread_count=1, accepted_notification_keys=frozenset((event.key,)),
        )
        save_ledger(self.ctx.dispatch_path(), stored)
        self.overlay.actions = [OverlayAction(
            "toggle", generation=self.ctx._presentation_generation,
        )]

        with patch("word_factori.client.save_ledger", side_effect=OSError("replace failed")):
            await self.ctx.process_overlay_actions_once()

        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(1, self.ctx.overlay_state.unread_count)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)
        self.assertEqual(frozenset((event.key,)), load_ledger(
            self.ctx.dispatch_path(), self.ctx.connected_identity,
        ).unread_keys)
        self.assertIn("replace failed", self.ctx.last_overlay_persistence_error)

    async def test_restart_invalidates_closed_toggle_already_waiting_on_lock(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        stored = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset((event.key,)), True, 0,
        )
        self.ctx.dispatch_ledger = stored
        self.ctx.overlay_state = OverlayState(
            unread_count=1, accepted_notification_keys=frozenset((event.key,)),
        )
        save_ledger(self.ctx.dispatch_path(), stored)
        controlled = _ControlledAsyncLock()
        self.ctx._dispatch_lock = controlled
        self.overlay.actions = [OverlayAction(
            "toggle", generation=self.ctx._presentation_generation,
        )]
        processing = asyncio.create_task(self.ctx.process_overlay_actions_once())
        entered = asyncio.create_task(controlled.entered.wait())
        done, _ = await asyncio.wait((processing, entered), return_when=asyncio.FIRST_COMPLETED)
        if processing in done:
            await processing
        self.assertTrue(entered.done())

        await self.ctx.overlay_control("restart")
        publications_after_restart = len(self.overlay.published)
        with patch("word_factori.client.save_ledger", wraps=save_ledger) as persisted:
            controlled.proceed.set()
            await processing

        self.assertEqual(0, persisted.call_count)
        self.assertEqual(publications_after_restart, len(self.overlay.published))
        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(frozenset((event.key,)), self.ctx.dispatch_ledger.unread_keys)
        self.assertEqual(frozenset((event.key,)), load_ledger(
            self.ctx.dispatch_path(), self.ctx.connected_identity,
        ).unread_keys)

    async def test_open_toggle_closes_without_saving_ledger(self):
        self.ctx.overlay_state = OverlayState(is_open=True)
        self.overlay.actions = [OverlayAction(
            "toggle", generation=self.ctx._presentation_generation,
        )]

        with patch("word_factori.client.save_ledger", wraps=save_ledger) as persisted:
            await self.ctx.process_overlay_actions_once()

        self.assertFalse(self.ctx.overlay_state.is_open)
        self.assertEqual(0, persisted.call_count)

    async def test_disconnect_preserves_room_history_and_publishes_status(self):
        event = self.ctx.dispatch_received_event(
            0, make_network_item(item=7001, location=9001, player=2),
        )
        self.ctx.dispatch_ledger = DispatchLedger(
            self.ctx.connected_identity, (event,), frozenset(), True, 0,
        )
        self.ctx.overlay_state = apply_action(
            self.ctx.overlay_state, OverlayAction("connection-status", "connected"),
        )
        previous_generation = self.ctx._presentation_generation

        await self.ctx.connection_closed()

        self.assertEqual((event,), self.ctx.dispatch_ledger.events)
        self.assertEqual("disconnected", self.ctx.overlay_state.connection_status)
        self.assertEqual("disconnected", self.overlay.published[-1].connection_status)
        self.assertGreater(self.overlay.published[-1].generation, previous_generation)

    async def test_action_poll_applies_filter_and_overlay_failure_isolated(self):
        self.overlay.actions = [OverlayAction(
            "filter", "sent", self.ctx._presentation_generation,
        )]
        self.overlay.publish_succeeds = False

        await self.ctx.process_overlay_actions_once()

        self.assertEqual(OverlayFilter.SENT, self.ctx.overlay_state.active_filter)
        self.assertIn("regular client", self.ctx.last_overlay_error)

    def test_health_failure_sets_fallback_status_without_raising(self):
        self.overlay.raise_on_health_check = True

        self.ctx.check_overlay_health()

        self.assertEqual(1, self.overlay.health_checks)
        self.assertIn("health", self.ctx.last_overlay_error)

    async def test_health_restart_invalidates_actions_buffered_by_old_child(self):
        self.ctx.start_overlay()
        buffered_generation = self.ctx._presentation_generation
        self.overlay.session_generation += 1
        self.overlay.actions = [OverlayAction("open", generation=buffered_generation)]

        self.ctx.check_overlay_health()
        await self.ctx.process_overlay_actions_once()

        self.assertGreater(self.ctx._presentation_generation, buffered_generation)
        self.assertFalse(self.ctx.overlay_state.is_open)

    async def test_sticker_delivery_preserves_matching_levels_without_reload(self):
        sticker_id = ITEM_NAME_TO_ID["I Sticker"]
        self.ctx.item_names.names[sticker_id] = "I Sticker"
        self.ctx.items_received = [make_network_item(
            item=sticker_id, location=9001, player=2, flags=1,
        )]
        installed = json.dumps(
            render_levels({"Bender Access"}, 0), separators=(",", ":"),
        )
        self.ctx.levels_path.write_text(installed, encoding="utf-8")

        await self.ctx.reconcile_received()

        self.assertEqual(installed, self.ctx.levels_path.read_text(encoding="utf-8"))
        self.assertFalse(self.ctx.overlay_state.reload_required)

    async def test_reconnect_preserves_matching_levels_without_reload(self):
        installed = json.dumps(
            render_levels({"Bender Access"}, 0), separators=(",", ":"),
        )
        self.ctx.levels_path.write_text(installed, encoding="utf-8")
        self.ctx.connected_identity = None

        self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        self.assertEqual(installed, self.ctx.levels_path.read_text(encoding="utf-8"))
        self.assertFalse(self.ctx.overlay_state.reload_required)

    async def test_connected_repair_of_corrupt_levels_requires_reload(self):
        self.ctx.levels_path.write_text("{not-json", encoding="utf-8")
        self.ctx.connected_identity = None

        self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        levels = json.loads(self.ctx.levels_path.read_text(encoding="utf-8"))
        self.assertEqual("I", levels[0]["text"])
        self.assertTrue(self.ctx.overlay_state.reload_required)

    async def test_unlock_render_sets_reload_required_snapshot(self):
        rotation_id = ITEM_NAME_TO_ID["Rotation Access"]
        self.ctx.item_names.names[rotation_id] = "Rotation Access"
        self.ctx.items_received = [make_network_item(
            item=rotation_id, location=9001, player=2, flags=1,
        )]

        await self.ctx.reconcile_received()

        levels = json.loads(self.ctx.levels_path.read_text(encoding="utf-8"))
        self.assertNotIn("Rotate_cw", levels[0]["module_counts"])
        self.assertTrue(self.ctx.overlay_state.reload_required)
        self.assertTrue(self.overlay.published[-1].reload_required)

    async def test_overlay_command_supports_exact_controls_and_help(self):
        processor = WordFactoriCommandProcessor(self.ctx)

        task = self.capture_scheduled_task(lambda: processor._cmd_wf_overlay("show"))
        await task
        self.assertTrue(self.ctx.overlay_state.is_open)
        task = self.capture_scheduled_task(lambda: processor._cmd_wf_overlay("hide"))
        await task
        self.assertFalse(self.ctx.overlay_state.is_open)
        task = self.capture_scheduled_task(lambda: processor._cmd_wf_overlay("restart"))
        await task
        self.assertEqual(1, len(self.overlay.restarted))
        self.assertIsNotNone(self.ctx.overlay_action_task)
        processor._cmd_wf_overlay("status")
        self.assertIn("overlay", processor.outputs[-1].lower())
        processor._cmd_wf_overlay("bogus")
        self.assertEqual(
            "Usage: /wf_overlay [status|show|hide|restart]",
            processor.outputs[-1],
        )
        await self.ctx.shutdown()

    async def test_shutdown_cancels_action_task_and_stops_overlay_even_if_base_fails(self):
        self.ctx.start_overlay()
        task = self.ctx.overlay_action_task

        with patch.object(
            _CommonContext, "shutdown", AsyncMock(side_effect=RuntimeError("base failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "base failed"):
                await self.ctx.shutdown()

        self.assertTrue(task.done())
        self.assertEqual(1, self.overlay.stopped)

    def test_launcher_component_registers_one_client_and_imports_renderer_without_kivy(self):
        launcher = types.ModuleType("worlds.LauncherComponents")
        launcher.components = []
        launcher.Type = types.SimpleNamespace(CLIENT="client")
        launcher.Component = lambda *args, **kwargs: types.SimpleNamespace(
            name=args[0], **kwargs,
        )
        launcher.launch = lambda *args, **kwargs: None
        worlds = types.ModuleType("worlds")
        worlds.__path__ = []
        removed = {
            name: sys.modules.pop(name, None)
            for name in ("word_factori.Components", "word_factori.overlay_renderer", "kivy")
        }
        package = sys.modules["word_factori"]
        renderer_attribute = getattr(package, "overlay_renderer", None)
        if hasattr(package, "overlay_renderer"):
            delattr(package, "overlay_renderer")
        try:
            with patch.dict(sys.modules, {
                "worlds": worlds,
                "worlds.LauncherComponents": launcher,
            }):
                importlib.import_module("word_factori.Components")
                self.assertEqual(["Word Factori Client"], [
                    component.name for component in launcher.components
                ])
                self.assertIn("word_factori.overlay_renderer", sys.modules)
                self.assertNotIn("kivy", sys.modules)
        finally:
            for name, module in removed.items():
                sys.modules.pop(name, None)
                if module is not None:
                    sys.modules[name] = module
            if renderer_attribute is not None:
                package.overlay_renderer = renderer_attribute

    async def test_manual_check_is_retained_until_server_acknowledges_it(self):
        location_id = LOCATIONS[0].code
        self.ctx.missing_locations = {location_id}
        await self.ctx.report_indices({0})
        self.assertIn(location_id, self.ctx.bridge_state.pending_checks)
        self.assertTrue(any(message["cmd"] == "LocationChecks" for message in self.ctx.sent_messages))

        self.ctx.checked_locations = {location_id}
        self.ctx.on_package("RoomUpdate", {})
        self.assertNotIn(location_id, self.ctx.bridge_state.pending_checks)

    async def test_pending_manual_check_does_not_cross_seed_boundary(self):
        location_id = LOCATIONS[0].code
        self.ctx.missing_locations = {location_id}
        await self.ctx.report_indices({0})
        self.assertIn(location_id, self.ctx.bridge_state.pending_checks)

        self.ctx.sent_messages.clear()
        self.ctx.room_seed_name = "Seed-B"
        self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertFalse(any(message["cmd"] == "LocationChecks" for message in self.ctx.sent_messages))

    async def test_goal_resends_only_for_same_seed_team_and_slot(self):
        final_id = LOCATIONS[29].code
        self.ctx.missing_locations = {final_id}
        await self.ctx.report_indices({29})
        first_identity = self.ctx.goal_identity
        first_count = sum(message["cmd"] == "StatusUpdate" for message in self.ctx.sent_messages)
        self.assertEqual(1, first_count)

        self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        same_room_count = sum(message["cmd"] == "StatusUpdate" for message in self.ctx.sent_messages)
        self.assertEqual(2, same_room_count)

        self.ctx.room_seed_name = "Seed-B"
        self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        new_room_count = sum(message["cmd"] == "StatusUpdate" for message in self.ctx.sent_messages)
        self.assertEqual(same_room_count, new_room_count)
        self.assertNotEqual(first_identity, self.ctx.current_identity())

    async def test_manifest_mismatch_blocks_checks_and_mod_rewrite(self):
        location_id = LOCATIONS[30].code
        self.ctx.bridge_state = BridgeState(pending_checks=frozenset({location_id}))
        self.ctx.slot_data["manifest_digest"] = "0" * 64
        self.ctx.missing_locations = {location_id}

        await self.ctx.report_indices({30})
        await self.ctx.reconcile_received()

        self.assertEqual(frozenset({location_id}), self.ctx.bridge_state.pending_checks)
        self.assertFalse(any(message["cmd"] == "LocationChecks" for message in self.ctx.sent_messages))
        self.assertFalse(self.ctx.levels_path.exists())
        self.assertIn("Campaign mismatch", self.ctx.last_bridge_error)

    async def test_discovery_check_is_queued_once_and_acknowledged(self):
        location_id = LOCATIONS[30].code
        self.ctx.missing_locations = {location_id}
        await self.ctx.report_indices({30})
        await self.ctx.report_indices({30})
        checks = [message for message in self.ctx.sent_messages if message["cmd"] == "LocationChecks"]
        self.assertEqual(1, len(checks))
        self.assertIn(location_id, self.ctx.bridge_state.pending_checks)

        self.ctx.checked_locations = {location_id}
        self.ctx.on_package("RoomUpdate", {})
        self.assertNotIn(location_id, self.ctx.bridge_state.pending_checks)

    async def test_unbound_existing_progress_is_rejected(self):
        self.write_active_slot("old-game-slot", {0, 29})
        location_id = LOCATIONS[0].code
        self.ctx.missing_locations = {location_id}

        await self.ctx.report_indices({0})

        self.assertIsNone(self.ctx.bridge_state.game_slot_id)
        self.assertFalse(any(message["cmd"] == "LocationChecks" for message in self.ctx.sent_messages))
        self.assertIn("prior completions", self.ctx.last_bridge_error)

    async def test_switching_from_bound_game_slot_pauses_checks(self):
        first_id = LOCATIONS[0].code
        self.ctx.missing_locations = {first_id}
        await self.ctx.report_indices({0})
        self.assertEqual("game-slot-A", self.ctx.bridge_state.game_slot_id)

        self.ctx.sent_messages.clear()
        self.write_active_slot("game-slot-B", set())
        second_id = LOCATIONS[1].code
        self.ctx.missing_locations = {second_id}
        await self.ctx.report_indices({1})

        self.assertEqual("game-slot-A", self.ctx.bridge_state.game_slot_id)
        self.assertFalse(any(message["cmd"] == "LocationChecks" for message in self.ctx.sent_messages))
        self.assertIn("different Word Factori save", self.ctx.last_bridge_error)


if __name__ == "__main__":
    unittest.main()
