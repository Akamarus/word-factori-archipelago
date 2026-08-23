from __future__ import annotations

from dataclasses import dataclass
import ntpath
from typing import Iterable, Mapping
import urllib.parse
from pathlib import Path

from .bridge import ReceivedItem
from .data import LOCATIONS, MACHINE_ITEMS
from .save import ActiveSlot


def game_font_path(executable: Path) -> Path | None:
    """Return the installed Fredoka font beside the game, without copying it."""
    if not isinstance(executable, Path):
        raise ValueError("executable must be a Path")
    candidate = executable.with_name("FredokaOne.ttf")
    return candidate if candidate.is_file() else None


@dataclass(frozen=True)
class InventoryView:
    owned_machines: set[str]
    world_access: int


def inventory_view(received: Iterable[ReceivedItem]) -> InventoryView:
    names = [item.name for item in received]
    owned = set(MACHINE_ITEMS).intersection(names)
    return InventoryView(owned, names.count("Progressive World Access"))


def goal_reached(goal: int, campaign_count: int, checked_indices: set[int]) -> bool:
    if goal == 0:
        return len(set(range(30)).intersection(checked_indices)) >= campaign_count
    if goal == 1:
        return 29 in checked_indices
    raise ValueError(f"unknown goal value {goal}")


def campaign_compatible(
    slot_data: Mapping[str, object],
    installed: Mapping[str, object],
) -> bool:
    return (
        slot_data.get("campaign_id") == installed.get("campaign_id")
        and slot_data.get("manifest_version") == installed.get("manifest_version")
        and slot_data.get("manifest_digest") == installed.get("manifest_digest")
        and installed.get("level_count") == len(LOCATIONS)
    )


def resolve_game_slot_binding(bound_id: str | None, active: ActiveSlot) -> str:
    if bound_id is None:
        if active.beaten_levels:
            raise ValueError(
                "The active Word Factori save has prior completions and cannot be auto-bound. "
                "Select an empty save slot for this Archipelago room."
            )
        return active.random_id
    if bound_id != active.random_id:
        raise ValueError(
            "A different Word Factori save is active. Return to the empty save slot bound to this Archipelago room."
        )
    return bound_id


def mod_is_selected(payload: Mapping[str, object], expected_folder: str) -> bool:
    folder = payload.get("folder")
    if not isinstance(folder, str) or not folder.strip():
        return False
    actual = ntpath.normcase(ntpath.normpath(folder.strip()))
    expected = ntpath.normcase(ntpath.normpath(expected_folder))
    if ntpath.isabs(actual):
        return actual == expected
    return actual == ntpath.basename(expected)


def parse_connection_url(value: str) -> tuple[str, str | None, str | None]:
    url = urllib.parse.urlparse(value)
    if url.scheme != "archipelago" or not url.hostname:
        raise ValueError("expected an archipelago:// connection URL")
    host = f"[{url.hostname}]" if ":" in url.hostname else url.hostname
    address = f"{host}:{url.port}" if url.port is not None else host
    name = urllib.parse.unquote(url.username) if url.username else None
    password = urllib.parse.unquote(url.password) if url.password else None
    return address, name, password


def state_identity(seed_name: str | None, team: int | None, slot: int | None, auth: str | None) -> str:
    return f"{seed_name or 'unknown-seed'}-team-{team if team is not None else 'unknown'}-slot-{slot if slot is not None else 'unknown'}-{auth or 'unnamed'}"
