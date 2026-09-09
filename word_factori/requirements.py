from __future__ import annotations

from .data import LOCATIONS, LocationData
from .capabilities import requirements_for_record
from .layout import PAGE_SIZE, PAGE_UNLOCK_COUNT, TUTORIAL_PAGE_UNLOCK_COUNT

WORD_REQUIREMENT_OPTIONS = {
    location.target: location.requirement_options
    for location in LOCATIONS
    if location.kind in {"word", "final"}
}

def requirements_for(location: LocationData) -> tuple[frozenset[str], ...]:
    return requirements_for_record(location)


def previous_page_names(
    location: LocationData, locations: tuple[LocationData, ...],
) -> tuple[str, ...]:
    if location.slot_index < PAGE_SIZE:
        return ()
    start = ((location.slot_index // PAGE_SIZE) - 1) * PAGE_SIZE
    return tuple(entry.name for entry in locations[start:start + PAGE_SIZE])


def access_rule_for(
    location: LocationData, locations: tuple[LocationData, ...], player: int,
):
    requirements = requirements_for(location)
    predecessors = previous_page_names(location, locations)
    threshold = TUTORIAL_PAGE_UNLOCK_COUNT if location.page_index == 1 else PAGE_UNLOCK_COUNT
    if 0 < location.slot_index < PAGE_SIZE:
        predecessors = (locations[location.slot_index - 1].name,)
        threshold = 1

    def rule(state) -> bool:
        if predecessors and sum(
            state.can_reach_location(name, player) for name in predecessors
        ) < threshold:
            return False
        return any(state.has_all(needs, player) for needs in requirements)

    return rule
