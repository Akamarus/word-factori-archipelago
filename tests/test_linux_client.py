"""Native Linux client behavior with local, isolated Proton fixtures."""
import asyncio
import argparse
import hashlib
import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Provides the same lightweight Archipelago client scaffold as lifecycle tests.
from tests.test_client_lifecycle import _FakeOverlaySupervisor, make_network_item
from word_factori.client import WordFactoriContext, launch_client
from word_factori.data import CAMPAIGN_DIGEST, CAMPAIGN_ID, CAMPAIGN_VERSION, LOCATIONS
from word_factori.enhanced_runtime import PATCH_PROTOCOL, RECEIPT_NAME
from word_factori.campaign import campaign_for_level_set
from word_factori.layout import build_layout, layout_slot_data
from word_factori.platform_paths import InstallationPaths, save_installation


class LinuxClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.platform = patch("word_factori.client.sys.platform", "linux")
        self.platform.start()
        self.addCleanup(self.platform.stop)
        self.config = self.root / "selected.json"
        self.game = self.root / "game" / "data.win"
        self.game.parent.mkdir()
        self.game.write_bytes(b"patched fixture")
        self.prefix = self.root / "pfx"
        self.factori = self.prefix / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "factori"
        self.factori.mkdir(parents=True)
        self.paths = InstallationPaths(self.game, self.prefix, self.factori)
        self.overlay = _FakeOverlaySupervisor()

    def context(self):
        ctx = WordFactoriContext("localhost:38281", None, overlay=self.overlay,
                                 installation_config=self.config)
        ctx.auth = "Factory Player"
        ctx.team = 0
        ctx.slot = 1
        ctx.room_seed_name = "Seed-A"
        ctx.slot_data = {"goal": 1, "campaign_count": 25, "campaign_id": CAMPAIGN_ID,
                         "manifest_version": CAMPAIGN_VERSION,
                         "manifest_digest": CAMPAIGN_DIGEST, "level_count": len(LOCATIONS)}
        ctx.connected_identity = ctx.current_identity()
        return ctx

    def enhanced_room(self, ctx):
        manifest = campaign_for_level_set("discovery_labs")
        layout = build_layout(manifest, "discovery_labs", "shuffled_pages", random.Random(41),
                              integration_mode="enhanced")
        ctx.slot_data.update(**layout_slot_data(layout), manifest_digest=layout.digest,
                             level_set="discovery_labs")
        ctx.connected_identity = ctx.current_identity()
        return layout

    def install(self):
        save_installation(self.paths, self.config)
        mod = self.paths.mod_folder
        mod.mkdir(parents=True)
        digest = hashlib.sha256(self.game.read_bytes()).hexdigest()
        backup = self.game.with_name("data.wf-ap-original.win")
        backup.write_bytes(b"original fixture")
        worlds = self.root / "custom_worlds"
        worlds.mkdir(exist_ok=True)
        (mod / RECEIPT_NAME).write_text(json.dumps({
            "protocol": PATCH_PROTOCOL, "original_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
            "patched_sha256": digest, "game_data": str(self.game), "platform": "linux",
            "prefix": str(self.prefix), "factori_root": str(self.factori), "ap_worlds": str(worlds),
        }))
        original = patch("word_factori.enhanced_runtime.ORIGINAL_SHA256", hashlib.sha256(backup.read_bytes()).hexdigest())
        patched = patch("word_factori.enhanced_runtime.PATCHED_SHA256", digest)
        original.start()
        self.addCleanup(original.stop)
        return patched

    async def test_missing_config_has_setup_error_and_no_guessed_appdata_writes(self):
        guessed = self.root / "guessed-local-appdata"
        with patch.dict(os.environ, {"LOCALAPPDATA": str(guessed)}):
            ctx = self.context()
            self.assertFalse(ctx.prepare_selected_campaign())
            self.assertIn("setup", ctx.last_bridge_error.lower())
            ctx.on_package("Connected", {"slot_data": ctx.slot_data})
            ctx.on_package("ReceivedItems", {})
            await asyncio.sleep(0.05)
        self.assertFalse(guessed.exists())
        self.assertFalse((self.root / "factori").exists())

    async def test_invalid_room_does_not_overwrite_missing_setup_error(self):
        ctx = self.context()
        ctx.on_package("Connected", {"slot_data": {"manifest_digest": "bad"}})
        self.assertIn("setup", ctx.last_bridge_error.lower())
        self.assertNotIn("Campaign mismatch:", ctx.last_bridge_error)

    async def test_missing_patch_is_not_campaign_mismatch(self):
        save_installation(self.paths, self.config)
        ctx = self.context()
        self.enhanced_room(ctx)
        self.assertFalse(ctx.prepare_selected_campaign())
        self.assertIn("patch", ctx.last_bridge_error.lower())
        self.assertNotIn("Campaign mismatch:", ctx.last_bridge_error)
        ctx.on_package("Connected", {"slot_data": ctx.slot_data})
        self.assertNotIn("Campaign mismatch:", ctx.last_bridge_error)

    async def test_linux_cannot_write_legacy_levels_without_native_patch(self):
        save_installation(self.paths, self.config)
        ctx = self.context()
        self.assertFalse(ctx.prepare_selected_campaign())
        self.assertFalse(ctx.levels_path.exists())
        self.assertIn("patch", ctx.last_bridge_error.lower())

    async def test_configured_paths_support_items_checks_reconnect_and_goal(self):
        with self.install():
            ctx = self.context()
            self.enhanced_room(ctx)
            account = self.factori / "account"
            save = account / "mods" / "word factori archipelago" / "save.json"
            save.parent.mkdir(parents=True)
            save.write_text(json.dumps({"slots": {"0": {"slot_is_active": 1,
                "random_id": "linux-slot", "beaten_levels": {}}}}))
            (self.factori / "user_ref.json").write_text(json.dumps({"most_recent_steam": "account"}))
            (self.factori / "mods.json").write_text(json.dumps({"folder": "mods\\word factori archipelago"}))
            first_code = ctx.active_locations()[0].code
            ctx.missing_locations = {first_code}
            self.assertTrue(ctx.prepare_selected_campaign())
            self.assertTrue(ctx.selected_mod())
            (self.factori / "mods.json").write_text(json.dumps({"folder":
                r"C:\users\steamuser\AppData\Local\factori\mods\word factori archipelago"}))
            self.assertTrue(ctx.selected_mod())
            (self.factori / "mods.json").write_text(json.dumps({"folder": r"C:\users\other\AppData\Local\factori\mods\word factori archipelago"}))
            self.assertFalse(ctx.selected_mod())
            (self.factori / "mods.json").write_text(json.dumps({"folder": "mods\\word factori archipelago"}))
            ctx.on_package("Connected", {"slot_data": ctx.slot_data})
            await asyncio.sleep(0.1)
            self.assertTrue((ctx.mod_folder / "archipelago_runtime.json").is_file())
            await ctx.scan_once()
            self.assertIsNotNone(ctx.bridge_state.game_slot_id)
            save.write_text(json.dumps({"slots": {"0": {"slot_is_active": 1,
                "random_id": "linux-slot", "beaten_levels": {"0": 1}}}}))
            await ctx.scan_once()
            self.assertIn(first_code, ctx.bridge_state.pending_checks)
            final = next(location for location in ctx.active_locations() if location.stable_key == "pitchfork-final")
            ctx.missing_locations.add(final.code)
            await ctx.report_indices({final.slot_index})
            self.assertTrue(any(message.get("cmd") == "StatusUpdate" for message in ctx.sent_messages))
            self.assertTrue(any(message["cmd"] == "LocationChecks" for message in ctx.sent_messages))
            ctx.items_received = [make_network_item(item=7001, location=first_code, player=1)]
            await ctx.reconcile_received()
            self.assertTrue(ctx.bridge_state.applied)
            ctx.on_package("Connected", {"slot_data": ctx.slot_data})
            await asyncio.sleep(0.1)
            self.assertIn(first_code, ctx.bridge_state.pending_checks)

    async def test_argument_parser_forwards_alternate_installation_config(self):
        with self.install():
            made = []
            real_context = WordFactoriContext

            def context_factory(address, password, *, installation_config):
                ctx = real_context(address, password, overlay=self.overlay,
                                   installation_config=installation_config)
                made.append(ctx)
                ctx.exit_event.set()
                return ctx

            def base_parser(description=None):
                parser = argparse.ArgumentParser(description=description)
                parser.add_argument("--connect")
                parser.add_argument("--password")
                return parser

            with patch("word_factori.client.WordFactoriContext", side_effect=context_factory), \
                 patch("word_factori.client.get_base_parser", side_effect=base_parser):
                await asyncio.to_thread(launch_client, "--wf-config", str(self.config))
            self.assertEqual(self.paths.factori_root, made[0].factori_root)

    async def check_redirected_mod_is_refused(self, redirect_parent):
        from tests.test_platform_paths import PlatformPathsTests
        with self.install():
            ctx = self.context()
            self.enhanced_room(ctx)
            source = self.paths.mod_folder.parent if redirect_parent else self.paths.mod_folder
            destination = self.root / "redirected"
            source.rename(destination)
            PlatformPathsTests.directory_alias(self, destination, source)
            before = {p.relative_to(destination): p.read_bytes()
                      for p in destination.rglob("*") if p.is_file()}
            from word_factori.client import logger
            with self.assertLogs(logger, level="WARNING"):
                self.assertFalse(ctx.prepare_selected_campaign())
            self.assertIn("unsafe", ctx.last_bridge_error.lower())
            self.assertEqual(before, {p.relative_to(destination): p.read_bytes()
                                     for p in destination.rglob("*") if p.is_file()})

    async def test_redirected_mod_folder_cannot_receive_client_writes(self):
        await self.check_redirected_mod_is_refused(False)

    async def test_redirected_mod_parent_cannot_receive_client_writes(self):
        await self.check_redirected_mod_is_refused(True)

    async def check_redirected_state_is_refused(self, dispatch_only):
        from tests.test_platform_paths import PlatformPathsTests
        from word_factori.bridge import save_state
        from word_factori.dispatch_store import save_ledger
        with self.install():
            ctx = self.context()
            self.enhanced_room(ctx)
            destination = self.root / "outside-state"
            destination.mkdir()
            marker = destination / "keep.txt"
            marker.write_bytes(b"unchanged")
            alias = ctx.state_root / "dispatch" if dispatch_only else ctx.state_root
            PlatformPathsTests.directory_alias(self, destination, alias)
            if not dispatch_only:
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    save_state(ctx.state_path(), ctx.bridge_state)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                save_ledger(ctx.dispatch_path(), ctx.dispatch_ledger)
            self.assertEqual([marker], list(destination.iterdir()))
            self.assertEqual(b"unchanged", marker.read_bytes())

    async def test_redirected_state_root_cannot_receive_client_writes(self):
        await self.check_redirected_state_is_refused(False)

    async def test_redirected_dispatch_cannot_receive_client_writes(self):
        await self.check_redirected_state_is_refused(True)

    async def test_overlay_never_starts_or_restarts_on_linux(self):
        ctx = self.context()
        ctx.start_overlay()
        await ctx.overlay_control("show")
        await ctx.overlay_control("restart")
        ctx.check_overlay_health()
        self.assertEqual([], self.overlay.started)
        self.assertEqual([], self.overlay.restarted)
        self.assertEqual(0, self.overlay.health_checks)
        self.assertIn("regular client", ctx.overlay_status_text())


if __name__ == "__main__":
    unittest.main()
