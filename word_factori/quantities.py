"""Pure progressive family arithmetic. No game, network or AP dependencies.

An allowance is 0..4 or -1 (unlimited); a budget is a nonnegative count.
Authoritative AP inventories already include precollected items. Only a fresh
native-context fallback should request the explicit bootstrap addition.
"""
from collections.abc import Iterable, Mapping, Sequence

FAMILIES = ('Bender', 'Rotation', 'Reflection', 'Merger2', 'Merger3', 'Merger4')
PROGRESSIVE_ITEMS = tuple(f'Progressive {name} Access' for name in FAMILIES)
MAX_SAFE_INTEGER = 2**53 - 1
QUANTITY_MODEL = 'progressive_machine_quantities_v1'
MODULE_FAMILIES = {
    'Bend': 0, 'Rotate_cw': 1, 'Rotate_ccw': 1,
    'Reflect_hor': 2, 'Reflect_vert': 2,
    'Merger2': 3, 'Merger3': 4, 'Merger4': 5,
}
Vector = tuple[int, ...]


def _nonnegative(value: object) -> bool:
    return type(value) is int and 0 <= value <= MAX_SAFE_INTEGER


def checked_vector(values: Sequence[int], *, allowance: bool = False) -> Vector:
    if not isinstance(values, (list, tuple)) or len(values) != len(FAMILIES):
        raise ValueError('machine vector must contain exactly six counts')
    valid = (lambda n: type(n) is int and n in (-1, 0, 1, 2, 3, 4)) if allowance else _nonnegative
    if not all(valid(n) for n in values):
        raise ValueError('invalid machine allowance' if allowance else 'invalid machine budget')
    return tuple(values)


def limits_for_counts(counts: Mapping[str, int], *, bootstrap: bool = False) -> Vector:
    if not isinstance(counts, Mapping) or not all(
        isinstance(name, str) and _nonnegative(count) for name, count in counts.items()
    ) or type(bootstrap) is not bool:
        raise ValueError('inventory must map item names to nonnegative integer counts')
    tiers = [counts.get(item, 0) for item in PROGRESSIVE_ITEMS]
    tiers[0] += int(bootstrap)
    return tuple(-1 if n >= 5 else n for n in tiers)


def affords(limits: Sequence[int], budget: Sequence[int]) -> bool:
    limits = checked_vector(limits, allowance=True)
    budget = checked_vector(budget)
    return all(limit == -1 or need <= limit for limit, need in zip(limits, budget))


def missing_tiers(limits: Sequence[int], budget: Sequence[int]) -> Vector:
    limits = checked_vector(limits, allowance=True)
    budget = checked_vector(budget)
    return tuple(max(0, min(need, 5) - (5 if limit == -1 else limit))
                 for limit, need in zip(limits, budget))


def placed_counts(modules: Iterable[str]) -> Vector:
    counts = [0] * len(FAMILIES)
    for module in modules:
        if not isinstance(module, str):
            raise ValueError('machine name must be a string')
        name = module.removeprefix('o')
        if name in ('IFactory', 'FinalWord'):
            continue
        if name not in MODULE_FAMILIES:
            raise ValueError(f'unsupported machine: {module}')
        counts[MODULE_FAMILIES[name]] += 1
    return tuple(counts)


def describe_allowances(limits: Sequence[int]) -> str:
    return ', '.join(f'{name}: {"unlimited" if limit == -1 else limit}'
                     for name, limit in zip(FAMILIES, checked_vector(limits, allowance=True)))


def describe_missing(limits: Sequence[int], budgets: Iterable[Sequence[int]]) -> str:
    alternatives = list(dict.fromkeys(missing_tiers(limits, budget) for budget in budgets))
    if any(not any(route) for route in alternatives):
        return 'ready'
    frontier = [route for route in alternatives if not any(
        other != route and all(a <= b for a,b in zip(other,route)) for other in alternatives)]
    return ' or '.join(' + '.join(f'{n} {name} upgrade{"s" if n != 1 else ""}'
                                 for name,n in zip(FAMILIES,route) if n)
                       for route in frontier) or 'no verified route under this level’s restrictions'
