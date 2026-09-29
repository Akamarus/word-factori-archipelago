from __future__ import annotations

from contextvars import ContextVar

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
    *, integration_mode: str = "supported", quantity_budgets=None, reach_location=None,
):
    requirements = requirements_for(location)
    if quantity_budgets is not None:
        from .quantity_contract import quantity_rule
        machine_rule = quantity_rule(quantity_budgets, player)
    else:
        machine_rule = lambda state: any(state.has_all(needs, player) for needs in requirements)
    predecessors = previous_page_names(location, locations)
    threshold = TUTORIAL_PAGE_UNLOCK_COUNT if location.page_index == 1 and integration_mode == "supported" else PAGE_UNLOCK_COUNT
    if integration_mode == "supported" and 0 < location.slot_index < PAGE_SIZE:
        predecessors = (locations[location.slot_index - 1].name,)
        threshold = 1
    lookup = reach_location or (lambda state, name: state.can_reach_location(name, player))

    def rule(state) -> bool:
        # Reject unavailable machines before recursively traversing earlier
        # pages, and stop as soon as the page threshold is met. Counting all
        # six branches on every page multiplies work deep into the campaign.
        if not machine_rule(state):
            return False
        if not predecessors:
            return True
        needed = threshold
        for name in predecessors:
            if lookup(state, name):
                needed -= 1
                if needed == 0:
                    return True
        return False

    return rule


def campaign_access_rules(locations, player, *, integration_mode="enhanced"):
    """Share predecessor answers only during one synchronous rule evaluation.

    Keep querying AP's real location reachability, including region/hook rules.
    Discard answers after each root query, including exceptions. Like ordinary
    AP access rules, this assumes inventory is stable during a synchronous query.
    """
    current = ContextVar("word_factori_page_evaluation", default=None)

    def lookup(state, name):
        frame = current.get()
        if frame is None or frame[0] is not state:
            return state.can_reach_location(name, player)
        answers = frame[1]
        if name not in answers:
            answers[name] = state.can_reach_location(name, player)
        return answers[name]

    def wrap(evaluate):
        def rule(state):
            frame = current.get()
            if frame is not None and frame[0] is state:
                return evaluate(state)
            token = current.set((state, {}))
            try:
                return evaluate(state)
            finally:
                current.reset(token)
        return rule

    return {location.code: wrap(access_rule_for(
        location, locations, player, integration_mode=integration_mode,
        reach_location=lookup)) for location in locations}
