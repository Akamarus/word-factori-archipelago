from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ntpath
from typing import Iterable, Mapping
import urllib.parse
from pathlib import Path

from .bridge import ReceivedItem
from .campaign import CampaignManifest, campaign_digest, campaign_for_level_set
from .data import (
    DEFAULT_LEVEL_SET,
    LOCATIONS,
    MACHINE_ITEMS,
    LocationData,
    locations_for_layout,
    locations_for_manifest,
)
from .layout import CampaignLayout, PROGRESSION_MODEL, layout_from_slot_data
from .save import ActiveSlot


_LAYOUT_SLOT_DATA_FIELDS = (
    "progression_model",
    "layout_algorithm",
    "page_size",
    "page_unlock_count",
    "base_manifest_digest",
    "layout_digest",
    "level_order",
)
_LAYOUT_IDENTITY_FIELDS = _LAYOUT_SLOT_DATA_FIELDS[:-1]


def utc_observed_at() -> str:
    """Return a parseable UTC observation time for live cosmetic events."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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


@dataclass(frozen=True)
class ResolvedCampaign:
    manifest: CampaignManifest
    layout: CampaignLayout | None
    locations: tuple[LocationData, ...]
    legacy: bool


def inventory_view(received: Iterable[ReceivedItem]) -> InventoryView:
    names = [item.name for item in received]
    owned = set(MACHINE_ITEMS).intersection(names)
    return InventoryView(owned, names.count("Progressive World Access"))


def goal_reached(
    goal: int,
    campaign_count: int,
    checked_codes: set[int] | frozenset[int],
    locations: tuple[LocationData, ...] = LOCATIONS,
) -> bool:
    if goal == 0:
        campaign_codes = {
            location.code for location in locations if location.kind != "discovery"
        }
        return len(campaign_codes.intersection(checked_codes)) >= campaign_count
    if goal == 1:
        final_codes = {
            location.code for location in locations
            if location.stable_key == "pitchfork-final"
        }
        if len(final_codes) != 1:
            raise ValueError("campaign must contain exactly one pitchfork-final location")
        return not final_codes.isdisjoint(checked_codes)
    raise ValueError(f"unknown goal value {goal}")


def resolve_room_campaign(slot_data: Mapping[str, object]) -> ResolvedCampaign:
    """Reconstruct a bundled campaign only when all room identity data validates."""
    if not isinstance(slot_data, Mapping):
        raise ValueError("room slot data is invalid")
    level_set = slot_data.get("level_set", DEFAULT_LEVEL_SET)
    try:
        manifest = campaign_for_level_set(level_set)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError(f"room campaign level set is invalid: {error}") from error
    if slot_data.get("campaign_id") != manifest.campaign_id:
        raise ValueError("room campaign ID does not match the bundled manifest")
    if slot_data.get("manifest_version") != manifest.version:
        raise ValueError("room manifest version does not match the bundled manifest")
    if slot_data.get("level_count") != len(manifest.levels):
        raise ValueError("room campaign level count does not match the bundled manifest")

    if "progression_model" not in slot_data:
        if slot_data.get("manifest_digest") != campaign_digest(manifest):
            raise ValueError("room manifest digest does not match the bundled manifest")
        return ResolvedCampaign(
            manifest=manifest,
            layout=None,
            locations=locations_for_manifest(manifest),
            legacy=True,
        )

    if slot_data.get("progression_model") != PROGRESSION_MODEL:
        raise ValueError("room progression model is unsupported")
    layout_payload = {
        field: slot_data.get(field) for field in _LAYOUT_SLOT_DATA_FIELDS
    }
    try:
        layout = layout_from_slot_data(manifest, str(level_set), layout_payload)
    except (TypeError, ValueError) as error:
        raise ValueError(f"room campaign layout is invalid: {error}") from error
    if slot_data.get("manifest_digest") != layout.digest:
        raise ValueError("room manifest digest does not match the campaign layout")
    return ResolvedCampaign(
        manifest=manifest,
        layout=layout,
        locations=locations_for_layout(manifest, layout),
        legacy=False,
    )


def _location_maps(
    locations: tuple[LocationData, ...],
) -> tuple[dict[int, int], dict[int, int]]:
    slots_to_codes: dict[int, int] = {}
    codes_to_slots: dict[int, int] = {}
    for location in locations:
        if location.slot_index in slots_to_codes:
            raise ValueError("location mapping has a duplicate native slot")
        if location.code in codes_to_slots:
            raise ValueError("location mapping has a duplicate location code")
        slots_to_codes[location.slot_index] = location.code
        codes_to_slots[location.code] = location.slot_index
    if set(slots_to_codes) != set(range(len(locations))):
        raise ValueError("location mapping native slots must be contiguous from zero")
    return slots_to_codes, codes_to_slots


def location_codes_for_native_slots(
    native_slots: Iterable[int], locations: tuple[LocationData, ...],
) -> frozenset[int]:
    slots_to_codes, _ = _location_maps(locations)
    return frozenset(
        slots_to_codes[slot] for slot in native_slots if slot in slots_to_codes
    )


def native_slots_for_location_codes(
    location_codes: Iterable[int], locations: tuple[LocationData, ...],
) -> frozenset[int]:
    _, codes_to_slots = _location_maps(locations)
    return frozenset(
        codes_to_slots[code] for code in location_codes if code in codes_to_slots
    )


def campaign_compatible(
    slot_data: Mapping[str, object],
    installed: Mapping[str, object],
) -> bool:
    compatible = (
        slot_data.get("campaign_id") == installed.get("campaign_id")
        and slot_data.get("manifest_version") == installed.get("manifest_version")
        and slot_data.get("manifest_digest") == installed.get("manifest_digest")
        and installed.get("level_count") == slot_data.get("level_count", len(LOCATIONS))
    )
    return compatible and all(
        field not in slot_data or slot_data.get(field) == installed.get(field)
        for field in _LAYOUT_IDENTITY_FIELDS
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
    owned_name = ntpath.basename(expected)
    return actual in {owned_name, ntpath.join("mods", owned_name)}


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
