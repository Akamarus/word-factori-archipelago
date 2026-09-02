from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any

from .campaign import CampaignManifest, CampaignRecord, campaign_digest
from .capabilities import FULL, unavoidable_nonbootstrap_machines


PAGE_SIZE = 6
PAGE_UNLOCK_COUNT = 4
PROGRESSION_MODEL = "four_of_six_v1"
FIXED_ALGORITHM = "fixed_pages_v1"
SHUFFLED_ALGORITHM = "balanced_pages_v1"
_SHUFFLE_ATTEMPT_BUDGET = 100_000
_CAPPED_MACHINES = FULL - {"Bender Access", "Merger2 Access"}


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


def _balanced_page(
    page: list[str] | tuple[str, ...],
    machine_profiles: dict[str, frozenset[str]],
) -> bool:
    profiles = {machine_profiles[stable_key] for stable_key in page}
    return len(profiles) >= 3 and all(
        sum(
            machine in machine_profiles[stable_key]
            for stable_key in page
        ) < 4
        for machine in _CAPPED_MACHINES
    )


def shuffled_layout(
    manifest: CampaignManifest, level_set: str, random_source: Any
) -> CampaignLayout:
    records = {record.stable_key: record for record in manifest.levels}
    anchors = {"complete-i", "complete-c", "pitchfork-final"}
    if not anchors <= set(records):
        raise ValueError("balanced_pages_v1 could not satisfy page constraints")

    priorities = {
        record.stable_key: random_source.random() for record in manifest.levels
    }
    machine_profiles = {
        stable_key: unavoidable_nonbootstrap_machines(record)
        for stable_key, record in records.items()
    }
    candidate_order = tuple(
        sorted(records, key=lambda stable_key: (priorities[stable_key], stable_key))
    )
    page_count = (len(records) + PAGE_SIZE - 1) // PAGE_SIZE
    pages: list[tuple[str, ...]] = [tuple() for _ in range(page_count)]
    attempts = 0
    failed_states: set[
        tuple[int, tuple[tuple[str, tuple[str, ...], int], ...]]
    ] = set()

    def candidate_allowed(stable_key: str, page_index: int) -> bool:
        kind = records[stable_key].kind
        if page_index == 0 and kind in {"challenge", "discovery", "final"}:
            return False
        return not (page_index < 2 and kind == "challenge")

    def build_page(
        page_index: int,
        page: list[str],
        remaining: frozenset[str],
        start_position: int,
    ) -> bool:
        nonlocal attempts
        target_size = min(PAGE_SIZE, len(records) - page_index * PAGE_SIZE)
        if len(page) == target_size:
            if target_size == PAGE_SIZE and not _balanced_page(
                page, machine_profiles
            ):
                return False
            if page_index == 0 and sum(
                "Merger2 Access" not in machine_profiles[stable_key]
                for stable_key in page
            ) < 4:
                return False
            ordered_page = tuple(
                sorted(page, key=lambda stable_key: (priorities[stable_key], stable_key))
            )
            pages[page_index] = ordered_page
            return build_next_page(page_index + 1, remaining)

        positions = range(start_position, len(candidate_order))
        if 2 <= page_index < page_count - 1 and not page:
            first_remaining_position = next(
                (
                    position
                    for position, stable_key in enumerate(candidate_order)
                    if stable_key in remaining
                ),
                None,
            )
            if first_remaining_position is None:
                return False
            positions = (first_remaining_position,)
        seen_signatures: set[tuple[str, frozenset[str]]] = set()
        for position in positions:
            stable_key = candidate_order[position]
            if stable_key not in remaining:
                continue
            signature = (
                records[stable_key].kind,
                machine_profiles[stable_key],
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            attempts += 1
            if attempts > _SHUFFLE_ATTEMPT_BUDGET:
                raise ValueError(
                    "balanced_pages_v1 could not satisfy page constraints"
                )
            if not candidate_allowed(stable_key, page_index):
                continue
            candidate_page = [*page, stable_key]
            if target_size == PAGE_SIZE and any(
                sum(
                    machine in machine_profiles[key]
                    for key in candidate_page
                ) >= 4
                for machine in _CAPPED_MACHINES
            ):
                continue
            if build_page(
                page_index,
                candidate_page,
                remaining - {stable_key},
                position + 1,
            ):
                return True
        return False

    def build_next_page(page_index: int, remaining: frozenset[str]) -> bool:
        if page_index == page_count:
            return not remaining
        signature_counts = Counter(
            (
                records[stable_key].kind,
                tuple(sorted(machine_profiles[stable_key])),
            )
            for stable_key in remaining
        )
        state = (
            page_index,
            tuple(
                sorted(
                    (kind, profile, count)
                    for (kind, profile), count in signature_counts.items()
                )
            ),
        )
        if state in failed_states:
            return False
        page: list[str] = []
        if page_index == 0:
            page.extend(("complete-i", "complete-c"))
        if page_index == page_count - 1:
            page.append("pitchfork-final")
        if build_page(page_index, page, remaining, 0):
            return True
        failed_states.add(state)
        return False

    remaining = frozenset(records) - anchors
    if not build_next_page(0, remaining):
        raise ValueError("balanced_pages_v1 could not satisfy page constraints")

    first_page = list(pages[0])
    random_source.shuffle(first_page)
    pages[0] = tuple(first_page)
    ordered_stable_keys = tuple(stable_key for page in pages for stable_key in page)
    layout = CampaignLayout(
        algorithm=SHUFFLED_ALGORITHM,
        level_set=level_set,
        progression_model=PROGRESSION_MODEL,
        base_manifest_digest=campaign_digest(manifest),
        ordered_stable_keys=ordered_stable_keys,
        digest="",
    )
    layout = replace(layout, digest=_layout_digest(layout))
    validate_layout(manifest, layout)
    return layout


def build_layout(
    manifest: CampaignManifest, level_set: str, mode: str, random_source: Any
) -> CampaignLayout:
    if mode == "fixed_pages":
        return fixed_layout(manifest, level_set)
    if mode == "shuffled_pages":
        return shuffled_layout(manifest, level_set, random_source)
    raise ValueError(f"layout mode is invalid: {mode}")


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
