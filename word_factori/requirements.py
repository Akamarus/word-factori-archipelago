from __future__ import annotations

from .data import LOCATIONS, LocationData
from .capabilities import requirements_for_record

WORD_REQUIREMENT_OPTIONS = {
    location.target: location.requirement_options
    for location in LOCATIONS
    if location.kind in {"word", "final"}
}

def requirements_for(location: LocationData) -> tuple[frozenset[str], ...]:
    return requirements_for_record(location)


def access_rule_for(location: LocationData, player: int):
    requirements = requirements_for(location)
    predecessor = LOCATIONS[location.slot_index - 1].name if location.slot_index else None

    def rule(state) -> bool:
        if predecessor is not None and not state.can_reach_location(predecessor, player):
            return False
        return any(state.has_all(needs, player) for needs in requirements)

    return rule
