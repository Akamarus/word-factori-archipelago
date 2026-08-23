from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from word_factori.dispatch import DispatchDirection, DispatchEvent


LEDGER_LIMIT = 200
LEDGER_VERSION = 1


@dataclass(frozen=True)
class DispatchLedger:
    identity: str
    events: tuple[DispatchEvent, ...] = ()
    unread_keys: frozenset[str] = frozenset()
    initialized: bool = False
    received_high_water: int = -1

    @classmethod
    def empty(cls, identity: str) -> "DispatchLedger":
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("ledger identity must be non-blank text")
        return cls(identity=identity)


@dataclass(frozen=True)
class LedgerUpdate:
    state: DispatchLedger
    notify: tuple[DispatchEvent, ...]
    historical_count: int = 0


def _trim_events(events: tuple[DispatchEvent, ...], limit: int = LEDGER_LIMIT) -> tuple[DispatchEvent, ...]:
    return events[-limit:]


def _validate_event_identity(identity: str, event: DispatchEvent) -> None:
    if not event.key.startswith(f"{identity}:"):
        raise ValueError("ledger event identity does not match room identity")


def _deduplicate_authoritative(events: Iterable[DispatchEvent]) -> tuple[DispatchEvent, ...]:
    by_key: dict[str, DispatchEvent] = {}
    by_index: dict[int, DispatchEvent] = {}
    for event in events:
        for existing in (by_key.get(event.key), by_index.get(event.receive_index)):
            if existing is not None:
                if existing != event:
                    raise ValueError("conflicting authoritative receive rows")
                break
        else:
            by_key[event.key] = event
            by_index[event.receive_index] = event
    return tuple(by_key.values())


def reconcile_received(state: DispatchLedger, authoritative: Iterable[DispatchEvent]) -> LedgerUpdate:
    incoming = tuple(sorted(authoritative, key=lambda event: event.receive_index or 0))
    for event in incoming:
        _validate_event_identity(state.identity, event)
        if event.direction not in (DispatchDirection.RECEIVED, DispatchDirection.SELF) or event.receive_index is None:
            raise ValueError("authoritative ledger events must be received events")
    incoming = _deduplicate_authoritative(incoming)
    received_keys = {event.key for event in incoming}
    retained = tuple(
        event for event in state.events
        if event.direction is DispatchDirection.SENT
        or (event.receive_index is not None and event.key in received_keys)
    )
    existing = {event.key for event in retained}
    additions = tuple(event for event in incoming if event.key not in existing)
    notify = tuple(
        event for event in additions
        if state.initialized and event.receive_index is not None
        and event.receive_index > state.received_high_water
    )
    merged = _trim_events(retained + additions)
    unread = (state.unread_keys | frozenset(event.key for event in notify)) & frozenset(event.key for event in merged)
    highest_incoming = max((event.receive_index for event in incoming if event.receive_index is not None), default=-1)
    high_water = max(state.received_high_water, highest_incoming)
    return LedgerUpdate(
        DispatchLedger(state.identity, merged, unread, True, high_water),
        notify,
        0 if state.initialized else len(additions),
    )


def record_event(state: DispatchLedger, event: DispatchEvent, *, notify: bool) -> LedgerUpdate:
    _validate_event_identity(state.identity, event)
    if event.key in {existing.key for existing in state.events}:
        return LedgerUpdate(state, ())
    events = _trim_events(state.events + (event,))
    unread = (state.unread_keys | ({event.key} if notify else set())) & {existing.key for existing in events}
    return LedgerUpdate(
        replace(state, events=events, unread_keys=frozenset(unread)),
        (event,) if notify else (),
    )


def mark_all_read(state: DispatchLedger) -> DispatchLedger:
    return replace(state, unread_keys=frozenset())


def ledger_path(root: Path, safe_identity: str) -> Path:
    return root / "dispatch" / f"{safe_identity}.json"


def _event_payload(event: DispatchEvent) -> dict[str, Any]:
    return {
        "key": event.key,
        "direction": event.direction.value,
        "item_id": event.item_id,
        "item_name": event.item_name,
        "other_slot": event.other_slot,
        "other_player": event.other_player,
        "other_game": event.other_game,
        "location_id": event.location_id,
        "location_name": event.location_name,
        "receive_index": event.receive_index,
        "observed_at": event.observed_at,
        "historical": event.historical,
    }


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"ledger event {field} must be non-blank text")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"ledger event {field} must be a non-negative integer")
    return value


def _event_from_payload(payload: Any) -> DispatchEvent:
    if not isinstance(payload, dict):
        raise ValueError("ledger event must be an object")
    try:
        direction = DispatchDirection(payload["direction"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("ledger event direction is invalid") from error
    receive_index = payload.get("receive_index")
    if receive_index is not None:
        receive_index = _nonnegative_int(receive_index, "receive_index")
    observed_at = payload.get("observed_at")
    if observed_at is not None and not isinstance(observed_at, str):
        raise ValueError("ledger event observed_at must be text or null")
    historical = payload.get("historical", False)
    if not isinstance(historical, bool):
        raise ValueError("ledger event historical must be boolean")
    try:
        return DispatchEvent(
            _required_text(payload["key"], "key"), direction,
            _nonnegative_int(payload["item_id"], "item_id"),
            _required_text(payload["item_name"], "item_name"),
            _nonnegative_int(payload["other_slot"], "other_slot"),
            _required_text(payload["other_player"], "other_player"),
            _required_text(payload["other_game"], "other_game"),
            _nonnegative_int(payload["location_id"], "location_id"),
            _required_text(payload["location_name"], "location_name"),
            receive_index, observed_at, historical,
        )
    except KeyError as error:
        raise ValueError("ledger event is missing a field") from error


def _validate_persisted_event(identity: str, event: DispatchEvent) -> None:
    _validate_event_identity(identity, event)
    sent_key = f"{identity}:send:{event.location_id}:{event.item_id}:{event.other_slot}"
    if event.direction is DispatchDirection.SENT:
        if event.receive_index is not None or event.key != sent_key:
            raise ValueError("ledger sent event is inconsistent")
    elif event.direction is DispatchDirection.RECEIVED:
        if event.receive_index is None or event.key != f"{identity}:receive:{event.receive_index}":
            raise ValueError("ledger received event is inconsistent")
    elif event.direction is DispatchDirection.SELF:
        if event.receive_index is None:
            if event.key != sent_key:
                raise ValueError("ledger self event is inconsistent")
        elif event.key != f"{identity}:receive:{event.receive_index}":
            raise ValueError("ledger self event is inconsistent")


def load_ledger(path: Path, identity: str) -> DispatchLedger:
    if not path.is_file():
        return DispatchLedger.empty(identity)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("ledger file is malformed") from error
    if not isinstance(payload, dict):
        raise ValueError("ledger file must contain an object")
    if type(payload.get("version")) is not int or payload["version"] != LEDGER_VERSION:
        raise ValueError("ledger version is not supported")
    stored_identity = payload.get("identity")
    if stored_identity != identity:
        raise ValueError("ledger identity does not match room identity")
    events_payload = payload.get("events")
    unread_payload = payload.get("unread_keys")
    initialized = payload.get("initialized")
    high_water = payload.get("received_high_water")
    if not isinstance(events_payload, list) or len(events_payload) > LEDGER_LIMIT:
        raise ValueError("ledger events must be an array of at most 200 entries")
    if not isinstance(unread_payload, list) or not all(isinstance(key, str) for key in unread_payload):
        raise ValueError("ledger unread_keys must be an array of text")
    if not isinstance(initialized, bool):
        raise ValueError("ledger initialized must be boolean")
    if isinstance(high_water, bool) or not isinstance(high_water, int) or high_water < -1:
        raise ValueError("ledger received_high_water must be an integer")
    events = tuple(_event_from_payload(event) for event in events_payload)
    if len({event.key for event in events}) != len(events):
        raise ValueError("ledger events contain duplicate keys")
    for event in events:
        _validate_persisted_event(identity, event)
    event_keys = frozenset(event.key for event in events)
    unread_keys = frozenset(unread_payload)
    if not unread_keys <= event_keys:
        raise ValueError("ledger unread_keys must reference retained events")
    highest_received = max((event.receive_index for event in events if event.receive_index is not None), default=-1)
    if high_water < highest_received:
        raise ValueError("ledger received_high_water cannot precede retained events")
    return DispatchLedger(identity, events, unread_keys, initialized, high_water)


def save_ledger(path: Path, state: DispatchLedger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({
                "version": LEDGER_VERSION,
                "identity": state.identity,
                "events": [_event_payload(event) for event in state.events],
                "unread_keys": sorted(state.unread_keys),
                "initialized": state.initialized,
                "received_high_water": state.received_high_water,
            }, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
