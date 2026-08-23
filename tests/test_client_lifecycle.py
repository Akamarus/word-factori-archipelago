import argparse
import asyncio
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
    def lookup_in_game(self, item_id):
        return str(item_id)


class _CommonContext:
    def __init__(self, server_address=None, password=None):
        self.server_address = server_address
        self.password = password
        self.auth = None
        self.team = None
        self.slot = None
        self.server = object()
        self.items_received = []
        self.item_names = _NameLookup()
        self.checked_locations = set()
        self.missing_locations = set()
        self.locations_checked = set()
        self.finished_game = False
        self.sent_messages = []
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

    async def shutdown(self):
        return None

    def run_cli(self):
        return None


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
from word_factori.data import CAMPAIGN_DIGEST, CAMPAIGN_ID, CAMPAIGN_VERSION, LOCATIONS


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
