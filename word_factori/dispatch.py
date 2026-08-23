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


def _require_text(value: str | None, field: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-blank text")
    return value


def _require_nonnegative_int(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _validate_received(identity: str, receive_index: int, item_id: int, item_name: str,
                       source_slot: int, source_name: str, source_game: str,
                       location_id: int, location_name: str,
                       observed_at: str | None) -> None:
    _require_text(identity, "identity")
    _require_nonnegative_int(receive_index, "receive index")
    _require_nonnegative_int(item_id, "item_id")
    _require_text(item_name, "item_name")
    _require_nonnegative_int(source_slot, "source slot")
    _require_text(source_name, "source_name")
    _require_text(source_game, "source_game")
    _require_nonnegative_int(location_id, "location_id")
    _require_text(location_name, "location_name")
    _require_text(observed_at, "observed_at", optional=True)


def received_event(identity: str, receive_index: int, item_id: int, item_name: str,
                   source_slot: int, source_name: str, source_game: str,
                   location_id: int, location_name: str, observed_at: str | None,
                   self_item: bool = False) -> DispatchEvent:
    _validate_received(identity, receive_index, item_id, item_name, source_slot,
                       source_name, source_game, location_id, location_name,
                       observed_at)
    direction = DispatchDirection.SELF if self_item else DispatchDirection.RECEIVED
    return DispatchEvent(f"{identity}:receive:{receive_index}", direction,
                         item_id, item_name, source_slot, source_name, source_game,
                         location_id, location_name, receive_index, observed_at)


def sent_event(identity: str, location_id: int, item_id: int, item_name: str,
               recipient_slot: int, recipient_name: str, recipient_game: str,
               location_name: str, self_item: bool,
               observed_at: str | None) -> DispatchEvent:
    _require_text(identity, "identity")
    _require_nonnegative_int(location_id, "location_id")
    _require_nonnegative_int(item_id, "item_id")
    _require_text(item_name, "item_name")
    _require_nonnegative_int(recipient_slot, "recipient slot")
    _require_text(recipient_name, "recipient_name")
    _require_text(recipient_game, "recipient_game")
    _require_text(location_name, "location_name")
    _require_text(observed_at, "observed_at", optional=True)
    direction = DispatchDirection.SELF if self_item else DispatchDirection.SENT
    key = f"{identity}:send:{location_id}:{item_id}:{recipient_slot}"
    return DispatchEvent(key, direction, item_id, item_name, recipient_slot,
                         recipient_name, recipient_game, location_id,
                         location_name, None, observed_at)
