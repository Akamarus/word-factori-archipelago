from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any

from .campaign import CampaignManifest, CampaignRecord, campaign_digest


PAGE_SIZE = 6
PAGE_UNLOCK_COUNT = 4
PROGRESSION_MODEL = "four_of_six_v1"
FIXED_ALGORITHM = "fixed_pages_v1"
SHUFFLED_ALGORITHM = "balanced_pages_v1"


@dataclass(frozen=True)
class CampaignLayout:
    algorithm: str
    level_set: str
    progression_model: str
    base_manifest_digest: str
    ordered_stable_keys: tuple[str, ...]
    digest: str
    page_size: int = PAGE_SIZE
    page_unlock_count: int = PAGE_UNLOCK_COUNT


@dataclass(frozen=True)
class LayoutEntry:
    slot_index: int
    page_index: int
    record: CampaignRecord


def _layout_digest(layout: CampaignLayout) -> str:
    payload = {
        "algorithm": layout.algorithm,
        "base_manifest_digest": layout.base_manifest_digest,
        "level_set": layout.level_set,
        "ordered_stable_keys": layout.ordered_stable_keys,
        "page_size": layout.page_size,
        "page_unlock_count": layout.page_unlock_count,
        "progression_model": layout.progression_model,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fixed_layout(manifest: CampaignManifest, level_set: str) -> CampaignLayout:
    layout = CampaignLayout(
        algorithm=FIXED_ALGORITHM,
        level_set=level_set,
        progression_model=PROGRESSION_MODEL,
        base_manifest_digest=campaign_digest(manifest),
        ordered_stable_keys=tuple(record.stable_key for record in manifest.levels),
        digest="",
    )
    layout = replace(layout, digest=_layout_digest(layout))
    validate_layout(manifest, layout)
    return layout


def validate_layout(manifest: CampaignManifest, layout: CampaignLayout) -> None:
    if not isinstance(layout, CampaignLayout):
        raise ValueError("layout is invalid")
    if layout.algorithm not in {FIXED_ALGORITHM, SHUFFLED_ALGORITHM}:
        raise ValueError("layout algorithm is invalid")
    if layout.progression_model != PROGRESSION_MODEL:
        raise ValueError("layout progression model is invalid")
    if layout.page_size != PAGE_SIZE or layout.page_unlock_count != PAGE_UNLOCK_COUNT:
        raise ValueError("layout page parameters are invalid")
    if layout.base_manifest_digest != campaign_digest(manifest):
        raise ValueError("layout base manifest digest does not match")

    manifest_keys = tuple(record.stable_key for record in manifest.levels)
    layout_keys = layout.ordered_stable_keys
    if len(layout_keys) != len(manifest_keys) or len(set(layout_keys)) != len(layout_keys):
        raise ValueError("layout stable keys must be complete and unique")
    if set(layout_keys) != set(manifest_keys):
        raise ValueError("layout stable keys do not match the manifest")
    if layout.algorithm == FIXED_ALGORITHM and layout_keys != manifest_keys:
        raise ValueError("fixed layout must preserve canonical stable key order")
    if layout.algorithm == SHUFFLED_ALGORITHM:
        records = {record.stable_key: record for record in manifest.levels}
        pages = tuple(
            layout_keys[start:start + layout.page_size]
            for start in range(0, len(layout_keys), layout.page_size)
        )
        if not {"complete-i", "complete-c"} <= set(pages[0]):
            raise ValueError("balanced layout has invalid first-page anchors")
        if "pitchfork-final" not in pages[-1]:
            raise ValueError("balanced layout has invalid final-page anchor")
        for page_index, page in enumerate(pages):
            kinds = {records[key].kind for key in page}
            if page_index == 0 and kinds & {"challenge", "discovery", "final"}:
                raise ValueError("balanced layout has invalid first-page anchors")
            if page_index < 2 and "challenge" in kinds:
                raise ValueError("balanced layout has invalid challenge anchor")
            if page_index == 0 and "discovery" in kinds:
                raise ValueError("balanced layout has invalid discovery anchor")
    if layout.digest != _layout_digest(layout):
        raise ValueError("layout digest does not match")


def layout_entries(manifest: CampaignManifest, layout: CampaignLayout) -> tuple[LayoutEntry, ...]:
    validate_layout(manifest, layout)
    records = {record.stable_key: record for record in manifest.levels}
    return tuple(
        LayoutEntry(slot_index=index, page_index=index // layout.page_size, record=records[key])
        for index, key in enumerate(layout.ordered_stable_keys)
    )


def layout_slot_data(layout: CampaignLayout) -> dict[str, Any]:
    return {
        "progression_model": layout.progression_model,
        "layout_algorithm": layout.algorithm,
        "page_size": layout.page_size,
        "page_unlock_count": layout.page_unlock_count,
        "base_manifest_digest": layout.base_manifest_digest,
        "layout_digest": layout.digest,
        "level_order": list(layout.ordered_stable_keys),
    }


def layout_from_slot_data(
    manifest: CampaignManifest, level_set: str, slot_data: dict[str, Any]
) -> CampaignLayout:
    expected_keys = {
        "progression_model", "layout_algorithm", "page_size", "page_unlock_count",
        "base_manifest_digest", "layout_digest", "level_order",
    }
    if not isinstance(slot_data, dict) or set(slot_data) != expected_keys:
        raise ValueError("layout slot data has invalid fields")
    if not isinstance(level_set, str):
        raise ValueError("layout level set is invalid")
    if not isinstance(slot_data["progression_model"], str):
        raise ValueError("layout progression model is invalid")
    if not isinstance(slot_data["layout_algorithm"], str):
        raise ValueError("layout algorithm is invalid")
    if type(slot_data["page_size"]) is not int or type(slot_data["page_unlock_count"]) is not int:
        raise ValueError("layout page parameters are invalid")
    if not isinstance(slot_data["base_manifest_digest"], str):
        raise ValueError("layout base manifest digest is invalid")
    if not isinstance(slot_data["layout_digest"], str):
        raise ValueError("layout digest is invalid")
    if not isinstance(slot_data["level_order"], list) or not all(
        isinstance(key, str) for key in slot_data["level_order"]
    ):
        raise ValueError("layout stable keys are invalid")
    layout = CampaignLayout(
        algorithm=slot_data["layout_algorithm"],
        level_set=level_set,
        progression_model=slot_data["progression_model"],
        base_manifest_digest=slot_data["base_manifest_digest"],
        ordered_stable_keys=tuple(slot_data["level_order"]),
        digest=slot_data["layout_digest"],
        page_size=slot_data["page_size"],
        page_unlock_count=slot_data["page_unlock_count"],
    )
    validate_layout(manifest, layout)
    return layout
