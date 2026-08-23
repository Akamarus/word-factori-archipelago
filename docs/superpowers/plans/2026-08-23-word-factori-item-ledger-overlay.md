# Word Factori Item Ledger Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a testable item-only Word Factori-styled overlay that displays, deduplicates, persists, and safely reconstructs local Archipelago items sent and received.

**Architecture:** Keep `WordFactoriContext` authoritative for networking and progression. Normalize relevant Archipelago packets into a separate room-scoped dispatch ledger, reduce that ledger into renderer-neutral snapshots, and send snapshots over a private process pipe to a Kivy child that tracks the Word Factori window. Overlay failure is cosmetic and cannot block the existing client.

**Tech Stack:** Python 3.12+, Archipelago 0.6.7 `CommonClient`/`NetUtils`, standard-library `dataclasses`, `json`, `multiprocessing`, `ctypes`, bundled Kivy/KivyMD, PowerShell installer, `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-23-word-factori-ingame-client-design.md`

## Global Constraints

- Do not patch or redistribute `data.win` or any other proprietary game binary.
- Do not invent or write unverified Word Factori save fields.
- Do not require a separate runtime, background service, overlay installer, or network connection.
- Do not allow overlay failure to interrupt checks, item delivery, level regeneration, or victory reporting.
- Keep the player installation to one downloaded package and one installer action.
- Support Windows, Archipelago 0.6.7, and the verified Word Factori depot first.
- Load `FredokaOne.ttf` from the installed game; never add it to Git, the APWorld, or a release ZIP.
- Use `unittest`, atomic sidecar writes, immutable domain values, TDD, and one focused commit per task.
- Treat each test function shown below as a method on the named `unittest.TestCase` class in that test module, even when the surrounding class is omitted for brevity.
- This plan implements the item-only prototype. It does not remove the experimental label.

---

## File map

- Create `word_factori/dispatch.py`: immutable dispatch events, packet normalization, event keys.
- Create `word_factori/dispatch_store.py`: room-scoped ledger reconciliation, unread state, atomic persistence.
- Create `word_factori/overlay_model.py`: pure notification queue and ledger presentation reducer.
- Create `word_factori/overlay_preferences.py`: validated local visual preferences and atomic persistence.
- Create `word_factori/overlay_protocol.py`: strict JSON-safe parent/renderer message schema.
- Create `word_factori/overlay_supervisor.py`: spawn, publish, poll, restart-once, and shutdown behavior.
- Create `word_factori/window_tracker.py`: Win32 Word Factori window discovery and scaled bounds.
- Create `word_factori/overlay_renderer.py`: Kivy mailbox, blue left toast, ledger, hit testing, and child entry point.
- Modify `word_factori/client.py`: packet capture, checked-location scouting, ledger lifecycle, overlay lifecycle.
- Modify `word_factori/client_core.py`: installed-game font resolution without Steam path assumptions.
- Create `tests/test_dispatch.py`: event keys, normalization, reconciliation, persistence.
- Create `tests/test_overlay_model.py`: queue, unread, filtering, and protocol behavior.
- Create `tests/test_overlay_supervisor.py`: process isolation and restart policy with fakes.
- Create `tests/test_window_tracker.py`: Win32 adapter behavior with injected API fakes.
- Modify `tests/test_client_lifecycle.py`: `ReceivedItems`, `PrintJSON`, `LocationInfo`, reconnect, and room-switch flows.
- Create `tests/test_installer.py`: clean install, forced update, and uninstall using temporary roots.
- Create `Install Word Factori Archipelago.cmd`: friendly double-click installer wrapper.
- Modify `install.ps1`: exact-target uninstall and testable root overrides.
- Modify `tools/build_release.py`, `tools/verify_release.py`, `tests/test_publication.py`: package new launcher and reject proprietary font files.
- Modify `README.md`, `word_factori/docs/setup_en.md`: player-facing overlay and fallback instructions.

---

### Task 1: Immutable Dispatch Event Domain

**Files:**
- Create: `word_factori/dispatch.py`
- Create: `tests/test_dispatch.py`

**Interfaces:**
- Consumes: primitive packet fields already available from `ReceivedItems` and `PrintJSON`.
- Produces: `DispatchDirection`, `DispatchEvent`, `received_event(...)`, `sent_event(...)`, and stable event keys used by every later task.

- [ ] **Step 1: Write failing tests for receive, send, and self-event identity**

```python
from word_factori.dispatch import DispatchDirection, received_event, sent_event


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
```

- [ ] **Step 2: Run the focused tests and confirm the import fails**

Run: `python -m unittest tests.test_dispatch -v`

Expected: `ModuleNotFoundError: No module named 'word_factori.dispatch'`.

- [ ] **Step 3: Implement the immutable event types and constructors**

```python
from dataclasses import dataclass
from enum import Enum


class DispatchDirection(str, Enum):
    RECEIVED = "received"
    SENT = "sent"
    SELF = "self"


@dataclass(frozen=True)
class DispatchEvent:
    key: str
    direction: DispatchDirection
    item_id: int
    item_name: str
    other_slot: int
    other_player: str
    other_game: str
    location_id: int
    location_name: str
    receive_index: int | None
    observed_at: str | None
    historical: bool = False


def received_event(identity: str, receive_index: int, item_id: int, item_name: str,
                   source_slot: int, source_name: str, source_game: str,
                   location_id: int, location_name: str, observed_at: str | None,
                   self_item: bool = False) -> DispatchEvent:
    direction = DispatchDirection.SELF if self_item else DispatchDirection.RECEIVED
    return DispatchEvent(f"{identity}:receive:{receive_index}", direction,
                         item_id, item_name, source_slot, source_name, source_game,
                         location_id, location_name, receive_index, observed_at)


def sent_event(identity: str, location_id: int, item_id: int, item_name: str,
               recipient_slot: int, recipient_name: str, recipient_game: str,
               location_name: str, self_item: bool, observed_at: str | None) -> DispatchEvent:
    direction = DispatchDirection.SELF if self_item else DispatchDirection.SENT
    key = f"{identity}:send:{location_id}:{item_id}:{recipient_slot}"
    return DispatchEvent(key, direction, item_id, item_name, recipient_slot,
                         recipient_name, recipient_game, location_id,
                         location_name, None, observed_at)
```

- [ ] **Step 4: Add validation tests and reject empty identities, negative receive indices, and blank display names**

```python
def test_event_constructors_reject_invalid_identity_and_index(self):
    with self.assertRaisesRegex(ValueError, "identity"):
        received_event("", 0, 1, "Item", 2, "Alex", "Game", 3, "Location", None)
    with self.assertRaisesRegex(ValueError, "receive index"):
        received_event("room", -1, 1, "Item", 2, "Alex", "Game", 3, "Location", None)
```

Implement a private `_require_text()` helper and explicit integer range checks in both constructors.

- [ ] **Step 5: Run the focused tests**

Run: `python -m unittest tests.test_dispatch -v`

Expected: all dispatch-domain tests pass.

- [ ] **Step 6: Commit the event domain**

```powershell
git add word_factori/dispatch.py tests/test_dispatch.py
git commit -m "feat: add dispatch event domain"
```

---

### Task 2: Room-Scoped Ledger Reconciliation and Persistence

**Files:**
- Create: `word_factori/dispatch_store.py`
- Modify: `tests/test_dispatch.py`

**Interfaces:**
- Consumes: `DispatchEvent` and `DispatchDirection` from Task 1.
- Produces: `DispatchLedger`, `LedgerUpdate`, `reconcile_received(...)`, `record_event(...)`, `mark_all_read(...)`, `load_ledger(...)`, and `save_ledger(...)`.

- [ ] **Step 1: Write failing tests for silent first sync and noisy incremental sync**

```python
from word_factori.dispatch_store import DispatchLedger, reconcile_received


def test_first_authoritative_sync_is_historical_and_silent(self):
    events = (make_received(0), make_received(1))
    update = reconcile_received(DispatchLedger.empty("room"), events)
    self.assertEqual(update.historical_count, 2)
    self.assertEqual(update.notify, ())
    self.assertTrue(update.state.initialized)


def test_incremental_receive_notifies_once(self):
    first = reconcile_received(DispatchLedger.empty("room"), (make_received(0),)).state
    update = reconcile_received(first, (make_received(0), make_received(1)))
    self.assertEqual(tuple(event.receive_index for event in update.notify), (1,))
    again = reconcile_received(update.state, (make_received(0), make_received(1)))
    self.assertEqual(again.notify, ())
```

- [ ] **Step 2: Run the tests and confirm the store import fails**

Run: `python -m unittest tests.test_dispatch -v`

Expected: import failure for `word_factori.dispatch_store`.

- [ ] **Step 3: Implement ledger values and authoritative receive reconciliation**

```python
@dataclass(frozen=True)
class DispatchLedger:
    identity: str
    events: tuple[DispatchEvent, ...] = ()
    unread_keys: frozenset[str] = frozenset()
    initialized: bool = False
    received_high_water: int = -1

    @classmethod
    def empty(cls, identity: str) -> "DispatchLedger":
        return cls(identity=identity)


@dataclass(frozen=True)
class LedgerUpdate:
    state: DispatchLedger
    notify: tuple[DispatchEvent, ...]
    historical_count: int = 0


def reconcile_received(state: DispatchLedger, authoritative: Iterable[DispatchEvent]) -> LedgerUpdate:
    incoming = tuple(sorted(authoritative, key=lambda event: event.receive_index or 0))
    received_keys = {event.key for event in incoming}
    retained = tuple(event for event in state.events
                     if event.direction is DispatchDirection.SENT
                     or (event.receive_index is not None and event.key in received_keys))
    existing = {event.key for event in retained}
    additions = tuple(event for event in incoming if event.key not in existing)
    notify = tuple(event for event in additions
                   if state.initialized and event.receive_index > state.received_high_water)
    unread = state.unread_keys | frozenset(event.key for event in notify)
    merged = _trim_events(retained + additions, limit=200)
    high_water = max((event.receive_index for event in incoming), default=-1)
    return LedgerUpdate(DispatchLedger(state.identity, merged, unread, True, high_water), notify,
                        0 if state.initialized else len(additions))
```

- [ ] **Step 4: Write failing tests for sent dedupe, self-item collapse, trimming, mark-read, stale receive removal, and reconnect backfill below the persisted high-water mark**

```python
def test_record_event_deduplicates_and_caps_history(self):
    state = DispatchLedger.empty("room")
    for index in range(205):
        state = record_event(state, make_sent(index), notify=True).state
    self.assertEqual(len(state.events), 200)
    duplicate = record_event(state, state.events[-1], notify=True)
    self.assertEqual(duplicate.notify, ())


def test_mark_all_read_clears_only_unread_keys(self):
    state = record_event(DispatchLedger.empty("room"), make_sent(1), notify=True).state
    self.assertEqual(mark_all_read(state).unread_keys, frozenset())
```

- [ ] **Step 5: Implement record, trim, and mark-read behavior**

```python
def record_event(state: DispatchLedger, event: DispatchEvent, *, notify: bool) -> LedgerUpdate:
    if event.key in {existing.key for existing in state.events}:
        return LedgerUpdate(state, ())
    events = _trim_events(state.events + (event,), 200)
    unread = state.unread_keys | ({event.key} if notify else set())
    return LedgerUpdate(replace(state, events=events, unread_keys=frozenset(unread)),
                        (event,) if notify else ())


def mark_all_read(state: DispatchLedger) -> DispatchLedger:
    return replace(state, unread_keys=frozenset())
```

- [ ] **Step 6: Write failing atomic persistence and malformed-file tests**

```python
def test_ledger_round_trip_and_corruption_recovery(self):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "ledger.json"
        state = record_event(DispatchLedger.empty("room"), make_sent(1), notify=True).state
        save_ledger(path, state)
        self.assertEqual(load_ledger(path, "room"), state)
        path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ledger"):
            load_ledger(path, "room")
```

- [ ] **Step 7: Implement version-1 JSON serialization and atomic replacement**

Use the same `mkstemp`, `fsync`, and `os.replace` pattern as `bridge.save_state`. Serialize enum values as strings, preserve `observed_at=None` and `received_high_water`, validate identity equality, and reject unknown versions.

```python
LEDGER_VERSION = 1

def ledger_path(root: Path, safe_identity: str) -> Path:
    return root / "dispatch" / f"{safe_identity}.json"
```

- [ ] **Step 8: Run focused and existing bridge tests**

Run: `python -m unittest tests.test_dispatch tests.test_core -v`

Expected: all tests pass.

- [ ] **Step 9: Commit the ledger store**

```powershell
git add word_factori/dispatch_store.py tests/test_dispatch.py
git commit -m "feat: persist room-scoped dispatch ledger"
```

---

### Task 3: Client Packet Normalization and Checked-Location Reconstruction

**Files:**
- Modify: `word_factori/client.py`
- Modify: `tests/test_client_lifecycle.py`

**Interfaces:**
- Consumes: Tasks 1-2 constructors and ledger operations.
- Produces: `WordFactoriContext.reconcile_dispatches()`, `record_item_send(args)`, `request_checked_location_info()`, and `on_package("LocationInfo", ...)` integration.

- [ ] **Step 1: Extend the CommonClient test doubles and write a failing received-item lifecycle test**

Add `slot_info`, `location_names`, `send_msgs`, and a local `make_network_item(...)` helper that returns a `types.SimpleNamespace` with `item`, `location`, `player`, and `flags` attributes. Assert that first connection builds history silently and a later receive adds one notification candidate.

```python
async def test_dispatch_received_items_are_idempotent_across_reconnect(self):
    self.ctx.items_received = [make_network_item(item=7001, location=9001, player=2, flags=1)]
    self.ctx.on_package("ReceivedItems", {"index": 0, "items": self.ctx.items_received})
    await asyncio.sleep(0)
    self.assertEqual(len(self.ctx.dispatch_ledger.events), 1)
    self.ctx.on_package("ReceivedItems", {"index": 0, "items": self.ctx.items_received})
    await asyncio.sleep(0)
    self.assertEqual(len(self.ctx.dispatch_ledger.events), 1)
```

- [ ] **Step 2: Run the lifecycle test and verify missing dispatch state**

Run: `python -m unittest tests.test_client_lifecycle.ClientLifecycleTests.test_dispatch_received_items_are_idempotent_across_reconnect -v`

Expected: failure because `dispatch_ledger` and dispatch reconciliation do not exist.

- [ ] **Step 3: Add dispatch state initialization and authoritative receive conversion**

```python
self.dispatch_ledger = DispatchLedger.empty("disconnected")
self.pending_overlay_events: tuple[DispatchEvent, ...] = ()

async def reconcile_dispatches(self) -> None:
    identity = self.connected_identity or self.current_identity()
    events = tuple(self.dispatch_received_event(index, item)
                   for index, item in enumerate(self.items_received))
    update = reconcile_received(self.dispatch_ledger, events)
    self.dispatch_ledger = update.state
    self.pending_overlay_events += update.notify
    save_ledger(self.dispatch_path(), self.dispatch_ledger)
```

Load the room ledger on `Connected`, then call `reconcile_dispatches()` after the existing bridge reconciliation for both `Connected` and `ReceivedItems`. Dispatch errors are logged and isolated; they must not prevent unlock rendering. Resolve source player/game through `self.slot_info[item.player]`, item name through `self.item_names.lookup_in_game(item.item)`, and location name through `self.location_names.lookup_in_slot(item.location, item.player)` with a numeric fallback. Pass `self_item=True` when the source slot is local, and skip the starting `Bender Access` pseudo-item before normalization.

- [ ] **Step 4: Write failing `ItemSend` relevance and self-item tests**

```python
def test_item_send_records_only_local_source_or_recipient(self):
    local_send = item_send_packet(source=1, receiving=2, location=LOCATIONS[0].code)
    unrelated = item_send_packet(source=3, receiving=2, location=123)
    self.ctx.on_print_json(local_send)
    self.ctx.on_print_json(unrelated)
    self.assertEqual(
        [event.direction for event in self.ctx.dispatch_ledger.events],
        [DispatchDirection.SENT],
    )
```

- [ ] **Step 5: Override `on_print_json` without breaking the standard UI**

```python
def on_print_json(self, args: dict) -> None:
    super().on_print_json(args)
    if args.get("type") != "ItemSend" or self.connected_identity is None:
        return
    item = args.get("item")
    receiving = args.get("receiving")
    if item is None or not isinstance(receiving, int):
        return
    if not self.slot_concerns_self(item.player) and not self.slot_concerns_self(receiving):
        return
    self.record_item_send(args)
```

For a self item, allow authoritative `ReceivedItems` to create the one displayed row and suppress the duplicate live sent row. Add tests for missing `slot_info`, item-name, and location-name lookups so numeric fallbacks remain renderable and never crash normalization.

- [ ] **Step 6: Write a failing missed-send reconstruction test**

```python
async def test_connected_scouts_only_checked_word_factori_locations(self):
    checked = {LOCATIONS[0].code, LOCATIONS[3].code}
    self.ctx.checked_locations = checked | {999999999}
    await self.ctx.request_checked_location_info()
    message = next(msg for msg in self.ctx.sent_messages if msg["cmd"] == "LocationScouts")
    self.assertEqual(set(message["locations"]), checked)
```

- [ ] **Step 7: Implement checked-location scouting and `LocationInfo` backfill**

```python
async def request_checked_location_info(self) -> None:
    local_ids = {location.code for location in LOCATIONS}
    locations = sorted(self.checked_locations & local_ids)
    if locations:
        await self.send_msgs([{"cmd": "LocationScouts", "locations": locations, "create_as_hint": 0}])
```

Handle `LocationInfo` by converting each returned checked location to a historical sent/self event and calling `record_event(..., notify=False)`. Never request `missing_locations`.

- [ ] **Step 8: Run lifecycle and dispatch tests**

Run: `python -m unittest tests.test_client_lifecycle tests.test_dispatch -v`

Expected: all tests pass.

- [ ] **Step 9: Commit client event integration**

```powershell
git add word_factori/client.py tests/test_client_lifecycle.py
git commit -m "feat: reconcile sent and received dispatches"
```

---

### Task 4: Pure Overlay Presentation Model and Protocol

**Files:**
- Create: `word_factori/overlay_model.py`
- Create: `word_factori/overlay_preferences.py`
- Create: `word_factori/overlay_protocol.py`
- Create: `tests/test_overlay_model.py`

**Interfaces:**
- Consumes: `DispatchEvent`, `DispatchLedger`.
- Produces: `OverlayFilter`, `OverlayState`, `OverlaySnapshot`, `OverlayPreferences`, `apply_action(...)`, `apply_events(...)`, validated preference load/save, `encode_parent_message(...)`, `decode_parent_message(...)`, and `decode_child_action(...)`.

- [ ] **Step 1: Write failing reducer tests for queue limits, filtering, unread state, and close behavior**

```python
def test_notification_queue_caps_visible_and_preserves_order(self):
    state = OverlayState.closed(max_visible=3)
    state = apply_events(state, tuple(make_event(i) for i in range(5)))
    self.assertEqual(
        [event.key for event in snapshot(state).visible_notifications],
        ["0", "1", "2"],
    )
    self.assertEqual([event.key for event in state.waiting_notifications], ["3", "4"])


def test_opening_ledger_marks_read_and_dismisses_toasts(self):
    state = apply_events(OverlayState.closed(), (make_event(1),))
    state = apply_action(state, OverlayAction("open"))
    self.assertTrue(state.is_open)
    self.assertEqual(state.unread_count, 0)
    self.assertEqual(snapshot(state).visible_notifications, ())
```

- [ ] **Step 2: Run the tests and confirm the model import fails**

Run: `python -m unittest tests.test_overlay_model -v`

Expected: import failure for `overlay_model`.

- [ ] **Step 3: Implement immutable presentation state and reducer actions**

```python
class OverlayFilter(str, Enum):
    ALL = "all"
    RECEIVED = "received"
    SENT = "sent"

@dataclass(frozen=True)
class OverlayAction:
    kind: str
    value: str | None = None

@dataclass(frozen=True)
class OverlayState:
    is_open: bool = False
    active_filter: OverlayFilter = OverlayFilter.ALL
    visible_notifications: tuple[DispatchEvent, ...] = ()
    waiting_notifications: tuple[DispatchEvent, ...] = ()
    unread_count: int = 0
    max_visible: int = 3
    connection_status: str = "disconnected"
    reload_required: bool = False
```

Support exactly `open`, `close`, `toggle`, `filter`, `expire`, `focus-lost`, `focus-returned`, `connection-status`, and `reload-required`; reject unknown actions with `ValueError`. Add assertions that disconnected and reload-required state survive filtering and appear in snapshots.

- [ ] **Step 4: Write failing protocol round-trip and malformed-message tests**

```python
def test_snapshot_message_round_trip_and_unknown_type_rejection(self):
    encoded = encode_parent_message(snapshot_message(make_snapshot()))
    self.assertEqual(decode_parent_message(encoded).kind, "snapshot")
    with self.assertRaisesRegex(ValueError, "message type"):
        decode_parent_message('{"type":"execute"}')
```

- [ ] **Step 5: Implement versioned JSON-safe protocol messages**

```python
PROTOCOL_VERSION = 1

@dataclass(frozen=True)
class ParentMessage:
    kind: str
    payload: Mapping[str, object]

def encode_parent_message(message: ParentMessage) -> str:
    return json.dumps({"version": PROTOCOL_VERSION, "type": message.kind,
                       "payload": dict(message.payload)}, separators=(",", ":"))
```

Allow parent message types `snapshot`, `settings`, and `shutdown`; allow child action kinds defined by the reducer. Limit decoded strings to 8 KiB and reject extra top-level fields.

- [ ] **Step 6: Write failing preference validation and persistence tests**

Cover defaults plus round trips for `enabled`, `interface_scale`, `left_offset`, `notification_duration`, `reduced_motion`, and `max_visible`. Reject non-finite numbers, clamp documented numeric ranges, recover to defaults from a malformed file, and prove atomic replacement leaves no temporary file behind.

```python
@dataclass(frozen=True)
class OverlayPreferences:
    enabled: bool = True
    interface_scale: float = 1.0
    left_offset: int = 0
    notification_duration: float = 6.0
    reduced_motion: bool = False
    max_visible: int = 3
```

Implement versioned JSON in `overlay_preferences.py` using the same atomic-write discipline as the ledger. Preferences are cosmetic and must never enter campaign logic or the Word Factori save.

- [ ] **Step 7: Run focused tests**

Run: `python -m unittest tests.test_overlay_model -v`

Expected: all tests pass.

- [ ] **Step 8: Commit model, preferences, and protocol**

```powershell
git add word_factori/overlay_model.py word_factori/overlay_preferences.py word_factori/overlay_protocol.py tests/test_overlay_model.py
git commit -m "feat: add overlay presentation model"
```

---

### Task 5: Isolated Overlay Supervisor

**Files:**
- Create: `word_factori/overlay_supervisor.py`
- Create: `tests/test_overlay_supervisor.py`

**Interfaces:**
- Consumes: encoded messages from Task 4 and a renderer entry point callable.
- Produces: `OverlaySupervisor.start()`, `publish(snapshot)`, `poll_actions()`, `health_check()`, and `stop()`.

- [ ] **Step 1: Write failing tests with fake process and pipe factories**

```python
def test_supervisor_restarts_once_then_disables(self):
    factory = FakeProcessFactory(exit_immediately=True)
    supervisor = OverlaySupervisor(factory=factory)
    supervisor.start(make_config())
    supervisor.health_check()
    self.assertEqual(factory.starts, 2)
    supervisor.health_check()
    self.assertTrue(supervisor.disabled)


def test_publish_failure_does_not_raise_into_client(self):
    supervisor = OverlaySupervisor(factory=BrokenPipeFactory())
    supervisor.start(make_config())
    self.assertFalse(supervisor.publish(make_snapshot()))
```

- [ ] **Step 2: Run the tests and confirm the supervisor import fails**

Run: `python -m unittest tests.test_overlay_supervisor -v`

Expected: import failure.

- [ ] **Step 3: Implement dependency-injected process ownership**

```python
class OverlaySupervisor:
    def __init__(self, *, process_context=None, target=None):
        self._context = process_context or multiprocessing.get_context("spawn")
        self._target = target
        self._restarts = 0
        self.disabled = False

    def start(self, config: OverlayConfig) -> bool: ...
    def publish(self, snapshot: OverlaySnapshot) -> bool: ...
    def poll_actions(self) -> tuple[OverlayAction, ...]: ...
    def health_check(self) -> None: ...
    def stop(self, timeout: float = 2.0) -> None: ...
```

Create one duplex `multiprocessing.Pipe`, close unused endpoints in each process, use only non-blocking `poll()`, catch `BrokenPipeError`, `EOFError`, and `OSError`, and permit exactly one restart per client session.

- [ ] **Step 4: Add frozen-runtime launch guard tests**

Assert the child target is a top-level importable function and that `multiprocessing.freeze_support()` is called from the launcher path before child creation. Do not pass `WordFactoriContext`, credentials, or live protocol objects to the child.

- [ ] **Step 5: Run the supervisor tests**

Run: `python -m unittest tests.test_overlay_supervisor -v`

Expected: all tests pass without starting Kivy.

- [ ] **Step 6: Commit the supervisor**

```powershell
git add word_factori/overlay_supervisor.py tests/test_overlay_supervisor.py
git commit -m "feat: isolate overlay renderer process"
```

---

### Task 6: Win32 Window Tracking and Kivy Renderer

**Files:**
- Create: `word_factori/window_tracker.py`
- Create: `word_factori/overlay_renderer.py`
- Create: `tests/test_window_tracker.py`
- Modify: `tests/test_overlay_model.py`

**Interfaces:**
- Consumes: Task 4 messages and Task 5 child connection.
- Produces: `WindowState`, `Win32WindowTracker.sample()`, `find_game_font(process_path)`, and top-level `overlay_process_main(connection, config)`.

- [ ] **Step 1: Write failing injected-Win32 tests**

```python
def test_tracker_returns_scaled_visible_game_bounds(self):
    api = FakeWin32(hwnd=100, pid=44, executable=r"C:\Games\Word Factori\word factori.exe",
                    rect=(100, 80, 2020, 1160), dpi=144, foreground=True)
    state = Win32WindowTracker(api=api).sample()
    self.assertEqual(state.bounds, (100, 80, 1920, 1080))
    self.assertEqual(state.scale, 1.5)
    self.assertTrue(state.visible and state.focused)


def test_tracker_ignores_wrong_executable_and_minimized_window(self):
    self.assertIsNone(Win32WindowTracker(api=FakeWin32(executable=r"C:\Game\other.exe")).sample())
    self.assertFalse(Win32WindowTracker(api=FakeWin32(minimized=True)).sample().visible)
```

- [ ] **Step 2: Run the tests and confirm the tracker import fails**

Run: `python -m unittest tests.test_window_tracker -v`

Expected: import failure.

- [ ] **Step 3: Implement the narrow Win32 adapter with `ctypes`**

```python
@dataclass(frozen=True)
class WindowState:
    hwnd: int
    process_path: Path
    bounds: tuple[int, int, int, int]
    scale: float
    visible: bool
    focused: bool

class Win32WindowTracker:
    def __init__(self, api: Win32API | None = None):
        self.api = api or CtypesWin32API()

    def sample(self) -> WindowState | None:
        ...
```

Use `EnumWindows`, `GetWindowThreadProcessId`, `OpenProcess`, `QueryFullProcessImageNameW`, `GetWindowRect`, `IsIconic`, `GetForegroundWindow`, and `GetDpiForWindow`. Close every process handle in `finally`. Match the executable basename case-insensitively to `word factori.exe`.

- [ ] **Step 4: Add failing font-resolution tests to `client_core`**

```python
def test_game_font_is_resolved_next_to_running_executable(self):
    with tempfile.TemporaryDirectory() as directory:
        exe = Path(directory) / "word factori.exe"
        font = exe.with_name("FredokaOne.ttf")
        exe.touch()
        font.touch()
        self.assertEqual(game_font_path(exe), font)
```

Implement `game_font_path(executable: Path) -> Path | None` to return the neighboring file only when it exists; add a missing-font assertion returning `None`. The renderer receives the discovered path in `OverlayConfig`.

- [ ] **Step 5: Add a renderer import-safety test**

```python
def test_renderer_module_does_not_import_kivy_at_module_import_time(self):
    source = Path("word_factori/overlay_renderer.py").read_text(encoding="utf-8")
    self.assertNotIn("from kivy", source.split("def overlay_process_main", 1)[0])
```

This keeps unit tests runnable outside the frozen Archipelago GUI runtime.

- [ ] **Step 6: Implement the child entry point and approved visual hierarchy**

```python
def overlay_process_main(connection, config: Mapping[str, object]) -> None:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.text import LabelBase
    from kivy.core.window import Window
    from kivy.uix.floatlayout import FloatLayout
    # Register installed FredokaOne.ttf when present, construct DispatchOverlayApp,
    # poll the pipe on Clock, and stop on the versioned shutdown message.
```

Implement focused widget classes `MailboxButton`, `DeliveryToast`, `DispatchRow`, and `DispatchLedger`. Use the approved tokens: red mailbox, blue left toast, purple ledger header, dark ledger body, six-second duration, three visible notifications, and direction icons plus labels.

- [ ] **Step 7: Implement overlay window positioning and hit testing**

On each 100 ms tracker sample, set Kivy window position and size to the Word Factori client bounds. Hide when `WindowState.visible` or `focused` is false. Apply `WS_EX_LAYERED | WS_EX_TOPMOST` and return `HTTRANSPARENT` outside mailbox/toast/open-ledger rectangles. Restore the original window procedure during shutdown.

- [ ] **Step 8: Run non-GUI tests and perform the explicit frozen-runtime smoke probe**

Run automated tests:

```powershell
python -m unittest tests.test_window_tracker tests.test_overlay_model -v
```

Then install the development APWorld, launch `Word Factori Client` through `ArchipelagoLauncher.exe`, start Word Factori windowed, and record these observations in `tests/live-overlay-smoke.md`:

- child process started;
- installed Fredoka One loaded;
- blue toast and mailbox rendered on the left;
- factory grid remained clickable outside overlay controls;
- moving, minimizing, and restoring the game moved/hid/restored the overlay;
- closing the child left the client connected.

If the frozen child cannot import Kivy or spawn, stop this plan and revise the approved process boundary before proceeding; do not add a runtime download or silently move networking into the renderer.

- [ ] **Step 9: Commit renderer and window tracking**

```powershell
git add word_factori/window_tracker.py word_factori/overlay_renderer.py word_factori/client_core.py tests/test_window_tracker.py tests/test_overlay_model.py tests/live-overlay-smoke.md
git commit -m "feat: render Word Factori dispatch overlay"
```

---

### Task 7: Client and Overlay Lifecycle Integration

**Files:**
- Modify: `word_factori/client.py`
- Modify: `tests/test_client_lifecycle.py`
- Modify: `word_factori/Components.py`

**Interfaces:**
- Consumes: `OverlaySupervisor`, ledger updates, presentation reducer, persisted `OverlayPreferences`, renderer entry point.
- Produces: automatic overlay startup, preference-backed renderer configuration, snapshot publication, child-action polling, status fallback, and clean shutdown.

- [ ] **Step 1: Write a failing lifecycle test proving overlay failure is cosmetic**

```python
async def test_overlay_publish_failure_does_not_block_item_reconcile(self):
    self.ctx.overlay = FailingOverlaySupervisor()
    self.ctx.items_received = [make_network_item(item=7001, location=9001, player=2, flags=1)]
    await self.ctx.reconcile_received()
    self.assertTrue(self.ctx.levels_path.exists())
    self.assertEqual(self.ctx.bridge_state.applied[0], "7001")
    self.assertIn("overlay", self.ctx.status_text().lower())
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `python -m unittest tests.test_client_lifecycle.ClientLifecycleTests.test_overlay_publish_failure_does_not_block_item_reconcile -v`

Expected: failure because the client has no overlay supervisor.

- [ ] **Step 3: Add supervisor ownership to `WordFactoriContext`**

```python
self.overlay = OverlaySupervisor(target=overlay_process_main)
self.overlay_state = OverlayState.closed()
self.overlay_preferences = load_preferences(self.overlay_preferences_path())
self.last_overlay_error: str | None = None

def publish_overlay(self) -> None:
    if not self.overlay.publish(snapshot(self.overlay_state, self.dispatch_ledger)):
        self.last_overlay_error = "overlay unavailable; using regular client"
```

Start after context initialization, not during import. If preferences disable the overlay, retain ledger collection without spawning the child. Pass only validated visual preferences to `OverlayConfig`. Process child actions in the existing two-second watcher plus a 100 ms async overlay-action task so `F8`, open, close, and filters feel responsive without affecting save scans.

- [ ] **Step 4: Write and pass tests for room switch, disconnect, preference loading, action polling, and clean shutdown**

Assert a room switch loads a distinct ledger, `Connected` publishes connection state, disconnect preserves history, mark-read persists, reload-required propagates from the bridge, disabled preferences prevent child startup without losing events, malformed preferences fall back to defaults, and `shutdown()` always calls `overlay.stop()` in `finally`.

- [ ] **Step 5: Add `/wf_overlay` fallback controls**

```python
def _cmd_wf_overlay(self, action: str = "status") -> None:
    """Show, hide, restart, or report the Word Factori overlay."""
```

Support exactly `status`, `show`, `hide`, and `restart`; reject other values with usage text. This remains available when click-through or display attachment fails.

- [ ] **Step 6: Run all automated tests**

Run: `python -m unittest discover -s tests -v`

Expected: all existing and overlay tests pass.

- [ ] **Step 7: Commit lifecycle integration**

```powershell
git add word_factori/client.py word_factori/Components.py tests/test_client_lifecycle.py
git commit -m "feat: attach dispatch overlay to client lifecycle"
```

---

### Task 8: One-Action Installer and Release Hygiene

**Files:**
- Create: `Install Word Factori Archipelago.cmd`
- Modify: `install.ps1`
- Create: `tests/test_installer.py`
- Modify: `tools/build_release.py`
- Modify: `tools/verify_release.py`
- Modify: `tests/test_publication.py`
- Modify: `README.md`
- Modify: `word_factori/docs/setup_en.md`

**Interfaces:**
- Consumes: complete item-ledger overlay.
- Produces: one-action install/update/uninstall and verified release contents.

- [ ] **Step 1: Write failing packaging tests**

```python
def test_release_includes_friendly_installer_and_excludes_game_font(self):
    build_release.write_world()
    build_release.write_release()
    with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as archive:
        names = set(archive.namelist())
    self.assertIn("Install Word Factori Archipelago.cmd", names)
    self.assertFalse(any(name.casefold().endswith("fredokaone.ttf") for name in names))
```

- [ ] **Step 2: Run the publication test and confirm the launcher is absent**

Run: `python -m unittest tests.test_publication -v`

Expected: failure because the `.cmd` file is not packaged.

- [ ] **Step 3: Add the double-click wrapper**

```batch
@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 (
  echo.
  echo Installation did not complete. Review the message above.
  pause
  exit /b 1
)
echo.
echo Word Factori Archipelago is ready.
pause
```

- [ ] **Step 4: Write failing installer integration tests using temporary environment roots**

Use `subprocess.run(["powershell.exe", "-NoProfile", "-File", install, "-Force"], env={...})` with temporary `ProgramData` and `LOCALAPPDATA`. Assert clean install, refusal without `-Force`, update with `-Force`, `-Uninstall` exact-target removal, and preservation of neighboring files.

- [ ] **Step 5: Add safe uninstall to `install.ps1`**

```powershell
[CmdletBinding()]
param([switch]$Force, [switch]$Uninstall)

if ($Uninstall) {
    Assert-DirectChild $worldTarget $worldTargetDirectory
    Assert-DirectChild $modTarget $modTargetDirectory
    if (Test-Path -LiteralPath $worldTarget) { Remove-Item -LiteralPath $worldTarget -Force }
    if (Test-Path -LiteralPath $modTarget) { Remove-Item -LiteralPath $modTarget -Recurse -Force }
    Write-Host "Removed only the Word Factori Archipelago integration."
    exit 0
}
```

Move `Assert-DirectChild` above the uninstall branch. Never delete the parent mod, Archipelago, ProgramData, or LocalAppData directories.

- [ ] **Step 6: Package the wrapper and harden proprietary-data checks**

Add the `.cmd` file to `write_release()` and make `verify_release.py` reject `FredokaOne.ttf`, `Letters.ttf`, `data.win`, `recipes.data`, `save.json`, and any `.superpowers` entry by basename or path component.

- [ ] **Step 7: Update player documentation**

Document the four-step install/launch flow, blue left toast, mailbox/F8 controls, item-only scope, regular-client fallback, supported display modes, and `/wf_overlay` recovery command. State that full chat/client operation remains an official-release gate.

- [ ] **Step 8: Run installer, publication, full suite, build, and verification**

```powershell
python -m unittest discover -s tests -v
python tools\build_release.py
python tools\verify_release.py
```

Expected: all tests pass and release verification reports data exclusions and archive parity.

- [ ] **Step 9: Commit installer and documentation**

```powershell
git add "Install Word Factori Archipelago.cmd" install.ps1 tests/test_installer.py tests/test_publication.py tools/build_release.py tools/verify_release.py README.md word_factori/docs/setup_en.md
git commit -m "feat: package item ledger overlay"
```

---

### Task 9: Live Acceptance and Prototype Release Gate

**Files:**
- Create: `docs/testing/item-ledger-overlay-acceptance.md`
- Modify: `README.md` only if observed limitations require correction.

**Interfaces:**
- Consumes: complete item-only subsystem.
- Produces: reproducible acceptance evidence and a go/no-go decision for the prototype release.

- [ ] **Step 1: Create the acceptance matrix before live testing**

Include rows for 1080p, 1440p, ultrawide, 100/125/150% scaling, windowed, borderless, minimize/restore, focus loss, resize, monitor movement, long names, child crash, and fallback.

- [ ] **Step 2: Generate a two-player test room and record its disposable seed identity**

Use a fresh Word Factori empty slot. Do not reuse the six-completion development slot. Record only test-room identifiers; do not commit server passwords or saves.

- [ ] **Step 3: Exercise authoritative receive scenarios**

Verify first sync is silent, a new received item produces one blue left toast, replay produces none, self item creates one row, reconnect preserves unread/history, and a new room shows a distinct ledger.

- [ ] **Step 4: Exercise sent and missed-send scenarios**

Complete a Word Factori location while connected and confirm one sent row. Close the client, complete another valid location only if the established save-safety flow permits it, reconnect, and verify checked-location scouting reconstructs the missed send as `earlier` without a popup.

- [ ] **Step 5: Exercise window and renderer failure scenarios**

Validate every matrix row. Terminate only the owned overlay child, confirm one automatic restart, terminate it again, and confirm the regular client remains connected with checks and items functional.

- [ ] **Step 6: Run final automated verification from a clean worktree**

```powershell
python -m unittest discover -s tests -v
python tools\build_release.py
python tools\verify_release.py
git diff --check
git status --short
```

Expected: all tests and verification pass; only the acceptance document or explicitly justified README correction is uncommitted.

- [ ] **Step 7: Complete the acceptance document with observed results and hashes**

Record PASS/FAIL per row, Word Factori build, Archipelago version, release ZIP hash, APWorld hash, and any explicitly supported fallback. No row may remain blank.

- [ ] **Step 8: Commit acceptance evidence**

```powershell
git add docs/testing/item-ledger-overlay-acceptance.md README.md
git commit -m "test: verify item ledger overlay acceptance"
```

- [ ] **Step 9: Stop at the prototype boundary**

Label the build experimental and proceed to `docs/superpowers/plans/2026-08-23-word-factori-full-ingame-client.md`. Do not call the integration official based on item-only acceptance.
