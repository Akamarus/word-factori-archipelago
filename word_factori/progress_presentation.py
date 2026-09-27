"""Read-only explanations; never authorizes checks, machines or native pages."""
from __future__ import annotations

from dataclasses import dataclass

from .client_core import InventoryView, ResolvedCampaign
from .layout import PAGE_SIZE, PAGE_UNLOCK_COUNT
from .quantities import FAMILIES, missing_tiers
from .quantity_logic import budgets_for_location, budgets_for_word
from .requirements import requirements_for
from .word_orders import missing_machine_options

MAX_ROWS = 40
MAX_TEXT = 512
FRESHNESS = frozenset(('current', 'last_known', 'unavailable'))
NO_ROUTE = "No verified route under this level's restrictions"


@dataclass(frozen=True)
class ProgressRow:
    code: int
    page: int
    slot: int
    name: str
    target: str
    kind: str
    completion: str
    page_status: str
    machine_status: str


@dataclass(frozen=True)
class ProgressPresentation:
    rows: tuple[ProgressRow, ...]
    summary: str
    freshness: str


def _alternatives(options: list[str]) -> str:
    if not options:
        return NO_ROUTE
    text = 'Need ' + ' or '.join(options)
    if len(text) <= MAX_TEXT:
        return text
    return 'Need ' + options[0] + f' (or one of {len(options) - 1} alternative routes)'


def _normal_status(routes, owned) -> str:
    missing = set(frozenset(route) - owned for route in routes)
    if frozenset() in missing:
        return 'Machines ready'
    frontier = sorted((route for route in missing if not any(other < route for other in missing)),
                      key=lambda route: (len(route), tuple(sorted(route))))
    return _alternatives([' + '.join(item.removesuffix(' Access') for item in sorted(route))
                          for route in frontier])


def _quantity_status(budgets, limits) -> str:
    missing = set(missing_tiers(limits, budget) for budget in budgets)
    if any(not any(route) for route in missing):
        return 'Machines ready'
    frontier = sorted((route for route in missing if not any(
        other != route and all(a <= b for a, b in zip(other, route)) for other in missing)),
        key=lambda route: (sum(route), route))
    return _alternatives([' + '.join(f'{count} more {family} upgrade{"s" if count != 1 else ""}'
                          for family, count in zip(FAMILIES, route) if count)
                          for route in frontier])


def word_machine_status(word: str, inventory: InventoryView) -> str:
    if inventory.machine_limits is not None:
        return _quantity_status(budgets_for_word(word), inventory.machine_limits)
    return _normal_status(missing_machine_options(word, inventory.owned_machines), frozenset())


def build_progress(campaign: ResolvedCampaign, inventory: InventoryView, *,
                   local_slots: frozenset[int] | None, checked: frozenset[int],
                   pending: frozenset[int], freshness: str) -> ProgressPresentation:
    if freshness not in FRESHNESS:
        raise ValueError('invalid progress freshness')
    locations = tuple(sorted(campaign.locations, key=lambda loc: loc.slot_index))
    if (not 1 <= len(locations) <= MAX_ROWS
            or any(type(loc.slot_index) is not int or loc.slot_index != i
                   or loc.page_index != i // PAGE_SIZE for i, loc in enumerate(locations))
            or len({loc.code for loc in locations}) != len(locations)):
        raise ValueError('invalid progress campaign slots')
    if local_slots is not None and any(type(i) is not int or not 0 <= i < len(locations)
                                       for i in local_slots):
        raise ValueError('invalid observed campaign slot')
    rows = []
    blocker = None
    kinds = dict(word='Campaign level', challenge='Campaign challenge',
                 discovery='Campaign lab', final='Final factory')
    for start in range(0, len(locations), PAGE_SIZE):
        page = locations[start:start + PAGE_SIZE]
        if local_slots is None or freshness == 'unavailable':
            page_status = 'Save progress unavailable'
        elif blocker is not None:
            page_status = f'Locked: finish {blocker[1]} more on page {blocker[0]}'
        else:
            page_status = 'Unlocked in save'
        for loc in page:
            machines = (_normal_status(requirements_for(loc), inventory.owned_machines)
                        if inventory.machine_limits is None else
                        _quantity_status(budgets_for_location(loc), inventory.machine_limits))
            completion = ('Completed' if loc.code in checked else
                          'Sending' if loc.code in pending else 'Not completed')
            rows.append(ProgressRow(loc.code, loc.page_index + 1, loc.slot_index % PAGE_SIZE + 1,
                                    loc.name, loc.target, kinds[loc.kind], completion,
                                    page_status, machines))
        if local_slots is not None and blocker is None:
            needed = PAGE_UNLOCK_COUNT - sum(loc.slot_index in local_slots for loc in page)
            if needed > 0:
                blocker = (start // PAGE_SIZE + 1, needed)
    completed = sum(row.completion == 'Completed' for row in rows)
    prefix = {'current': '', 'last_known': 'Last known; reconnect to refresh. ',
              'unavailable': 'Save progress unavailable. '}[freshness]
    summary = prefix + f'{completed} of {len(rows)} campaign checks confirmed. Page access uses your local save, not tracker reachability.'
    return ProgressPresentation(tuple(rows), summary, freshness)
