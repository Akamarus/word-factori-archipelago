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
    utc_observed_at,
)
from .data import GAME, ITEM_NAME_TO_ID, LOCATIONS
from .dispatch import DispatchDirection, DispatchEvent, received_event, sent_event
from .dispatch_store import (
    DispatchLedger, ledger_path, load_ledger, mark_all_read, reconcile_received, record_event,
    save_ledger,
)
from .mod import render_levels, write_levels
from .overlay_model import OverlayAction, OverlayState, apply_action, apply_events, snapshot
from .overlay_preferences import load_preferences
from .overlay_supervisor import OverlayConfig, OverlaySupervisor
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

    def _cmd_wf_overlay(self, action: str = "status") -> None:
        """Show, hide, restart, or report the Word Factori overlay."""
        action = action.strip().casefold()
        if action == "status":
            self.output(self.ctx.overlay_status_text())
        elif action in {"show", "hide", "restart"}:
            asyncio.create_task(self.ctx.overlay_control(action))
        else:
            self.output("Usage: /wf_overlay [status|show|hide|restart]")


class WordFactoriContext(CommonContext):
    command_processor = WordFactoriCommandProcessor
    game = GAME
    items_handling = 0b111
    want_slot_data = True

    def __init__(
        self, server_address: str | None, password: str | None, *, overlay: object | None = None,
    ):
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
        self.overlay = overlay if overlay is not None else OverlaySupervisor()
        self.overlay_preferences = load_preferences(self.overlay_preferences_path())
        self.overlay_state = OverlayState.closed(max_visible=self.overlay_preferences.max_visible)
        self.last_overlay_transport_error: str | None = None
        self.last_overlay_persistence_error: str | None = None
        self.overlay_action_task: asyncio.Task | None = None
        self._overlay_identity: str | None = None
        self._connection_generation = 0
        self._presentation_generation = 0
        self._overlay_session_generation = int(
            getattr(self.overlay, "session_generation", 0),
        )

    @property
    def last_overlay_error(self) -> str | None:
        return self.last_overlay_persistence_error or self.last_overlay_transport_error

    def _advance_connection_generation(self) -> int:
        self._connection_generation += 1
        self._presentation_generation += 1
        return self._connection_generation

    def _connection_epoch_matches(self, identity: str | None, generation: int) -> bool:
        return (
            identity is not None
            and self.connected_identity == identity
            and self._connection_generation == generation
        )

    def _sync_overlay_session(self) -> None:
        current = int(getattr(self.overlay, "session_generation", 0))
        if current != self._overlay_session_generation:
            self._overlay_session_generation = current
            self._presentation_generation += 1

    async def server_auth(self, password_requested: bool = False) -> None:
        self._set_overlay_connection_status("authenticating")
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    async def connection_closed(self) -> None:
        self._advance_connection_generation()
        try:
            await super().connection_closed()
        finally:
            self._set_overlay_connection_status("disconnected")

    async def shutdown(self) -> None:
        action_task, self.overlay_action_task = self.overlay_action_task, None
        if action_task is not None:
            action_task.cancel()
            try:
                await action_task
            except asyncio.CancelledError:
                pass
            except Exception as error:
                self._overlay_warning(f"overlay action loop stopped: {error}")
        try:
            await super().shutdown()
        finally:
            try:
                self.overlay.stop(timeout=2.0)
            except Exception as error:
                self._overlay_warning(f"overlay shutdown failed: {error}")

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "RoomInfo":
            seed_name = args.get("seed_name")
            self.room_seed_name = str(seed_name) if seed_name is not None else None
        elif cmd == "Connected":
            connection_generation = self._advance_connection_generation()
            self.slot_data = dict(args.get("slot_data") or {})
            self.connected_identity = self.current_identity()
            try:
                baseline_ledger = load_ledger(
                    self.dispatch_path(self.connected_identity), self.connected_identity,
                )
            except (OSError, ValueError, TypeError) as error:
                logger.warning("Ignoring invalid dispatch ledger; room history will rebuild it: %s", error)
                baseline_ledger = DispatchLedger.empty(self.connected_identity)
            self.dispatch_ledger = baseline_ledger
            self.pending_overlay_events = ()
            self.overlay_state = OverlayState(
                unread_count=len(baseline_ledger.unread_keys),
                max_visible=self.overlay_preferences.max_visible,
                connection_status="connected",
                accepted_notification_keys=frozenset(
                    event.key for event in baseline_ledger.events
                ),
            )
            self._overlay_identity = self.connected_identity
            self.publish_overlay(self.connected_identity, connection_generation)
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
                frozenset(self.checked_locations), connection_generation,
            ))
            asyncio.create_task(self._resend_pending_checks())
            if self.goal_identity == self.connected_identity:
                asyncio.create_task(self._send_goal())
        elif cmd == "ReceivedItems":
            asyncio.create_task(self._received_items_reconcile(
                self.connected_identity, self._snapshot_dispatch_items(self.items_received),
                self._connection_generation,
            ))
        elif cmd == "LocationInfo" and self.connected_identity is not None:
            asyncio.create_task(self._backfill_location_info_safely(
                self.connected_identity,
                self._snapshot_dispatch_items(args.get("locations") or ()),
                frozenset(self.checked_locations),
                self._connection_generation,
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

    def overlay_preferences_path(self) -> Path:
        return self.state_root / "overlay_preferences.json"

    def overlay_config(self) -> OverlayConfig:
        preferences = self.overlay_preferences
        return OverlayConfig(
            enabled=preferences.enabled,
            interface_scale=preferences.interface_scale,
            left_offset=preferences.left_offset,
            notification_duration=preferences.notification_duration,
            reduced_motion=preferences.reduced_motion,
            max_visible=preferences.max_visible,
            # The renderer resolves the installed font from the tracked Word Factori process.
            # sys.executable belongs to the Archipelago launcher and is intentionally ignored.
            font_path=None,
        )

    def start_overlay(self) -> None:
        """Start optional cosmetic work only after the async client runtime exists."""
        if not self.overlay_preferences.enabled:
            return
        try:
            started = bool(self.overlay.start(self.overlay_config()))
        except Exception as error:
            started = False
            self._overlay_warning(f"overlay startup failed: {error}")
        if not started:
            self._overlay_warning("overlay unavailable; using regular client")
            return
        self._sync_overlay_session()
        self.last_overlay_transport_error = None
        self._ensure_overlay_action_task()
        self.publish_overlay()

    def _ensure_overlay_action_task(self) -> None:
        if self.overlay_action_task is None or self.overlay_action_task.done():
            self.overlay_action_task = asyncio.create_task(
                self._overlay_action_loop(), name="Word Factori overlay actions",
            )

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
            utc_observed_at(), self_item=self.slot_concerns_self(item.player),
        )

    def _dispatch_room_matches(
        self, identity: str, connection_generation: int | None = None,
    ) -> bool:
        return (
            self.connected_identity == identity
            and self.dispatch_ledger.identity == identity
            and (
                connection_generation is None
                or self._connection_generation == connection_generation
            )
        )

    def _room_overlay_candidate(
        self, identity: str, ledger: DispatchLedger, notifications: tuple[DispatchEvent, ...],
    ) -> OverlayState:
        """Create a fresh room presentation without replaying retained history."""
        notification_keys = frozenset(event.key for event in notifications)
        state = OverlayState(
            unread_count=len(ledger.unread_keys - notification_keys),
            max_visible=self.overlay_preferences.max_visible,
            connection_status="connected",
            reload_required=self.overlay_state.reload_required,
            accepted_notification_keys=frozenset(
                event.key for event in ledger.events if event.key not in notification_keys
            ),
        )
        return apply_events(state, notifications)

    def _event_overlay_candidates(
        self, identity: str, ledger: DispatchLedger,
        notifications: tuple[DispatchEvent, ...],
    ) -> tuple[DispatchLedger, OverlayState]:
        state = self.overlay_state
        if self._overlay_identity not in (None, identity):
            return ledger, state
        if notifications:
            state = apply_events(state, notifications)
        if state.is_open and ledger.unread_keys:
            ledger = mark_all_read(ledger)
        return ledger, state

    def _commit_dispatch_candidates(
        self, identity: str, connection_generation: int,
        ledger: DispatchLedger, state: OverlayState,
    ) -> bool:
        if not self._connection_epoch_matches(identity, connection_generation):
            return False
        try:
            save_ledger(self.dispatch_path(identity), ledger)
        except Exception as error:
            self._overlay_persistence_warning(
                f"dispatch persistence failed: {error}; presentation state retained",
            )
            logger.error(
                "Dispatch history could not be persisted; Word Factori unlocks remain active: %s",
                error,
            )
            return False
        if not self._connection_epoch_matches(identity, connection_generation):
            return False
        self.dispatch_ledger = ledger
        self.overlay_state = state
        self.pending_overlay_events = ()
        self._overlay_identity = identity
        self.last_overlay_persistence_error = None
        self.publish_overlay(identity, connection_generation)
        return True

    async def reconcile_dispatches(
        self, identity: str | None = None, items=None,
        connection_generation: int | None = None,
    ) -> None:
        identity = identity or self.connected_identity or self.current_identity()
        connection_generation = (
            self._connection_generation
            if connection_generation is None else connection_generation
        )
        items = tuple(self.items_received) if items is None else tuple(items)
        if not self._connection_epoch_matches(identity, connection_generation):
            return
        async with self._dispatch_lock:
            if not self._dispatch_room_matches(identity, connection_generation):
                return
            events = tuple(
                event for index, item in enumerate(items)
                if (event := self.dispatch_received_event(index, item, identity)) is not None
            )
            update = reconcile_received(self.dispatch_ledger, events)
            ledger, state = self._event_overlay_candidates(
                identity, update.state, update.notify,
            )
            self._commit_dispatch_candidates(
                identity, connection_generation, ledger, state,
            )

    async def _connected_reconcile(
        self, identity: str, items, checked_locations,
        connection_generation: int | None = None,
    ) -> None:
        connection_generation = (
            self._connection_generation
            if connection_generation is None else connection_generation
        )
        if not self._connection_epoch_matches(identity, connection_generation):
            return
        await self.reconcile_received()
        if not self._connection_epoch_matches(identity, connection_generation):
            return
        try:
            async with self._dispatch_lock:
                if not self._connection_epoch_matches(identity, connection_generation):
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
                if (
                    not self._connection_epoch_matches(identity, connection_generation)
                    or update.state.identity != identity
                ):
                    return
                state = self._room_overlay_candidate(identity, update.state, update.notify)
                ledger = mark_all_read(update.state) if state.is_open else update.state
                self._commit_dispatch_candidates(
                    identity, connection_generation, ledger, state,
                )
        except Exception:
            logger.exception("Dispatch history reconciliation failed; Word Factori unlocks remain active.")
        try:
            if not self._dispatch_room_matches(identity, connection_generation):
                return
            await self.request_checked_location_info(
                identity, checked_locations, connection_generation,
            )
            if not self._connection_epoch_matches(identity, connection_generation):
                return
        except Exception:
            logger.exception("Checked-location dispatch history could not be requested.")

    async def _received_items_reconcile(
        self, identity: str | None, items, connection_generation: int,
    ) -> None:
        if not self._connection_epoch_matches(identity, connection_generation):
            return
        await self.reconcile_received()
        if not self._connection_epoch_matches(identity, connection_generation):
            return
        try:
            await self.reconcile_dispatches(identity, items, connection_generation)
        except Exception:
            logger.exception("Dispatch history reconciliation failed; Word Factori unlocks remain active.")

    async def request_checked_location_info(
        self, identity: str | None = None, checked_locations=None,
        connection_generation: int | None = None,
    ) -> None:
        identity = identity or self.connected_identity or self.current_identity()
        connection_generation = (
            self._connection_generation
            if connection_generation is None else connection_generation
        )
        checked_locations = (
            frozenset(self.checked_locations)
            if checked_locations is None else frozenset(checked_locations)
        )
        local_ids = {location.code for location in LOCATIONS}
        locations = sorted(checked_locations & local_ids)
        if locations and self._dispatch_room_matches(identity, connection_generation):
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
            self.slot_concerns_self(item.player), None if historical else utc_observed_at(),
        )
        return replace(event, historical=historical)

    async def _backfill_location_info_safely(
        self, identity: str, items, checked_locations,
        connection_generation: int | None = None,
    ) -> None:
        connection_generation = (
            self._connection_generation
            if connection_generation is None else connection_generation
        )
        try:
            local_ids = {location.code for location in LOCATIONS}
            checked = checked_locations & local_ids
            async with self._dispatch_lock:
                if not self._dispatch_room_matches(identity, connection_generation):
                    return
                ledger = self.dispatch_ledger
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
                        for existing in ledger.events
                    ):
                        continue
                    update = record_event(ledger, event, notify=False)
                    changed = changed or update.state is not ledger
                    ledger = update.state
                if changed:
                    self._commit_dispatch_candidates(
                        identity, connection_generation, ledger, self.overlay_state,
                    )
        except Exception:
            logger.exception("Checked-location dispatch history could not be recorded.")

    async def _record_dispatch_event_safely(
        self, identity: str, event: DispatchEvent, *, notify: bool,
        connection_generation: int | None = None,
    ) -> None:
        connection_generation = (
            self._connection_generation
            if connection_generation is None else connection_generation
        )
        try:
            async with self._dispatch_lock:
                if not self._dispatch_room_matches(identity, connection_generation):
                    return
                update = record_event(self.dispatch_ledger, event, notify=notify)
                ledger, state = self._event_overlay_candidates(
                    identity, update.state, update.notify,
                )
                self._commit_dispatch_candidates(
                    identity, connection_generation, ledger, state,
                )
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
            self._lookup_location_name(item.location, item.player), False, utc_observed_at(),
        )
        asyncio.create_task(self._record_dispatch_event_safely(
            identity, event, notify=True,
            connection_generation=self._connection_generation,
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
            self.overlay_state = apply_action(
                self.overlay_state, OverlayAction("reload-required", "true"),
            )
            self.publish_overlay(self.connected_identity)

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
        return f"AP mod: {selected}; campaign: {campaign}; game save: {game_slot}; received item deliveries: {deliveries}; bridge: {self.last_bridge_error or 'ready'}; overlay: {self.last_overlay_error or 'ready'}"

    def overlay_status_text(self) -> str:
        if not self.overlay_preferences.enabled:
            availability = "disabled by preference; regular client active"
        else:
            availability = self.last_overlay_error or "ready"
        panel = "open" if self.overlay_state.is_open else "closed"
        return (
            f"Word Factori overlay: {availability}; panel: {panel}; "
            f"connection: {self.overlay_state.connection_status}"
        )

    def _overlay_warning(self, message: str) -> None:
        if message != self.last_overlay_transport_error:
            logger.warning("Word Factori overlay: %s", message)
            self.last_overlay_transport_error = message

    def _overlay_persistence_warning(self, message: str) -> None:
        if message != self.last_overlay_persistence_error:
            logger.warning("Word Factori overlay state: %s", message)
            self.last_overlay_persistence_error = message

    def publish_overlay(
        self, expected_identity: str | None = None,
        expected_connection_generation: int | None = None,
    ) -> bool:
        """Publish cosmetic presentation without exposing renderer failure to bridge work."""
        if not self.overlay_preferences.enabled:
            return False
        if (
            expected_connection_generation is not None
            and self._connection_generation != expected_connection_generation
        ):
            return False
        if expected_identity is not None and (
            self.connected_identity != expected_identity
            or self.dispatch_ledger.identity != expected_identity
            or self._overlay_identity not in (None, expected_identity)
        ):
            return False
        try:
            published = self.overlay.publish(snapshot(
                self.overlay_state, self.dispatch_ledger, self.overlay_preferences,
                generation=self._presentation_generation,
            ))
        except Exception as error:
            published = False
            self._overlay_warning(f"publish failed: {error}; using regular client")
        if published:
            self.last_overlay_transport_error = None
        elif self.last_overlay_transport_error is None:
            self._overlay_warning("unavailable; using regular client")
        return published

    def _set_overlay_connection_status(self, status: str) -> None:
        try:
            self.overlay_state = apply_action(
                self.overlay_state, OverlayAction("connection-status", status),
            )
            self.publish_overlay(self.connected_identity)
        except Exception as error:
            self._overlay_warning(f"status update failed: {error}; using regular client")

    async def _apply_overlay_action(
        self, action: OverlayAction, *, expected_identity: str | None = None,
        expected_connection_generation: int | None = None,
    ) -> bool:
        if expected_connection_generation is not None and (
            not self._connection_epoch_matches(
                expected_identity, expected_connection_generation,
            )
        ):
            return False
        if action.kind == "open" and self.connected_identity is not None:
            async with self._dispatch_lock:
                identity = self.connected_identity
                connection_generation = self._connection_generation
                if expected_connection_generation is not None:
                    identity = expected_identity
                    connection_generation = expected_connection_generation
                if not self._dispatch_room_matches(identity, connection_generation):
                    return False
                try:
                    previous = self.overlay_state
                    updated = apply_action(previous, action)
                except Exception as error:
                    self._overlay_warning(f"action rejected: {error}; using regular client")
                    return False
                candidate_ledger = self.dispatch_ledger
                if not previous.is_open and updated.is_open and candidate_ledger.unread_keys:
                    candidate_ledger = mark_all_read(candidate_ledger)
                    try:
                        save_ledger(self.dispatch_path(identity), candidate_ledger)
                    except Exception as error:
                        self._overlay_persistence_warning(
                            f"mark-read persistence failed: {error}; presentation state retained",
                        )
                        self.publish_overlay(identity, connection_generation)
                        return False
                    if not self._connection_epoch_matches(identity, connection_generation):
                        return False
                    self.dispatch_ledger = candidate_ledger
                    self.last_overlay_persistence_error = None
                self.overlay_state = updated
                self.publish_overlay(identity, connection_generation)
                return True
        try:
            updated = apply_action(self.overlay_state, action)
        except Exception as error:
            self._overlay_warning(f"action rejected: {error}; using regular client")
            return False
        self.overlay_state = updated
        self.publish_overlay(self.connected_identity)
        return True

    async def _apply_child_overlay_action(self, action: OverlayAction) -> None:
        if action.generation != self._presentation_generation:
            return
        identity = self.connected_identity
        connection_generation = self._connection_generation
        await self._apply_overlay_action(
            action, expected_identity=identity,
            expected_connection_generation=connection_generation,
        )

    async def _apply_local_overlay_action(self, action: OverlayAction) -> bool:
        identity = self.connected_identity
        if identity is None:
            return await self._apply_overlay_action(action)
        return await self._apply_overlay_action(
            action, expected_identity=identity,
            expected_connection_generation=self._connection_generation,
        )

    async def process_overlay_actions_once(self) -> None:
        """Drain one nonblocking child-action batch; useful for deterministic tests."""
        try:
            actions = tuple(self.overlay.poll_actions())
        except Exception as error:
            self._overlay_warning(f"action poll failed: {error}; using regular client")
            return
        for action in actions:
            await self._apply_child_overlay_action(action)

    async def _overlay_action_loop(self) -> None:
        while not self.exit_event.is_set():
            await self.process_overlay_actions_once()
            try:
                await asyncio.wait_for(self.exit_event.wait(), timeout=0.1)
            except asyncio.TimeoutError:
                pass

    def check_overlay_health(self) -> None:
        if not self.overlay_preferences.enabled:
            return
        try:
            self.overlay.health_check()
            self._sync_overlay_session()
            if bool(getattr(self.overlay, "disabled", False)):
                self._overlay_warning("renderer stopped after restart attempt; using regular client")
                return
            self.publish_overlay(self.connected_identity)
        except Exception as error:
            self._overlay_warning(f"health check failed: {error}; using regular client")

    async def overlay_control(self, action: str) -> None:
        if action == "show":
            if not self.overlay_preferences.enabled:
                self._overlay_warning("disabled by preference; regular client active")
                return
            if bool(getattr(self.overlay, "disabled", False)):
                self._overlay_warning("renderer disabled for this session; use restart")
                return
            if not self.publish_overlay(self.connected_identity):
                try:
                    started = bool(self.overlay.start(self.overlay_config()))
                except Exception as error:
                    started = False
                    self._overlay_warning(f"overlay startup failed: {error}")
                if started:
                    self._sync_overlay_session()
                    self._ensure_overlay_action_task()
                if not started or not self.publish_overlay(self.connected_identity):
                    self._overlay_warning("unavailable; using regular client")
                    return
            await self._apply_local_overlay_action(OverlayAction("open"))
            return
        if action == "hide":
            await self._apply_local_overlay_action(OverlayAction("close"))
            return
        if action != "restart":
            raise ValueError("unknown overlay control")
        if not self.overlay_preferences.enabled:
            self._overlay_warning("disabled by preference; regular client active")
            return
        self._presentation_generation += 1
        try:
            restarted = bool(self.overlay.restart(self.overlay_config()))
        except Exception as error:
            restarted = False
            self._overlay_warning(f"restart failed: {error}; using regular client")
        if restarted:
            self._overlay_session_generation = int(
                getattr(self.overlay, "session_generation", self._overlay_session_generation),
            )
            self.last_overlay_transport_error = None
            self._ensure_overlay_action_task()
            self.publish_overlay(self.connected_identity)
        elif self.last_overlay_transport_error is None:
            self._overlay_warning("restart failed; using regular client")

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
        ctx.check_overlay_health()
        await asyncio.sleep(2)


def launch_client(*passed_args: str) -> None:
    async def _main(args) -> None:
        ctx = WordFactoriContext(args.connect, args.password)
        ctx.auth = args.name
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        ctx.start_overlay()
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
