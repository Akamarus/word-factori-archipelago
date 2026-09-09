from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class ActiveSlot:
    key: str
    random_id: str
    beaten_levels: frozenset[int]


def _selected_slot_key(previous: object) -> str:
    if isinstance(previous, bool) or not isinstance(previous, (int, float)):
        raise ValueError("save selection pointer is not a native integer")
    try:
        numeric_key = int(previous)
    except (OverflowError, ValueError):
        raise ValueError("save selection pointer is not a native integer") from None
    if numeric_key < 0 or numeric_key != previous:
        raise ValueError("No Word Factori save is selected. Enter the room's save slot first.")
    return str(numeric_key)


def parse_active_slot(payload: dict) -> ActiveSlot:
    if not isinstance(payload, dict):
        raise ValueError("save is not an object")
    slots = payload.get("slots")
    if not isinstance(slots, dict):
        raise ValueError("save has no slots object")
    if any(not isinstance(slot, dict) for slot in slots.values()):
        raise ValueError("save slot is not an object")
    active = [(str(key), slot) for key, slot in slots.items() if slot.get("slot_is_active") == 1]
    # Verified native slot-button behavior stores the selection in slot zero,
    # regardless of which slot is selected. Activation flags persist for all
    # used slots. -1 means the player has returned to the save-selection menu.
    if "previous_save" in slots.get("0", {}):
        selected_key = _selected_slot_key(slots["0"]["previous_save"])
        active = [(key, slot) for key, slot in active if key == selected_key]
    if len(active) != 1:
        raise ValueError(f"expected exactly one active slot, found {len(active)}")
    key, slot = active[0]
    random_id = slot.get("random_id")
    if not isinstance(random_id, str) or not random_id:
        raise ValueError("active slot has no stable random_id")
    beaten = slot.get("beaten_levels", {})
    if not isinstance(beaten, dict):
        raise ValueError("active slot beaten_levels is not an object")
    return ActiveSlot(
        key=key,
        random_id=random_id,
        beaten_levels=frozenset(int(index) for index, value in beaten.items() if value),
    )


def parse_save(payload: dict) -> frozenset[int]:
    return parse_active_slot(payload).beaten_levels


def read_save(path: Path) -> frozenset[int]:
    return parse_save(json.loads(path.read_text(encoding="utf-8")))


def read_active_slot(path: Path) -> ActiveSlot:
    return parse_active_slot(json.loads(path.read_text(encoding="utf-8")))


def find_save(local_app_data: Path, mod_folder: Path | None = None) -> Path:
    reference = json.loads((local_app_data / "factori" / "user_ref.json").read_text(encoding="utf-8"))
    folder = reference["most_recent_steam"]
    account = local_app_data / "factori" / folder
    path = account / mod_folder / "save.json" if mod_folder is not None else account / "save.json"
    if not path.is_file(): raise FileNotFoundError(path)
    return path
