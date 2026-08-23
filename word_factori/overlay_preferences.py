"""Cosmetic, versioned preferences for the independent overlay."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any


PREFERENCES_VERSION = 1
_FIELDS = frozenset((
    "enabled", "interface_scale", "left_offset", "notification_duration", "reduced_motion", "max_visible",
))


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def _bounded_number(value: object, field: str, minimum: float, maximum: float) -> float:
    return min(max(_finite_number(value, field), minimum), maximum)


def _bounded_int(value: object, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return min(max(value, minimum), maximum)


@dataclass(frozen=True)
class OverlayPreferences:
    enabled: bool = True
    interface_scale: float = 1.0
    left_offset: int = 0
    notification_duration: float = 6.0
    reduced_motion: bool = False
    max_visible: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be boolean")
        if not isinstance(self.reduced_motion, bool):
            raise ValueError("reduced_motion must be boolean")
        object.__setattr__(self, "interface_scale", _bounded_number(self.interface_scale, "interface_scale", 0.75, 2.0))
        object.__setattr__(self, "left_offset", _bounded_int(self.left_offset, "left_offset", -2000, 2000))
        object.__setattr__(self, "notification_duration", _bounded_number(
            self.notification_duration, "notification_duration", 1.0, 30.0,
        ))
        object.__setattr__(self, "max_visible", _bounded_int(self.max_visible, "max_visible", 1, 10))


def _from_payload(payload: Any) -> OverlayPreferences:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise ValueError("overlay preferences payload is malformed")
    return OverlayPreferences(**payload)


def load_preferences(path: Path) -> OverlayPreferences:
    """Return defaults for a missing, corrupt, or obsolete cosmetic settings file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"version", "preferences"}:
            raise ValueError("overlay preferences file is malformed")
        if type(payload["version"]) is not int or payload["version"] != PREFERENCES_VERSION:
            raise ValueError("overlay preferences version is unsupported")
        return _from_payload(payload["preferences"])
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return OverlayPreferences()


def save_preferences(path: Path, preferences: OverlayPreferences) -> None:
    """Persist validated cosmetic settings with an atomic replacement."""
    if not isinstance(preferences, OverlayPreferences):
        raise ValueError("overlay preferences are invalid")
    validated = _from_payload({field: getattr(preferences, field) for field in _FIELDS})
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({
                "version": PREFERENCES_VERSION,
                "preferences": {field: getattr(validated, field) for field in sorted(_FIELDS)},
            }, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
