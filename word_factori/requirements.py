from __future__ import annotations

from .data import LOCATIONS, LocationData

FULL = frozenset({"Bender Access", "Rotation Access", "Reflection Access", "Merger2 Access", "Merger3 Access", "Merger4 Access"})

WORD_REQUIREMENT_OPTIONS = {
    location.target: location.requirement_options
    for location in LOCATIONS
    if location.kind in {"word", "final"}
}

# These three levels also impose machine-count limits. The requirements below
# are backed by layouts observed in the installed game's own save schema.
CHALLENGE_REQUIREMENTS = {
    26: (frozenset({"Bender Access", "Rotation Access", "Reflection Access", "Merger2 Access"}),),
    27: (frozenset({"Bender Access", "Rotation Access", "Reflection Access", "Merger2 Access", "Merger3 Access"}),),
    28: (FULL,),
}


def requirements_for(location: LocationData) -> tuple[frozenset[str], ...]:
    if location.kind == "discovery":
        return (location.required_route,)
    if location.kind == "challenge":
        return CHALLENGE_REQUIREMENTS[location.index]
    return location.requirement_options


def access_rule_for(location: LocationData, player: int):
    requirements = requirements_for(location)
    predecessor = LOCATIONS[location.index - 1].name if location.index else None

    def rule(state) -> bool:
        if predecessor is not None and not state.can_reach_location(predecessor, player):
            return False
        return any(state.has_all(needs, player) for needs in requirements)

    return rule
