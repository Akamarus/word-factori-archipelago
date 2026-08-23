"""Strict, versioned JSON messages for the isolated overlay process."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Mapping

from word_factori.overlay_model import OverlayAction, OverlaySnapshot, validate_action


PROTOCOL_VERSION = 1
_PARENT_TYPES = frozenset(("snapshot", "settings", "shutdown"))
_SNAPSHOT_FIELDS = frozenset(OverlaySnapshot.__dataclass_fields__)
_SETTINGS_FIELDS = frozenset((
    "enabled", "interface_scale", "left_offset", "notification_duration", "reduced_motion", "max_visible",
))
_EVENT_FIELDS = frozenset((
    "key", "direction", "item_id", "item_name", "other_slot", "other_player", "other_game",
    "location_id", "location_name", "receive_index", "observed_at", "historical",
))


@dataclass(frozen=True)
class ParentMessage:
    kind: str
    payload: Mapping[str, object]


def _bad_constant(_: str) -> None:
    raise ValueError("non-finite JSON numbers are not permitted")


def _decode_json(encoded: str) -> object:
    if not isinstance(encoded, str):
        raise ValueError("protocol message must be JSON text")
    try:
        value = json.loads(encoded, parse_constant=_bad_constant)
    except (TypeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("protocol message is malformed") from error
    _validate_json(value)
    return value


def _validate_json(value: object) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if len(value) > 8192:
            raise ValueError("protocol string exceeds 8192 code points")
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("protocol numbers must be finite")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("protocol object keys must be strings")
            _validate_json(key)
            _validate_json(item)
        return
    raise ValueError("protocol value is not JSON-safe")


def _json_value(value: object) -> object:
    """Copy a value into canonical JSON containers while validating it."""
    if value is None or isinstance(value, bool) or isinstance(value, str) or isinstance(value, int):
        _validate_json(value)
        return value
    if isinstance(value, float):
        _validate_json(value)
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("protocol object keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    raise ValueError("protocol value is not JSON-safe")


def _require_exact_keys(payload: object, fields: frozenset[str], name: str) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError(f"{name} payload has invalid fields")
    return payload


def _require_bool(value: object, field: str) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")


def _require_int(value: object, field: str, *, minimum: int | None = None) -> None:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError(f"{field} must be an integer")


def _require_number(value: object, field: str, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    if not minimum <= value <= maximum:
        raise ValueError(f"{field} is outside its allowed range")


def _require_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be text")


def _validate_event_row(value: object) -> None:
    row = _require_exact_keys(value, _EVENT_FIELDS, "event")
    for field in ("key", "item_name", "other_player", "other_game", "location_name"):
        _require_text(row[field], field)
    if row["direction"] not in ("received", "sent", "self"):
        raise ValueError("event direction is invalid")
    for field in ("item_id", "other_slot", "location_id"):
        _require_int(row[field], field, minimum=0)
    if row["receive_index"] is not None:
        _require_int(row["receive_index"], "receive_index", minimum=0)
    if row["observed_at"] is not None:
        _require_text(row["observed_at"], "observed_at")
    _require_bool(row["historical"], "historical")


def _validate_settings_payload(payload: dict[str, object]) -> None:
    _require_bool(payload["enabled"], "enabled")
    _require_number(payload["interface_scale"], "interface_scale", 0.75, 2.0)
    _require_int(payload["left_offset"], "left_offset", minimum=-2000)
    if payload["left_offset"] > 2000:
        raise ValueError("left_offset is outside its allowed range")
    _require_number(payload["notification_duration"], "notification_duration", 1.0, 30.0)
    _require_bool(payload["reduced_motion"], "reduced_motion")
    _require_int(payload["max_visible"], "max_visible", minimum=1)
    if payload["max_visible"] > 10:
        raise ValueError("max_visible is outside its allowed range")


def _validate_snapshot_payload(payload: dict[str, object]) -> None:
    for field in ("ledger_rows", "visible_notifications", "waiting_notifications"):
        if not isinstance(payload[field], list):
            raise ValueError(f"{field} must be an array")
        for row in payload[field]:
            _validate_event_row(row)
    _require_int(payload["unread_count"], "unread_count", minimum=0)
    for field in ("is_open", "is_focused", "reload_required", "enabled", "reduced_motion"):
        _require_bool(payload[field], field)
    if payload["active_filter"] not in ("all", "received", "sent"):
        raise ValueError("active_filter is invalid")
    _require_text(payload["connection_status"], "connection_status")
    _validate_settings_payload({field: payload[field] for field in _SETTINGS_FIELDS})


def _validate_parent(kind: object, payload: object) -> tuple[str, dict[str, object]]:
    if not isinstance(kind, str) or kind not in _PARENT_TYPES:
        raise ValueError("message type is invalid")
    if kind == "shutdown":
        return kind, _require_exact_keys(payload, frozenset(), kind)
    if kind == "settings":
        checked = _require_exact_keys(payload, _SETTINGS_FIELDS, kind)
        _validate_settings_payload(checked)
        return kind, checked
    checked = _require_exact_keys(payload, _SNAPSHOT_FIELDS, kind)
    _validate_snapshot_payload(checked)
    return kind, checked


def encode_parent_message(message: ParentMessage) -> str:
    if not isinstance(message, ParentMessage):
        raise ValueError("parent message is invalid")
    payload = _json_value(dict(message.payload))
    kind, checked_payload = _validate_parent(message.kind, payload)
    return json.dumps(
        {"version": PROTOCOL_VERSION, "type": kind, "payload": checked_payload},
        separators=(",", ":"), sort_keys=True, allow_nan=False,
    )


def decode_parent_message(encoded: str) -> ParentMessage:
    decoded = _decode_json(encoded)
    if not isinstance(decoded, dict):
        raise ValueError("protocol top-level fields are invalid")
    if not isinstance(decoded.get("type"), str) or decoded["type"] not in _PARENT_TYPES:
        raise ValueError("message type is invalid")
    if set(decoded) != {"version", "type", "payload"}:
        raise ValueError("protocol top-level fields are invalid")
    if type(decoded["version"]) is not int or decoded["version"] != PROTOCOL_VERSION:
        raise ValueError("protocol version is not supported")
    kind, payload = _validate_parent(decoded["type"], decoded["payload"])
    return ParentMessage(kind, payload)


def snapshot_message(value: OverlaySnapshot) -> ParentMessage:
    if not isinstance(value, OverlaySnapshot):
        raise ValueError("overlay snapshot is invalid")
    return ParentMessage("snapshot", {
        field: _to_json_container(getattr(value, field))
        for field in OverlaySnapshot.__dataclass_fields__
    })


def settings_message(payload: Mapping[str, object]) -> ParentMessage:
    return ParentMessage("settings", dict(payload))


def shutdown_message() -> ParentMessage:
    return ParentMessage("shutdown", {})


def _to_json_container(value: object) -> object:
    if isinstance(value, tuple):
        return [_to_json_container(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_json_container(item) for key, item in value.items()}
    return value


def decode_child_action(encoded: str) -> OverlayAction:
    decoded = _decode_json(encoded)
    if not isinstance(decoded, dict) or set(decoded) != {"version", "type", "payload"}:
        raise ValueError("protocol top-level fields are invalid")
    if type(decoded["version"]) is not int or decoded["version"] != PROTOCOL_VERSION:
        raise ValueError("protocol version is not supported")
    if decoded["type"] != "action":
        raise ValueError("child message type is invalid")
    payload = _require_exact_keys(decoded["payload"], frozenset(("kind", "value")), "action")
    kind = payload["kind"]
    value = payload["value"]
    if not isinstance(kind, str):
        raise ValueError("child action is invalid")
    if value is not None and not isinstance(value, str):
        raise ValueError("child action value is invalid")
    try:
        return validate_action(OverlayAction(kind, value))
    except ValueError as error:
        raise ValueError("child action is invalid") from error
