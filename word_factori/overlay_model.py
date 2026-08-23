"""Pure, renderer-neutral presentation state for the dispatch overlay."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable, Iterator, Mapping

from .dispatch import DispatchDirection, DispatchEvent
from .dispatch_store import DispatchLedger


CONNECTION_STATUSES = frozenset((
    "disconnected", "connecting", "connected", "reconnecting", "authenticating", "error",
))
_NO_VALUE_ACTIONS = frozenset((
    "open", "open-items", "open-chat", "open-connect", "request-password",
    "close", "toggle", "focus-lost", "focus-returned", "submit-started", "submit-failed",
))
_ACTION_KINDS = _NO_VALUE_ACTIONS | frozenset(("filter", "expire", "connection-status", "reload-required"))
_MAX_ACTION_VALUE_LENGTH = 8192


class OverlayFilter(str, Enum):
    ALL = "all"
    RECEIVED = "received"
    SENT = "sent"


class OverlayView(str, Enum):
    ITEMS = "items"
    CHAT = "chat"
    CONNECT = "connect"
    PASSWORD = "password"


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass(frozen=True)
class OverlayAction:
    kind: str
    value: str | None = None
    generation: int | None = None


@dataclass(frozen=True)
class OverlayState:
    is_open: bool = False
    active_filter: OverlayFilter = OverlayFilter.ALL
    active_view: OverlayView = OverlayView.ITEMS
    input_focused: bool = False
    visible_notifications: tuple[DispatchEvent, ...] = ()
    waiting_notifications: tuple[DispatchEvent, ...] = ()
    unread_count: int = 0
    max_visible: int = 3
    connection_status: str = "disconnected"
    reload_required: bool = False
    is_focused: bool = True
    accepted_notification_keys: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.is_open, bool):
            raise ValueError("is_open must be boolean")
        if not isinstance(self.active_filter, OverlayFilter):
            raise ValueError("active_filter must be an OverlayFilter")
        if not isinstance(self.active_view, OverlayView):
            raise ValueError("active_view must be an OverlayView")
        if not isinstance(self.input_focused, bool):
            raise ValueError("input_focused must be boolean")
        for field, events in (
            ("visible_notifications", self.visible_notifications),
            ("waiting_notifications", self.waiting_notifications),
        ):
            if not isinstance(events, tuple) or not all(isinstance(event, DispatchEvent) for event in events):
                raise ValueError(f"{field} must be a tuple of DispatchEvent values")
        if isinstance(self.max_visible, bool) or not isinstance(self.max_visible, int) or not 1 <= self.max_visible <= 10:
            raise ValueError("max_visible must be an integer from 1 to 10")
        if len(self.visible_notifications) > self.max_visible:
            raise ValueError("visible_notifications exceeds max_visible")
        if isinstance(self.unread_count, bool) or not isinstance(self.unread_count, int) or self.unread_count < 0:
            raise ValueError("unread_count must be a non-negative integer")
        if not isinstance(self.connection_status, str) or self.connection_status not in CONNECTION_STATUSES:
            raise ValueError("connection_status is invalid")
        if not isinstance(self.reload_required, bool) or not isinstance(self.is_focused, bool):
            raise ValueError("overlay state flags must be boolean")
        if not isinstance(self.accepted_notification_keys, frozenset):
            raise ValueError("accepted_notification_keys must be a frozenset")
        if not all(isinstance(key, str) and key.strip() and len(key) <= _MAX_ACTION_VALUE_LENGTH
                   for key in self.accepted_notification_keys):
            raise ValueError("accepted_notification_keys must contain bounded non-blank text")
        notification_keys = tuple(event.key for event in self.visible_notifications + self.waiting_notifications)
        if len(notification_keys) != len(set(notification_keys)):
            raise ValueError("notification queues contain duplicate keys")
        if not set(notification_keys) <= self.accepted_notification_keys:
            raise ValueError("accepted_notification_keys must include queued notifications")
        if self.is_open and (notification_keys or self.unread_count):
            raise ValueError("open overlay state cannot have queued or unread presentation")
        input_views = (OverlayView.CHAT, OverlayView.CONNECT, OverlayView.PASSWORD)
        if self.input_focused and (
            not self.is_open or not self.is_focused or self.active_view not in input_views
        ):
            raise ValueError("keyboard focus requires an open focused input view")

    @classmethod
    def closed(cls, *, max_visible: int = 3) -> "OverlayState":
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
    generation: int
    ledger_rows: tuple[JsonObject, ...]
    visible_notifications: tuple[JsonObject, ...]
    waiting_notifications: tuple[JsonObject, ...]
    unread_count: int
    is_open: bool
    is_focused: bool
    active_filter: str
    active_view: str
    accepts_keyboard: bool
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
    accepted = state.accepted_notification_keys
    additions: list[DispatchEvent] = []
    for event in incoming:
        if event.key not in accepted:
            additions.append(event)
            accepted = accepted | frozenset((event.key,))
    if state.is_open:
        return replace(state, accepted_notification_keys=accepted)
    visible, waiting = _filled(state.visible_notifications, state.waiting_notifications + tuple(additions), state.max_visible)
    return replace(state, visible_notifications=visible, waiting_notifications=waiting,
                   unread_count=state.unread_count + len(additions), accepted_notification_keys=accepted)


def validate_action(action: OverlayAction) -> OverlayAction:
    """Reject action values that cannot be safely applied by the reducer."""
    if not isinstance(action, OverlayAction) or not isinstance(action.kind, str) or action.kind not in _ACTION_KINDS:
        raise ValueError("overlay action is unknown")
    if action.generation is not None and (
        type(action.generation) is not int or action.generation < 0
    ):
        raise ValueError("overlay action generation is invalid")
    if action.kind in _NO_VALUE_ACTIONS:
        if action.value is not None:
            raise ValueError("overlay action does not accept a value")
    elif action.kind == "filter":
        if action.value not in tuple(item.value for item in OverlayFilter):
            raise ValueError("overlay filter is invalid")
    elif action.kind == "expire":
        if action.value is not None and (
            not isinstance(action.value, str) or not action.value.strip() or len(action.value) > _MAX_ACTION_VALUE_LENGTH
        ):
            raise ValueError("overlay expire key is invalid")
    elif action.kind == "connection-status":
        if not isinstance(action.value, str) or action.value not in CONNECTION_STATUSES:
            raise ValueError("connection status is invalid")
    elif action.value not in ("true", "false"):
        raise ValueError("reload-required must be true or false")
    return action


def apply_action(state: OverlayState, action: OverlayAction) -> OverlayState:
    action = validate_action(action)
    if action.kind in ("open", "open-items", "open-chat", "open-connect", "request-password"):
        view = {
            "open": OverlayView.ITEMS,
            "open-items": OverlayView.ITEMS,
            "open-chat": OverlayView.CHAT,
            "open-connect": OverlayView.CONNECT,
            "request-password": OverlayView.PASSWORD,
        }[action.kind]
        accepts_keyboard = state.is_focused and view in (
            OverlayView.CHAT, OverlayView.CONNECT, OverlayView.PASSWORD,
        )
        return replace(
            state,
            is_open=True,
            active_view=view,
            input_focused=accepts_keyboard,
            visible_notifications=(),
            waiting_notifications=(),
            unread_count=0,
        )
    if action.kind == "close":
        return replace(state, is_open=False, input_focused=False)
    if action.kind == "toggle":
        return apply_action(state, OverlayAction("close" if state.is_open else "open"))
    if action.kind == "filter":
        return replace(state, active_filter=OverlayFilter(action.value))
    if action.kind == "expire":
        visible = state.visible_notifications
        if action.value is None:
            visible = visible[1:]
        else:
            visible = tuple(event for event in visible if event.key != action.value)
        visible, waiting = _filled(visible, state.waiting_notifications, state.max_visible)
        return replace(state, visible_notifications=visible, waiting_notifications=waiting)
    if action.kind == "focus-lost":
        return replace(state, is_focused=False, input_focused=False)
    if action.kind == "focus-returned":
        return replace(state, is_focused=True)
    if action.kind == "connection-status":
        return replace(state, connection_status=action.value)
    if action.kind == "reload-required":
        return replace(state, reload_required=action.value == "true")
    if action.kind == "submit-started":
        return replace(state, input_focused=False)
    if action.kind == "submit-failed":
        accepts_keyboard = state.is_open and state.is_focused and state.active_view in (
            OverlayView.CHAT, OverlayView.CONNECT, OverlayView.PASSWORD,
        )
        return replace(state, input_focused=accepts_keyboard)
    raise AssertionError("validated action kind was not handled")


def snapshot(state: OverlayState, ledger: DispatchLedger | Iterable[DispatchEvent] | None = None,
             preferences: object | None = None, *, generation: int = 0) -> OverlaySnapshot:
    """Return a renderer-ready snapshot containing only JSON-compatible values."""
    if not isinstance(state, OverlayState):
        raise ValueError("overlay state is invalid")
    if type(generation) is not int or generation < 0:
        raise ValueError("overlay generation must be a non-negative integer")
    from .overlay_preferences import OverlayPreferences

    if ledger is None:
        events: Iterable[DispatchEvent] = ()
    elif isinstance(ledger, DispatchLedger):
        events = ledger.events
    else:
        events = ledger
    if preferences is None:
        preferences = OverlayPreferences(max_visible=state.max_visible)
    if not isinstance(preferences, OverlayPreferences):
        raise ValueError("overlay preferences are invalid")
    if preferences.max_visible != state.max_visible:
        raise ValueError("overlay state and preferences max_visible disagree")
    visible = () if not state.is_focused else tuple(_event_row(event) for event in state.visible_notifications)
    return OverlaySnapshot(
        generation=generation,
        ledger_rows=tuple(_event_row(event) for event in _filtered(events, state.active_filter)),
        visible_notifications=visible,
        waiting_notifications=tuple(_event_row(event) for event in state.waiting_notifications),
        unread_count=state.unread_count,
        is_open=state.is_open,
        is_focused=state.is_focused,
        active_filter=state.active_filter.value,
        active_view=state.active_view.value,
        accepts_keyboard=state.input_focused,
        connection_status=state.connection_status,
        reload_required=state.reload_required,
        enabled=preferences.enabled,
        interface_scale=preferences.interface_scale,
        left_offset=preferences.left_offset,
        notification_duration=preferences.notification_duration,
        reduced_motion=preferences.reduced_motion,
        max_visible=preferences.max_visible,
    )
