"""Deterministic quantity identity shared by generator, tracker and client."""
from functools import lru_cache
from types import MappingProxyType

from .quantities import QUANTITY_MODEL, PROGRESSIVE_ITEMS, affords, limits_for_counts
from .quantity_graphs import load_catalog, payload_digest
from .quantity_logic import budgets_for_location, budgets_for_word, pareto_budgets

FIELDS = ('quantity_model', 'quantity_catalog_digest', 'quantity_budget_digest')


@lru_cache(maxsize=128)
def check_budgets(locations, orders, recipe_checks):
    result = {location.code: budgets_for_location(location) for location in locations}
    result.update({order.code: budgets_for_word(order.word) for order in orders})
    if recipe_checks:
        result.update({code: pareto_budgets(graphs) for code, graphs in load_catalog().recipes.items()})
    if any(not routes for routes in result.values()):
        raise ValueError('quantity catalog has no factory for a required check')
    return MappingProxyType(result)


def quantity_slot_data(enabled, locations, orders, recipe_checks):
    if not enabled:
        return {}
    budgets = check_budgets(tuple(locations), tuple(orders), recipe_checks)
    return {'progressive_machines': True, 'quantity_model': QUANTITY_MODEL,
            'quantity_catalog_digest': load_catalog().digest,
            'quantity_budget_digest': payload_digest({str(k): v for k,v in budgets.items()})}


def quantity_enabled(slot):
    enabled = slot.get('progressive_machines', False)
    if type(enabled) is not bool:
        raise ValueError('progressive_machines must be a boolean')
    if (slot.get('progression_model') == QUANTITY_MODEL) != enabled:
        raise ValueError('progressive machine setting does not match its room model')
    if not enabled:
        if any(name in slot for name in FIELDS):
            raise ValueError('disabled progressive machines cannot include quantity metadata')
        return False
    if slot.get('quantity_model') != QUANTITY_MODEL or slot.get('quantity_catalog_digest') != load_catalog().digest:
        raise ValueError('quantity catalog or version does not match; install the matching release')
    digest = slot.get('quantity_budget_digest')
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('invalid quantity budget digest')
    return True


def validate_quantity_contract(slot, locations, orders, recipe_checks):
    enabled = quantity_enabled(slot)
    if enabled:
        expected = quantity_slot_data(True, locations, orders, recipe_checks)
        if any(slot.get(name) != value for name,value in expected.items()):
            raise ValueError('quantity check budgets do not match this room')
    return enabled


def quantity_rule(budgets, player):
    @lru_cache(maxsize=4096)
    def affordable(limits):
        return any(affords(limits, budget) for budget in budgets)
    def rule(state):
        limits = limits_for_counts({item: state.count(item, player) for item in PROGRESSIVE_ITEMS})
        return affordable(limits)
    return rule


def campaign_quantity_rules(locations, budgets, player):
    """Evaluate the acyclic four-of-six page chain once per inventory, not recursively."""
    from .layout import PAGE_SIZE, PAGE_UNLOCK_COUNT
    ordered = tuple(sorted(locations, key=lambda location: location.slot_index))
    @lru_cache(maxsize=4096)
    def reachable(limits):
        reached = set()
        for start in range(0, len(ordered), PAGE_SIZE):
            page = ordered[start:start + PAGE_SIZE]
            count = 0
            for location in page:
                if any(affords(limits, budget) for budget in budgets[location.code]):
                    reached.add(location.code)
                    count += 1
            if count < PAGE_UNLOCK_COUNT:
                break
        return frozenset(reached)
    def for_code(code):
        def rule(state):
            limits = limits_for_counts({item: state.count(item, player) for item in PROGRESSIVE_ITEMS})
            return code in reachable(limits)
        return rule
    return {location.code: for_code(location.code) for location in ordered}
