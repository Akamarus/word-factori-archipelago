import argparse
import asyncio
from dataclasses import FrozenInstanceError
import json
import logging
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


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
        self.exit_event = asyncio.Event()

    async def get_username(self):
        return None

    async def send_connect(self):
        return None

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

    async def shutdown(self):
        return None

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

    def output(self, text):
        return None


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

from word_factori.client import WordFactoriContext
from word_factori.bridge import BridgeState
from word_factori.data import (
    CAMPAIGN_DIGEST, CAMPAIGN_ID, CAMPAIGN_VERSION, ITEM_NAME_TO_ID, LOCATIONS,
)
from word_factori.dispatch import DispatchDirection
from word_factori.dispatch_store import DispatchLedger


class ClientLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {"LOCALAPPDATA": self.directory.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.ctx = WordFactoriContext("localhost:38281", None)
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

    async def test_dispatch_received_items_are_idempotent_across_reconnect(self):
        first = make_network_item(item=7001, location=9001, player=2, flags=1)
        self.ctx.items_received = [first]
        self.ctx.connected_identity = None

        self.ctx.on_package("Connected", {"slot_data": self.ctx.slot_data})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(1, len(self.ctx.dispatch_ledger.events))
        self.assertEqual((), self.ctx.pending_overlay_events)

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
        self.assertEqual(1, len(self.ctx.pending_overlay_events))

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
