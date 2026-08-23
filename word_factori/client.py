from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import json
import os
import re
import sys
from pathlib import Path

import Utils
from CommonClient import (
    ClientCommandProcessor,
    CommonContext,
    get_base_parser,
    gui_enabled,
    logger,
    server_loop,
)
from NetUtils import ClientStatus

from .bridge import (
    BridgeState,
    ReceivedItem,
    acknowledge_checks,
    bind_game_slot,
    load_state,
    queue_checks,
    reconcile,
    save_state,
)
from .client_core import (
    campaign_compatible,
    goal_reached,
    inventory_view,
    mod_is_selected,
    parse_connection_url,
    resolve_game_slot_binding,
    state_identity,
)
from .data import GAME, ITEM_NAME_TO_ID, LOCATIONS
from .dispatch import DispatchDirection, DispatchEvent, received_event, sent_event
from .dispatch_store import (
    DispatchLedger, ledger_path, load_ledger, reconcile_received, record_event,
    save_ledger,
)
from .mod import render_levels, write_levels
from .save import ActiveSlot, find_save, read_active_slot

MOD_FOLDER = "word factori archipelago"
CAMPAIGN_MISMATCH = (
    "Campaign mismatch: this Archipelago room requires a different Word Factori hybrid mod. "
    "Reinstall the release matching the room before scanning or completing levels."
)


@dataclass(frozen=True)
class _DispatchItemSnapshot:
    item: int
    location: int
    player: int
    flags: int


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "slot"


class WordFactoriCommandProcessor(ClientCommandProcessor):
    ctx: "WordFactoriContext"

    def _cmd_wf_complete(self, identifier: str = "") -> None:
        """Manually report a completed level by 1-based number, target word, or location name."""
        try:
            index = self.ctx.resolve_location(identifier)
        except ValueError as error:
            self.output(str(error))
            return
        asyncio.create_task(self.ctx.report_indices({index}))

    def _cmd_wf_scan(self) -> None:
        """Scan the active Word Factori save once, even if mod selection cannot be verified."""
        asyncio.create_task(self.ctx.scan_once(ignore_selection_guard=True))

    def _cmd_wf_status(self) -> None:
        """Show bridge, mod-selection, and received-item status."""
        self.output(self.ctx.status_text())


class WordFactoriContext(CommonContext):
    command_processor = WordFactoriCommandProcessor
    game = GAME
    items_handling = 0b111
    want_slot_data = True

    def __init__(self, server_address: str | None, password: str | None):
        super().__init__(server_address, password)
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self.factori_root = local / "factori"
        self.mod_folder = self.factori_root / "mods" / MOD_FOLDER
        self.levels_path = self.mod_folder / "levels.json"
        self.campaign_path = self.mod_folder / "archipelago_campaign.json"
        self.mods_path = self.factori_root / "mods.json"
        self.state_root = self.factori_root / "archipelago"
        self.slot_data: dict = {}
        self.bridge_state = BridgeState.empty()
        self.last_render_signature: tuple[str, ...] | None = None
        self.last_bridge_error: str | None = None
        self.room_seed_name: str | None = None
        self.connected_identity: str | None = None
        self.goal_identity: str | None = None
        self.dispatch_ledger = DispatchLedger.empty("disconnected")
        self.pending_overlay_events: tuple[DispatchEvent, ...] = ()
        self._dispatch_lock = asyncio.Lock()

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "RoomInfo":
            seed_name = args.get("seed_name")
            self.room_seed_name = str(seed_name) if seed_name is not None else None
        elif cmd == "Connected":
            self.slot_data = dict(args.get("slot_data") or {})
            self.connected_identity = self.current_identity()
            try:
                self.bridge_state = load_state(self.state_path())
            except (OSError, ValueError, TypeError) as error:
                self._bridge_warning(f"Ignoring invalid bridge sidecar; server state will rebuild it: {error}")
                self.bridge_state = BridgeState.empty()
            if not self.compatible_campaign():
                self._bridge_warning(CAMPAIGN_MISMATCH)
                return
            self.bridge_state = acknowledge_checks(self.bridge_state, self.checked_locations)
            save_state(self.state_path(), self.bridge_state)
            self.last_render_signature = None
            asyncio.create_task(self._connected_reconcile(
                self.connected_identity, self._snapshot_dispatch_items(self.items_received),
                frozenset(self.checked_locations),
            ))
            asyncio.create_task(self._resend_pending_checks())
            if self.goal_identity == self.connected_identity:
                asyncio.create_task(self._send_goal())
        elif cmd == "ReceivedItems":
            asyncio.create_task(self._received_items_reconcile(
                self.connected_identity, self._snapshot_dispatch_items(self.items_received),
            ))
        elif cmd == "LocationInfo" and self.connected_identity is not None:
            asyncio.create_task(self._backfill_location_info_safely(
                self.connected_identity,
                self._snapshot_dispatch_items(args.get("locations") or ()),
                frozenset(self.checked_locations),
            ))
        elif cmd == "RoomUpdate":
            if self.connected_identity is not None and self.compatible_campaign():
                self.bridge_state = acknowledge_checks(self.bridge_state, self.checked_locations)
                save_state(self.state_path(), self.bridge_state)

    def state_path(self) -> Path:
        identity = self.connected_identity or self.current_identity()
        return self.state_root / f"{_safe_filename(identity)}.json"

    def dispatch_path(self, identity: str | None = None) -> Path:
        identity = identity or self.connected_identity or self.current_identity()
        return ledger_path(self.state_root, _safe_filename(identity))

    def current_identity(self) -> str:
        return state_identity(self.room_seed_name, self.team, self.slot, self.auth)

    def _snapshot_dispatch_item(self, item) -> _DispatchItemSnapshot:
        return _DispatchItemSnapshot(
            int(item.item), int(item.location), int(item.player), int(item.flags),
        )

    def _snapshot_dispatch_items(self, items) -> tuple[_DispatchItemSnapshot, ...]:
        snapshots = []
        for item in items:
            try:
                snapshots.append(self._snapshot_dispatch_item(item))
            except (AttributeError, TypeError, ValueError) as error:
                logger.warning("Ignoring malformed dispatch item metadata: %s", error)
        return tuple(snapshots)

    def _lookup_item_name(self, item_id: int) -> str:
        try:
            name = self.item_names.lookup_in_game(item_id)
        except (LookupError, TypeError, ValueError):
            name = None
        return name if isinstance(name, str) and name.strip() else f"Item {item_id}"

    def _lookup_location_name(self, location_id: int, slot: int) -> str:
        try:
            name = self.location_names.lookup_in_slot(location_id, slot)
        except (LookupError, TypeError, ValueError):
            name = None
        return name if isinstance(name, str) and name.strip() else f"Location {location_id}"

    def _slot_details(self, slot: int) -> tuple[str, str]:
        info = self.slot_info.get(slot)
        name = getattr(info, "name", None)
        game = getattr(info, "game", None)
        if not isinstance(name, str) or not name.strip():
            name = f"Player {slot}"
        if not isinstance(game, str) or not game.strip():
            game = "Unknown Game"
        return name, game

    def dispatch_received_event(
        self, index: int, item, identity: str | None = None,
    ) -> DispatchEvent | None:
        item_name = self._lookup_item_name(item.item)
        if item.item == ITEM_NAME_TO_ID["Bender Access"] or item_name == "Bender Access":
            return None
        player_name, player_game = self._slot_details(item.player)
        return received_event(
            identity or self.connected_identity or self.current_identity(), index,
            item.item, item_name, item.player, player_name, player_game,
            item.location, self._lookup_location_name(item.location, item.player),
            None, self_item=self.slot_concerns_self(item.player),
        )

    def _dispatch_room_matches(self, identity: str) -> bool:
        return (
            self.connected_identity == identity
            and self.dispatch_ledger.identity == identity
        )

    async def reconcile_dispatches(
        self, identity: str | None = None, items=None,
    ) -> None:
        identity = identity or self.connected_identity or self.current_identity()
        items = tuple(self.items_received) if items is None else tuple(items)
        async with self._dispatch_lock:
            if not self._dispatch_room_matches(identity):
                return
            events = tuple(
                event for index, item in enumerate(items)
                if (event := self.dispatch_received_event(index, item, identity)) is not None
            )
            update = reconcile_received(self.dispatch_ledger, events)
            self.dispatch_ledger = update.state
            self.pending_overlay_events += update.notify
            save_ledger(self.dispatch_path(identity), self.dispatch_ledger)

    async def _connected_reconcile(self, identity: str, items, checked_locations) -> None:
        await self.reconcile_received()
        try:
            async with self._dispatch_lock:
                if self.connected_identity != identity:
                    return
                try:
                    ledger = load_ledger(self.dispatch_path(identity), identity)
                except (OSError, ValueError, TypeError) as error:
                    logger.warning("Ignoring invalid dispatch ledger; room history will rebuild it: %s", error)
                    ledger = DispatchLedger.empty(identity)
                events = tuple(
                    event for index, item in enumerate(items)
                    if (event := self.dispatch_received_event(index, item, identity)) is not None
                )
                update = reconcile_received(ledger, events)
                if self.connected_identity != identity or update.state.identity != identity:
                    return
                self.pending_overlay_events = ()
                self.dispatch_ledger = update.state
                self.pending_overlay_events += update.notify
                save_ledger(self.dispatch_path(identity), self.dispatch_ledger)
        except Exception:
            logger.exception("Dispatch history reconciliation failed; Word Factori unlocks remain active.")
        try:
            if not self._dispatch_room_matches(identity):
                return
            await self.request_checked_location_info(identity, checked_locations)
        except Exception:
            logger.exception("Checked-location dispatch history could not be requested.")

    async def _received_items_reconcile(self, identity: str | None, items) -> None:
        await self.reconcile_received()
        if identity is None:
            return
        try:
            await self.reconcile_dispatches(identity, items)
        except Exception:
            logger.exception("Dispatch history reconciliation failed; Word Factori unlocks remain active.")

    async def request_checked_location_info(
        self, identity: str | None = None, checked_locations=None,
    ) -> None:
        identity = identity or self.connected_identity or self.current_identity()
        checked_locations = (
            frozenset(self.checked_locations)
            if checked_locations is None else frozenset(checked_locations)
        )
        local_ids = {location.code for location in LOCATIONS}
        locations = sorted(checked_locations & local_ids)
        if locations and self._dispatch_room_matches(identity):
            await self.send_msgs([{
                "cmd": "LocationScouts", "locations": locations,
                "create_as_hint": 0,
            }])

    def dispatch_sent_event(
        self, item, *, historical: bool, identity: str | None = None,
    ) -> DispatchEvent:
        recipient_name, recipient_game = self._slot_details(item.player)
        event = sent_event(
            identity or self.connected_identity or self.current_identity(), item.location,
            item.item, self._lookup_item_name(item.item), item.player,
            recipient_name, recipient_game,
            self._lookup_location_name(item.location, self.slot),
            self.slot_concerns_self(item.player), None,
        )
        return replace(event, historical=historical)

    async def _backfill_location_info_safely(
        self, identity: str, items, checked_locations,
    ) -> None:
        try:
            local_ids = {location.code for location in LOCATIONS}
            checked = checked_locations & local_ids
            async with self._dispatch_lock:
                if not self._dispatch_room_matches(identity):
                    return
                changed = False
                for item in items:
                    if getattr(item, "location", None) not in checked:
                        continue
                    event = self.dispatch_sent_event(
                        item, historical=True, identity=identity,
                    )
                    if event.direction is DispatchDirection.SELF and any(
                        existing.receive_index is not None
                        and existing.item_id == event.item_id
                        and existing.location_id == event.location_id
                        for existing in self.dispatch_ledger.events
                    ):
                        continue
                    update = record_event(self.dispatch_ledger, event, notify=False)
                    changed = changed or update.state is not self.dispatch_ledger
                    self.dispatch_ledger = update.state
                if changed:
                    save_ledger(self.dispatch_path(identity), self.dispatch_ledger)
        except Exception:
            logger.exception("Checked-location dispatch history could not be recorded.")

    async def _record_dispatch_event_safely(
        self, identity: str, event: DispatchEvent, *, notify: bool,
    ) -> None:
        try:
            async with self._dispatch_lock:
                if not self._dispatch_room_matches(identity):
                    return
                update = record_event(self.dispatch_ledger, event, notify=notify)
                self.dispatch_ledger = update.state
                self.pending_overlay_events += update.notify
                save_ledger(self.dispatch_path(identity), self.dispatch_ledger)
        except Exception:
            logger.exception("Dispatch packet could not be recorded; standard client output remains active.")

    def record_item_send(self, args: dict, identity: str | None = None) -> None:
        identity = identity or self.connected_identity or self.current_identity()
        item = args["item"]
        receiving = args["receiving"]
        if self.slot_concerns_self(receiving):
            return
        item_name = self._lookup_item_name(item.item)
        if item.item == ITEM_NAME_TO_ID["Bender Access"] or item_name == "Bender Access":
            return
        recipient_name, recipient_game = self._slot_details(receiving)
        event = sent_event(
            identity, item.location,
            item.item, item_name, receiving, recipient_name, recipient_game,
            self._lookup_location_name(item.location, item.player), False, None,
        )
        asyncio.create_task(self._record_dispatch_event_safely(
            identity, event, notify=True,
        ))

    def on_print_json(self, args: dict) -> None:
        super().on_print_json(args)
        if args.get("type") != "ItemSend" or self.connected_identity is None:
            return
        item = args.get("item")
        receiving = args.get("receiving")
        if item is None or not isinstance(receiving, int):
            return
        try:
            if not self.slot_concerns_self(item.player) and not self.slot_concerns_self(receiving):
                return
            self.record_item_send(args, self.connected_identity)
        except Exception:
            logger.exception("Dispatch packet could not be recorded; standard client output remains active.")

    def network_items(self) -> list[ReceivedItem]:
        received = [ReceivedItem(-1, "Bender Access")]
        for index, item in enumerate(self.items_received):
            received.append(ReceivedItem(index, self.item_names.lookup_in_game(item.item)))
        return received

    async def reconcile_received(self) -> None:
        if not self.compatible_campaign():
            self._bridge_warning(CAMPAIGN_MISMATCH)
            return
        result = reconcile(self.bridge_state, self.network_items(), set(), set(), authoritative=True)
        self.bridge_state = result.state
        save_state(self.state_path(), self.bridge_state)
        view = inventory_view(ReceivedItem(index, name) for index, name in self.bridge_state.applied.items())
        signature = tuple(sorted(self.bridge_state.applied.values()))
        if signature != self.last_render_signature:
            levels = render_levels(view.owned_machines, view.world_access)
            write_levels(self.levels_path, levels)
            self.last_render_signature = signature
            logger.info("Word Factori unlocks updated. Reload the AP mod or reselect its save slot in game.")

    def selected_mod(self) -> bool:
        try:
            payload = json.loads(self.mods_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return mod_is_selected(payload, str(self.mod_folder))

    def installed_campaign(self) -> dict:
        try:
            payload = json.loads(self.campaign_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def compatible_campaign(self) -> bool:
        return campaign_compatible(self.slot_data, self.installed_campaign())

    def ensure_game_slot_binding(self) -> ActiveSlot | None:
        try:
            active = read_active_slot(
                find_save(self.factori_root.parent, Path("mods") / MOD_FOLDER)
            )
            resolved = resolve_game_slot_binding(self.bridge_state.game_slot_id, active)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self._bridge_warning(f"Word Factori save binding paused: {error}")
            return None
        if self.bridge_state.game_slot_id is None:
            self.bridge_state = bind_game_slot(self.bridge_state, resolved)
            save_state(self.state_path(), self.bridge_state)
            logger.info("Bound this Archipelago room to the active empty Word Factori save slot.")
        return active

    async def scan_once(self, ignore_selection_guard: bool = False) -> None:
        if not self.compatible_campaign():
            self._bridge_warning(CAMPAIGN_MISMATCH)
            return
        if not ignore_selection_guard and not self.selected_mod():
            self._bridge_warning("Automatic checks paused: the selected Word Factori mod is not the Archipelago mod. Use /wf_scan for an explicit one-time scan.")
            return
        active = self.ensure_game_slot_binding()
        if active is None:
            return
        local_checks = set(active.beaten_levels)
        if not ignore_selection_guard and not self.selected_mod():
            self._bridge_warning("Automatic check discarded because the selected mod changed during the save read.")
            return
        self.last_bridge_error = None
        await self.report_indices(local_checks)

    async def report_indices(self, indices: set[int]) -> None:
        if self.connected_identity is None:
            self._bridge_warning("Connect to an Archipelago slot before reporting Word Factori checks.")
            return
        if not self.compatible_campaign():
            self._bridge_warning(CAMPAIGN_MISMATCH)
            return
        if self.ensure_game_slot_binding() is None:
            return
        valid = {index for index in indices if 0 <= index < len(LOCATIONS)}
        server_indices = {
            location.index for location in LOCATIONS if location.code in self.checked_locations
        }
        result = reconcile(self.bridge_state, [], valid, server_indices)
        if result.new_checks:
            location_ids = {
                LOCATIONS[index].code for index in result.new_checks
            } - self.bridge_state.pending_checks
            if location_ids:
                self.bridge_state = queue_checks(self.bridge_state, location_ids)
                save_state(self.state_path(), self.bridge_state)
                await self.check_locations(location_ids)
        combined = server_indices | valid
        goal = int(self.slot_data.get("goal", 0))
        target = int(self.slot_data.get("campaign_count", 25))
        if goal_reached(goal, target, combined) and self.goal_identity != self.connected_identity:
            self.goal_identity = self.connected_identity
            await self._send_goal()

    async def _resend_pending_checks(self) -> None:
        if self.compatible_campaign() and self.ensure_game_slot_binding() is not None and self.bridge_state.pending_checks:
            await self.check_locations(self.bridge_state.pending_checks)

    async def _send_goal(self) -> None:
        if self.compatible_campaign() and self.ensure_game_slot_binding() is not None:
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])

    def resolve_location(self, identifier: str) -> int:
        value = identifier.strip()
        if value.isdigit():
            index = int(value) - 1
            if 0 <= index < len(LOCATIONS):
                return index
        folded = value.casefold()
        matches = [location.index for location in LOCATIONS if folded in {location.target.casefold(), location.name.casefold()}]
        if len(matches) == 1:
            return matches[0]
        raise ValueError("Use a unique 1-based level number, target word, or full location name.")

    def status_text(self) -> str:
        selected = "selected" if self.selected_mod() else "not selected or unverified"
        campaign = "compatible" if self.compatible_campaign() else "mismatched or missing"
        game_slot = "bound" if self.bridge_state.game_slot_id else "not bound"
        deliveries = max(0, len(self.bridge_state.applied) - 1)
        return f"AP mod: {selected}; campaign: {campaign}; game save: {game_slot}; received item deliveries: {deliveries}; bridge: {self.last_bridge_error or 'ready'}"

    def _bridge_warning(self, message: str) -> None:
        if message != self.last_bridge_error:
            logger.warning(message)
            self.last_bridge_error = message


async def game_watcher(ctx: WordFactoriContext) -> None:
    while not ctx.exit_event.is_set():
        if ctx.server and ctx.slot_data:
            try:
                await ctx.reconcile_received()
            except Exception as error:
                ctx._bridge_warning(f"Word Factori unlock update failed; retrying: {error}")
            try:
                await ctx.scan_once()
            except Exception as error:
                ctx._bridge_warning(f"Word Factori completion scan failed; retrying: {error}")
        await asyncio.sleep(2)


def launch_client(*passed_args: str) -> None:
    async def _main(args) -> None:
        ctx = WordFactoriContext(args.connect, args.password)
        ctx.auth = args.name
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        watcher = asyncio.create_task(game_watcher(ctx), name="Word Factori watcher")
        await ctx.exit_event.wait()
        watcher.cancel()
        await ctx.shutdown()

    parser = get_base_parser(description="Word Factori Archipelago Client")
    parser.add_argument("--name", default=None, help="Archipelago slot name")
    parser.add_argument("url", nargs="?", help="archipelago:// connection URL")
    args = parser.parse_args(passed_args)
    if args.url:
        try:
            args.connect, url_name, url_password = parse_connection_url(args.url)
        except ValueError as error:
            parser.error(str(error))
        args.name = url_name or args.name
        args.password = url_password or args.password
    asyncio.run(_main(args))


if __name__ == "__main__":
    Utils.init_logging("WordFactoriClient", exception_logger="Client")
    launch_client(*sys.argv[1:])
