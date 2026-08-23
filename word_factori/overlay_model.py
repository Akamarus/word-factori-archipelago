"""Pure, renderer-neutral presentation state for the dispatch overlay."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable, Iterator, Mapping

from word_factori.dispatch import DispatchDirection, DispatchEvent
from word_factori.dispatch_store import DispatchLedger


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
    is_focused: bool = True

    @classmethod
    def closed(cls, *, max_visible: int = 3) -> "OverlayState":
        if isinstance(max_visible, bool) or not isinstance(max_visible, int) or not 1 <= max_visible <= 10:
            raise ValueError("max_visible must be an integer from 1 to 10")
        return cls(max_visible=max_visible)


class JsonObject(dict[str, object]):
    """An immutable JSON object with convenient read-only attribute access."""

    def __init__(self, values: Mapping[str, object]) -> None:
        dict.__init__(self, {key: _freeze_json(value) for key, value in values.items()})

    def __getattr__(self, name: str) -> object:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def _immutable(self, *_: object, **__: object) -> None:
        raise TypeError("snapshot values are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


class JsonArray(list[object]):
    """An immutable JSON array used inside snapshot and message values."""

    def __init__(self, values: Iterable[object]) -> None:
        list.__init__(self, (_freeze_json(value) for value in values))

    def _immutable(self, *_: object, **__: object) -> None:
        raise TypeError("snapshot values are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable


def _freeze_json(value: object) -> object:
    if isinstance(value, dict):
        return JsonObject(value)
    if isinstance(value, (list, tuple)):
        return JsonArray(value)
    return value


@dataclass(frozen=True)
class OverlaySnapshot:
    ledger_rows: tuple[JsonObject, ...]
    visible_notifications: tuple[JsonObject, ...]
    waiting_notifications: tuple[JsonObject, ...]
    unread_count: int
    is_open: bool
    is_focused: bool
    active_filter: str
    connection_status: str
    reload_required: bool
    enabled: bool
    interface_scale: float
    left_offset: int
    notification_duration: float
    reduced_motion: bool
    max_visible: int


def _event_row(event: DispatchEvent) -> JsonObject:
    return JsonObject({
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
    })


def event_payload(event: DispatchEvent) -> JsonObject:
    """Expose the sole event-to-primitive conversion used by the overlay."""
    return _event_row(event)


def _filtered(events: Iterable[DispatchEvent], active_filter: OverlayFilter) -> Iterator[DispatchEvent]:
    for event in events:
        if active_filter is OverlayFilter.ALL:
            yield event
        elif active_filter is OverlayFilter.RECEIVED:
            if event.direction in (DispatchDirection.RECEIVED, DispatchDirection.SELF):
                yield event
        elif event.direction is DispatchDirection.SENT:
            yield event


def _filled(visible: tuple[DispatchEvent, ...], waiting: tuple[DispatchEvent, ...], limit: int) -> tuple[tuple[DispatchEvent, ...], tuple[DispatchEvent, ...]]:
    room = limit - len(visible)
    if room <= 0 or not waiting:
        return visible, waiting
    return visible + waiting[:room], waiting[room:]


def apply_events(state: OverlayState, events: Iterable[DispatchEvent]) -> OverlayState:
    incoming = tuple(events)
    if not all(isinstance(event, DispatchEvent) for event in incoming):
        raise ValueError("overlay events must be DispatchEvent values")
    known = {event.key for event in state.visible_notifications + state.waiting_notifications}
    additions = tuple(event for event in incoming if event.key not in known)
    visible, waiting = _filled(state.visible_notifications, state.waiting_notifications + additions, state.max_visible)
    return replace(state, visible_notifications=visible, waiting_notifications=waiting,
                   unread_count=state.unread_count + len(additions))


def apply_action(state: OverlayState, action: OverlayAction) -> OverlayState:
    if not isinstance(action, OverlayAction):
        raise ValueError("overlay action must be an OverlayAction")
    if action.kind == "open":
        return replace(state, is_open=True, visible_notifications=(), waiting_notifications=(), unread_count=0)
    if action.kind == "close":
        return replace(state, is_open=False)
    if action.kind == "toggle":
        return apply_action(state, OverlayAction("close" if state.is_open else "open"))
    if action.kind == "filter":
        try:
            active_filter = OverlayFilter(action.value)
        except (TypeError, ValueError) as error:
            raise ValueError("overlay filter is invalid") from error
        return replace(state, active_filter=active_filter)
    if action.kind == "expire":
        visible = state.visible_notifications
        if action.value is None:
            visible = visible[1:]
        else:
            visible = tuple(event for event in visible if event.key != action.value)
        visible, waiting = _filled(visible, state.waiting_notifications, state.max_visible)
        return replace(state, visible_notifications=visible, waiting_notifications=waiting)
    if action.kind == "focus-lost":
        return replace(state, is_focused=False)
    if action.kind == "focus-returned":
        return replace(state, is_focused=True)
    if action.kind == "connection-status":
        if not isinstance(action.value, str) or not action.value:
            raise ValueError("connection status must be non-blank text")
        return replace(state, connection_status=action.value)
    if action.kind == "reload-required":
        if action.value not in ("true", "false"):
            raise ValueError("reload-required must be true or false")
        return replace(state, reload_required=action.value == "true")
    raise ValueError("overlay action is unknown")


def snapshot(state: OverlayState, ledger: DispatchLedger | Iterable[DispatchEvent] | None = None,
             preferences: object | None = None) -> OverlaySnapshot:
    """Return a renderer-ready snapshot containing only JSON-compatible values."""
    if not isinstance(state, OverlayState):
        raise ValueError("overlay state is invalid")
    if ledger is None:
        events: Iterable[DispatchEvent] = ()
        unread_count = state.unread_count
    elif isinstance(ledger, DispatchLedger):
        events = ledger.events
        unread_count = len(ledger.unread_keys)
    else:
        events = ledger
        unread_count = state.unread_count
    if preferences is None:
        preference_values = (True, 1.0, 0, 6.0, False, 3)
    else:
        try:
            preference_values = (
                preferences.enabled, preferences.interface_scale, preferences.left_offset,
                preferences.notification_duration, preferences.reduced_motion, preferences.max_visible,
            )
        except AttributeError as error:
            raise ValueError("overlay preferences are invalid") from error
    visible = () if not state.is_focused else tuple(_event_row(event) for event in state.visible_notifications)
    return OverlaySnapshot(
        ledger_rows=tuple(_event_row(event) for event in _filtered(events, state.active_filter)),
        visible_notifications=visible,
        waiting_notifications=tuple(_event_row(event) for event in state.waiting_notifications),
        unread_count=unread_count,
        is_open=state.is_open,
        is_focused=state.is_focused,
        active_filter=state.active_filter.value,
        connection_status=state.connection_status,
        reload_required=state.reload_required,
        enabled=preference_values[0],
        interface_scale=preference_values[1],
        left_offset=preference_values[2],
        notification_duration=preference_values[3],
        reduced_motion=preference_values[4],
        max_visible=preference_values[5],
    )
