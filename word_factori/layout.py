from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any

from .campaign import CampaignManifest, CampaignRecord, campaign_digest
from .capabilities import FULL, requirements_for_record, unavoidable_nonbootstrap_machines


PAGE_SIZE = 6
PAGE_UNLOCK_COUNT = 4
TUTORIAL_PAGE_UNLOCK_COUNT = 6
PROGRESSION_MODEL = "tutorial_six_then_four_v1"
FIXED_ALGORITHM = "fixed_pages_v1"
SHUFFLED_ALGORITHM = "balanced_pages_v2"
ENHANCED_ALGORITHM = "enhanced_balanced_pages_v1"
ENHANCED_MODEL = "enhanced_four_of_six_v1"
MACHINE_MODEL = "machines_tutorial_six_then_four_v1"
ENHANCED_MACHINE_MODEL = "machines_enhanced_four_of_six_v1"
MACHINE_MODELS = frozenset({MACHINE_MODEL, ENHANCED_MACHINE_MODEL})
TUTORIAL_KEYS = (
    "complete-i", "complete-c", "complete-v", "complete-l", "complete-o", "complete-a",
)
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
    integration_mode: str = "supported"
    tutorial_page_unlock_count: int = TUTORIAL_PAGE_UNLOCK_COUNT
    later_page_unlock_count: int = PAGE_UNLOCK_COUNT


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
        "integration_mode": layout.integration_mode,
        "tutorial_page_unlock_count": layout.tutorial_page_unlock_count,
        "later_page_unlock_count": layout.later_page_unlock_count,
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
    *,
    allow_four_rotation: bool = False,
) -> bool:
    profiles = {machine_profiles[stable_key] for stable_key in page}
    return len(profiles) >= 3 and all(
        sum(
            machine in machine_profiles[stable_key]
            for stable_key in page
        ) < (5 if allow_four_rotation and machine == "Rotation Access" else 4)
        for machine in _CAPPED_MACHINES
    )


def shuffled_layout(
    manifest: CampaignManifest, level_set: str, random_source: Any,
    *, enhanced_starter: tuple[str, ...] | None = None,
) -> CampaignLayout:
    records = {record.stable_key: record for record in manifest.levels}
    starter_page = tuple(
        record.stable_key
        for record in manifest.levels
        if record.region == "Starter Workshop" and record.kind != "discovery"
    )
    if starter_page != TUTORIAL_KEYS:
        raise ValueError("balanced_pages_v2 requires the canonical tutorial order")
    enhanced = enhanced_starter is not None
    if enhanced:
        starter_page = enhanced_starter
    anchors = {*starter_page, "pitchfork-final"}
    if not anchors <= set(records):
        raise ValueError("balanced_pages_v2 could not satisfy page constraints")

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
        tuple[int, int, tuple[tuple[str, tuple[str, ...], int], ...]]
    ] = set()

    def candidate_allowed(stable_key: str, page_index: int) -> bool:
        kind = records[stable_key].kind
        if page_index == 0 and kind in ({"challenge", "final"} if enhanced else {"challenge", "discovery", "final"}):
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
                page,
                machine_profiles,
                allow_four_rotation=(
                    level_set == "core_campaign" and page_index > 0
                ),
            ):
                return False
            ordered_page = starter_page if page_index == 0 and not enhanced else tuple(
                sorted(page, key=lambda stable_key: (priorities[stable_key], stable_key))
            )
            pages[page_index] = ordered_page
            return build_next_page(page_index + 1, remaining)

        positions = range(start_position, len(candidate_order))
        # The penultimate page is not interchangeable with the final page,
        # which has the fixed Pitchfork anchor.
        if 2 <= page_index < page_count - 2 and not page:
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
                    "balanced_pages_v2 could not satisfy page constraints"
                )
            if not candidate_allowed(stable_key, page_index):
                continue
            candidate_page = [*page, stable_key]
            if target_size == PAGE_SIZE and any(
                sum(
                    machine in machine_profiles[key]
                    for key in candidate_page
                ) >= (
                    5
                    if level_set == "core_campaign"
                    and page_index > 0
                    and machine == "Rotation Access"
                    else 4
                )
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
            return not remaining and sum(
                sum(
                    "Rotation Access" in machine_profiles[stable_key]
                    for stable_key in page
                ) == 4
                for page in pages[1:]
                if len(page) == PAGE_SIZE
            ) <= (1 if level_set == "core_campaign" else 0)
        signature_counts = Counter(
            (
                records[stable_key].kind,
                tuple(sorted(machine_profiles[stable_key])),
            )
            for stable_key in remaining
        )
        completed_four_rotation_pages = sum(
            sum(
                "Rotation Access" in machine_profiles[stable_key]
                for stable_key in page
            ) == 4
            for page in pages[1:page_index]
            if len(page) == PAGE_SIZE
        )
        state = (
            page_index,
            completed_four_rotation_pages,
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
            page.extend(starter_page)
        if page_index == page_count - 1:
            page.append("pitchfork-final")
        if build_page(page_index, page, remaining, 0):
            return True
        failed_states.add(state)
        return False

    remaining = frozenset(records) - anchors
    if not build_next_page(0, remaining):
        raise ValueError("balanced_pages_v2 could not satisfy page constraints")
    ordered_stable_keys = tuple(stable_key for page in pages for stable_key in page)
    layout = CampaignLayout(
        algorithm=ENHANCED_ALGORITHM if enhanced else SHUFFLED_ALGORITHM,
        level_set=level_set,
        progression_model=ENHANCED_MODEL if enhanced else PROGRESSION_MODEL,
        base_manifest_digest=campaign_digest(manifest),
        ordered_stable_keys=ordered_stable_keys,
        digest="",
        integration_mode="enhanced" if enhanced else "supported",
        tutorial_page_unlock_count=4 if enhanced else 6,
    )
    layout = replace(layout, digest=_layout_digest(layout))
    validate_layout(manifest, layout)
    return layout


def build_layout(
    manifest: CampaignManifest, level_set: str, mode: str, random_source: Any,
    *, integration_mode: str = "supported", machine_only: bool = False,
) -> CampaignLayout:
    if machine_only:
        layout = build_layout(manifest, level_set, mode, random_source, integration_mode=integration_mode)
        layout = replace(layout, progression_model=(
            ENHANCED_MACHINE_MODEL if integration_mode == "enhanced" else MACHINE_MODEL
        ))
        layout = replace(layout, digest=_layout_digest(layout))
        validate_layout(manifest, layout)
        return layout
    if integration_mode not in {"supported", "enhanced"}:
        raise ValueError("layout integration mode is unsupported")
    if integration_mode == "enhanced":
        if mode != "shuffled_pages":
            raise ValueError("Enhanced mode requires shuffled_pages")
        early = {"Bender Access", "Merger2 Access", "Rotation Access"}
        starters = [r.stable_key for r in manifest.levels
                    if r.region == "Starter Workshop" and r.stable_key not in {"complete-i", "complete-c"}
                    and any(route <= early for route in requirements_for_record(r))]
        later = [r.stable_key for r in manifest.levels
                 if r.region != "Starter Workshop" and r.kind not in {"challenge", "final"}]
        if len(starters) < 2 or len(later) < 2:
            raise ValueError("Enhanced campaign has insufficient early/later candidates")
        for _ in range(50):
            first = ("complete-i", "complete-c", *random_source.sample(starters, 2), *random_source.sample(later, 2))
            try:
                return shuffled_layout(manifest, level_set, random_source, enhanced_starter=first)
            except ValueError as error:
                if "could not satisfy page constraints" not in str(error):
                    raise
        raise ValueError("Enhanced campaign could not satisfy page constraints")
    if mode == "fixed_pages":
        return fixed_layout(manifest, level_set)
    if mode == "shuffled_pages":
        return shuffled_layout(manifest, level_set, random_source)
    raise ValueError(f"layout mode is invalid: {mode}")


def validate_layout(manifest: CampaignManifest, layout: CampaignLayout) -> None:
    if not isinstance(layout, CampaignLayout):
        raise ValueError("layout is invalid")
    enhanced = layout.integration_mode == "enhanced"
    if layout.algorithm not in ({ENHANCED_ALGORITHM} if enhanced else {FIXED_ALGORITHM, SHUFFLED_ALGORITHM}):
        raise ValueError("layout algorithm is invalid")
    if layout.progression_model not in ({ENHANCED_MODEL, ENHANCED_MACHINE_MODEL} if enhanced else {PROGRESSION_MODEL, MACHINE_MODEL}):
        raise ValueError("layout progression model is invalid")
    if layout.integration_mode not in {"supported", "enhanced"}:
        raise ValueError("layout integration mode is unsupported")
    if any(type(value) is not int for value in (
        layout.page_size, layout.tutorial_page_unlock_count, layout.later_page_unlock_count,
    )) or (
        layout.page_size != PAGE_SIZE
        or layout.tutorial_page_unlock_count != (4 if enhanced else TUTORIAL_PAGE_UNLOCK_COUNT)
        or layout.later_page_unlock_count != PAGE_UNLOCK_COUNT
    ):
        raise ValueError("layout page parameters are invalid")
    if layout.base_manifest_digest != campaign_digest(manifest):
        raise ValueError("layout base manifest digest does not match")

    manifest_keys = tuple(record.stable_key for record in manifest.levels)
    layout_keys = layout.ordered_stable_keys
    if len(layout_keys) != len(manifest_keys) or len(set(layout_keys)) != len(layout_keys):
        raise ValueError("layout stable keys must be complete and unique")
    if set(layout_keys) != set(manifest_keys):
        raise ValueError("layout stable keys do not match the manifest")
    if not enhanced and layout_keys[:PAGE_SIZE] != TUTORIAL_KEYS:
        raise ValueError("layout must preserve canonical tutorial order")
    if layout.algorithm == FIXED_ALGORITHM and layout_keys != manifest_keys:
        raise ValueError("fixed layout must preserve canonical stable key order")
    if layout.algorithm in {SHUFFLED_ALGORITHM, ENHANCED_ALGORITHM}:
        records = {record.stable_key: record for record in manifest.levels}
        pages = tuple(
            layout_keys[start:start + layout.page_size]
            for start in range(0, len(layout_keys), layout.page_size)
        )
        starter_page = {
            record.stable_key
            for record in manifest.levels
            if record.region == "Starter Workshop" and record.kind != "discovery"
        }
        if not enhanced and (len(starter_page) != PAGE_SIZE or set(pages[0]) != starter_page):
            raise ValueError("balanced layout has invalid canonical starter page")
        if enhanced:
            first = [records[key] for key in pages[0]]
            early = {"Bender Access", "Merger2 Access", "Rotation Access"}
            if not {"complete-i", "complete-c"} <= set(pages[0]) or sum(
                r.region == "Starter Workshop" and any(route <= early for route in requirements_for_record(r))
                for r in first
            ) < 4 or sum(r.region != "Starter Workshop" for r in first) != 2:
                raise ValueError("Enhanced layout has invalid early-solvable first page")
        if "pitchfork-final" not in pages[-1]:
            raise ValueError("balanced layout has invalid final-page anchor")
        for page_index, page in enumerate(pages):
            kinds = {records[key].kind for key in page}
            if page_index == 0 and kinds & ({"challenge", "final"} if enhanced else {"challenge", "discovery", "final"}):
                raise ValueError("balanced layout has invalid first-page anchors")
            if page_index < 2 and "challenge" in kinds:
                raise ValueError("balanced layout has invalid challenge anchor")
            if not enhanced and page_index == 0 and "discovery" in kinds:
                raise ValueError("balanced layout has invalid discovery anchor")
            if len(page) == PAGE_SIZE and not _balanced_page(
                page,
                {
                    key: unavoidable_nonbootstrap_machines(record)
                    for key, record in records.items()
                },
                allow_four_rotation=(
                    layout.level_set == "core_campaign" and page_index > 0
                ),
            ):
                raise ValueError("balanced layout has invalid page balance")
        later_pages_with_four_rotation = sum(
            sum(
                "Rotation Access" in unavoidable_nonbootstrap_machines(records[key])
                for key in page
            ) == 4
            for page in pages[1:]
            if len(page) == PAGE_SIZE
        )
        if later_pages_with_four_rotation > (
            1 if layout.level_set == "core_campaign" else 0
        ):
            raise ValueError("balanced layout has too many four-Rotation pages")
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
        "integration_mode": layout.integration_mode,
        "tutorial_page_unlock_count": layout.tutorial_page_unlock_count,
        "later_page_unlock_count": layout.later_page_unlock_count,
        "base_manifest_digest": layout.base_manifest_digest,
        "layout_digest": layout.digest,
        "level_order": list(layout.ordered_stable_keys),
    }


def layout_from_slot_data(
    manifest: CampaignManifest, level_set: str, slot_data: dict[str, Any]
) -> CampaignLayout:
    expected_keys = {
        "progression_model", "layout_algorithm", "page_size", "integration_mode",
        "tutorial_page_unlock_count", "later_page_unlock_count",
        "base_manifest_digest", "layout_digest", "level_order",
    }
    if isinstance(slot_data, dict) and slot_data.get("progression_model") == "four_of_six_v1":
        raise ValueError("Unpublished beta room used incorrect native rules. Regenerate the room with the current APWorld.")
    if not isinstance(slot_data, dict) or set(slot_data) != expected_keys:
        raise ValueError("layout slot data has invalid fields")
    if not isinstance(level_set, str):
        raise ValueError("layout level set is invalid")
    if not isinstance(slot_data["progression_model"], str):
        raise ValueError("layout progression model is invalid")
    if not isinstance(slot_data["layout_algorithm"], str):
        raise ValueError("layout algorithm is invalid")
    if any(type(slot_data[field]) is not int for field in (
        "page_size", "tutorial_page_unlock_count", "later_page_unlock_count",
    )):
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
        integration_mode=slot_data["integration_mode"],
        tutorial_page_unlock_count=slot_data["tutorial_page_unlock_count"],
        later_page_unlock_count=slot_data["later_page_unlock_count"],
    )
    validate_layout(manifest, layout)
    return layout
