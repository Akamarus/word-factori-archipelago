"""Conservative complete-factory candidates; never claim exhaustive trade-offs."""
from collections import Counter
from functools import lru_cache

from .quantities import FAMILIES, MODULE_FAMILIES, checked_vector
from .quantity_graphs import FactoryGraph, graph_budget, load_catalog, merge_graphs
from .symbols import TARGET_SET

MAX_CANDIDATES = 256


def _fits(graph, module_limits, allowed_families):
    counts = Counter(n.machine.removeprefix('o') for n in graph.nodes)
    if any(counts[name] > limit for name, limit in module_limits):
        return False
    return allowed_families is None or all(
        not count or family in allowed_families
        for family, count in zip(FAMILIES, graph_budget(graph))
    )


def _ranked_candidates(graphs):
    # Keep shape diversity for later sharing, not only one graph per budget.
    unique = dict.fromkeys(graphs)
    costs = {graph: graph_budget(graph) for graph in unique}
    keys = {graph: repr(graph) for graph in unique}
    ranked = sorted(unique, key=lambda g: (sum(costs[g]), costs[g], keys[g]))
    if len(ranked) <= MAX_CANDIDATES:
        return tuple(ranked)
    selected = dict.fromkeys(ranked[:MAX_CANDIDATES // 2])
    for axis in range(6):
        weighted = sorted(ranked, key=lambda g: (costs[g][axis], sum(costs[g]), keys[g]))
        for graph in weighted[:MAX_CANDIDATES // 12]:
            selected[graph] = None
    return tuple(selected)


@lru_cache(maxsize=256)
def graphs_for_word(word: str, module_limits: tuple[tuple[str,int], ...] = (),
                    allowed_families: frozenset[str] | None = None) -> tuple[FactoryGraph, ...]:
    if not isinstance(word, str) or not 1 <= len(word) <= 12 or any(c not in TARGET_SET for c in word):
        raise ValueError('quantity word must be 1–12 supported uppercase letters or symbols')
    if any(name not in MODULE_FAMILIES and name != 'IFactory' or type(n) is not int or n < 0
           for name, n in module_limits):
        raise ValueError('invalid native module restriction')
    if allowed_families is not None and not allowed_families <= set(FAMILIES):
        raise ValueError('unknown allowed machine family')
    catalog = load_catalog()
    unique_letters = tuple(dict.fromkeys(word))
    candidates = ()
    for letter in unique_letters:
        choices = tuple(g for g in catalog.alphabet[letter] if _fits(g, module_limits, allowed_families))
        if not choices:
            return ()
        if not candidates:
            candidates = choices
        else:
            merged = (merge_graphs((left,right)) for left in candidates for right in choices)
            candidates = _ranked_candidates(g for g in merged if _fits(g, module_limits, allowed_families))
        if not candidates:
            return ()
    return tuple(FactoryGraph(g.nodes, tuple(g.roots[unique_letters.index(c)] for c in word)) for g in candidates)


def pareto_budgets(graphs) -> tuple[tuple[int,...], ...]:
    budgets = sorted(set(graph_budget(g) for g in graphs), key=lambda b: (sum(b), b))
    frontier = []
    for budget in budgets:
        checked_vector(budget)
        if not any(all(a <= b for a,b in zip(other,budget)) for other in frontier):
            frontier.append(budget)
    return tuple(frontier)


def budgets_for_word(word, module_limits=(), allowed_families=None):
    return pareto_budgets(graphs_for_word(word, module_limits, allowed_families))


def graphs_for_location(location):
    families = (frozenset(item.removesuffix(' Access') for item in location.required_route)
                if location.kind == 'discovery' else None)
    return graphs_for_word(location.target, location.module_limits, families)


@lru_cache(maxsize=256)
def budgets_for_location(location):
    return pareto_budgets(graphs_for_location(location))
