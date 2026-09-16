"""Validated, immutable fixed-output factory witnesses for quantity logic."""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from importlib.resources import files
import json
from types import MappingProxyType
from collections.abc import Mapping

from .quantities import MODULE_FAMILIES, Vector, placed_counts
from .symbols import TARGET_SET, TARGET_TOKENS

Transition = tuple[str, tuple[str, ...], str]


@dataclass(frozen=True)
class Node:
    machine: str
    output: str
    inputs: tuple[int, ...]


@dataclass(frozen=True)
class FactoryGraph:
    nodes: tuple[Node, ...]
    roots: tuple[int, ...]


def _check_structure(graph: FactoryGraph) -> None:
    if not isinstance(graph, FactoryGraph) or not graph.nodes or not graph.roots:
        raise ValueError('factory must contain producers and target roots')
    for i, node in enumerate(graph.nodes):
        if not isinstance(node, Node) or not isinstance(node.output, str) or not node.output:
            raise ValueError('invalid producer')
        if not isinstance(node.inputs, tuple) or any(type(j) is not int or not 0 <= j < i for j in node.inputs):
            raise ValueError('producer inputs must reference earlier nodes')
        if node.machine == 'oIFactory':
            if node.inputs or node.output != 'I':
                raise ValueError('only actual I sources are permitted')
        else:
            if not isinstance(node.machine, str) or node.machine.removeprefix('o') not in MODULE_FAMILIES:
                raise ValueError('unsupported producer machine')
            arity = int(node.machine[-1]) if 'Merger' in node.machine else 1
            if len(node.inputs) != arity:
                raise ValueError('producer has incorrect arity')
    if any(type(root) is not int or not 0 <= root < len(graph.nodes) for root in graph.roots):
        raise ValueError('invalid target root')
    used = set(graph.roots)
    for i in reversed(range(len(graph.nodes))):
        if i in used:
            used.update(graph.nodes[i].inputs)
    if len(used) != len(graph.nodes):
        raise ValueError('factory contains producers disconnected from every target')


def validate_graph(graph: FactoryGraph, transitions: frozenset[Transition]) -> None:
    _check_structure(graph)
    for node in graph.nodes:
        if node.machine == 'oIFactory':
            continue
        key = (node.machine, tuple(sorted(graph.nodes[i].output for i in node.inputs)), node.output)
        if key not in transitions:
            raise ValueError(f'factory uses an unverified native transition: {key}')


def graph_budget(graph: FactoryGraph) -> Vector:
    _check_structure(graph)
    return placed_counts(node.machine for node in graph.nodes)


def merge_graphs(graphs: tuple[FactoryGraph, ...]) -> FactoryGraph:
    """Share identical processes, never merely equal output tokens. Keep root order."""
    nodes, roots, cache = [], [], {}
    for graph in graphs:
        _check_structure(graph)
        indices = {}
        for i, node in enumerate(graph.nodes):
            inputs = tuple(indices[j] for j in node.inputs)
            key = (node.machine, node.output, inputs)
            if key not in cache:
                cache[key] = len(nodes)
                nodes.append(Node(node.machine, node.output, inputs))
            indices[i] = cache[key]
        roots.extend(indices[i] for i in graph.roots)
    merged = FactoryGraph(tuple(nodes), tuple(roots))
    _check_structure(merged)
    return merged


def graph_from_payload(payload: object) -> FactoryGraph:
    if not isinstance(payload, dict) or set(payload) != {'nodes', 'roots'}:
        raise ValueError('factory payload must contain nodes and roots')
    if not isinstance(payload['nodes'], list) or not isinstance(payload['roots'], list):
        raise ValueError('factory nodes and roots must be arrays')
    nodes = []
    for node in payload['nodes']:
        if not isinstance(node, dict) or set(node) != {'machine', 'output', 'inputs'} or not isinstance(node['inputs'], list):
            raise ValueError('invalid producer payload')
        nodes.append(Node(node['machine'], node['output'], tuple(node['inputs'])))
    graph = FactoryGraph(tuple(nodes), tuple(payload['roots']))
    _check_structure(graph)
    return graph


def graph_payload(graph: FactoryGraph) -> dict:
    _check_structure(graph)
    return {'nodes': [{'machine': n.machine, 'output': n.output, 'inputs': list(n.inputs)}
                      for n in graph.nodes], 'roots': list(graph.roots)}


def payload_digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class QuantityCatalog:
    digest: str
    transitions: frozenset[Transition]
    recipes: Mapping[int, tuple[FactoryGraph, ...]]
    alphabet: Mapping[str, tuple[FactoryGraph, ...]]


def catalog_from_payload(raw: object) -> QuantityCatalog:
    from .recipe_checks import RECIPE_CHECKS
    expected = {'schema', 'digest', 'provenance', 'transitions', 'recipes', 'alphabet'}
    if not isinstance(raw, dict) or set(raw) != expected or type(raw['schema']) is not int or raw['schema'] != 2:
        raise ValueError('unsupported quantity catalog')
    if raw['digest'] != payload_digest({k: v for k, v in raw.items() if k != 'digest'}):
        raise ValueError('quantity catalog digest mismatch')
    try:
        transitions = frozenset((m, tuple(sorted(inputs)), out) for m, inputs, out in raw['transitions'])
        if not isinstance(raw['recipes'], dict) or set(raw['recipes']) != {str(c.code) for c in RECIPE_CHECKS}:
            raise ValueError('quantity recipe identities do not match the AP catalog')
        if not isinstance(raw['alphabet'], dict) or set(raw['alphabet']) != TARGET_SET:
            raise ValueError('quantity alphabet must contain every supported target character')
        def decode(alternatives):
            if not isinstance(alternatives, list) or not alternatives:
                raise ValueError('missing constructive alternatives')
            result = tuple(graph_from_payload(p) for p in alternatives)
            for graph in result:
                validate_graph(graph, transitions)
                if len(graph.roots) != 1:
                    raise ValueError('catalog recipe must have one root')
            return result
        recipes = {int(code): decode(value) for code, value in raw['recipes'].items()}
        alphabet = {letter: decode(value) for letter, value in raw['alphabet'].items()}
        for check in RECIPE_CHECKS:
            for graph in recipes[check.code]:
                root = graph.nodes[graph.roots[0]]
                actual = (root.machine, tuple(sorted(graph.nodes[i].output for i in root.inputs)), root.output)
                if actual != (check.machine, tuple(check.inputs), check.output):
                    raise ValueError('quantity recipe root does not match its AP identity')
        for letter, graphs in alphabet.items():
            if any(graph.nodes[graph.roots[0]].output != TARGET_TOKENS[letter] for graph in graphs):
                raise ValueError('quantity alphabet output mismatch')
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('malformed quantity catalog') from error
    return QuantityCatalog(raw['digest'], transitions, MappingProxyType(recipes), MappingProxyType(alphabet))


@lru_cache(maxsize=1)
def load_catalog() -> QuantityCatalog:
    return catalog_from_payload(json.loads(files(__package__).joinpath('data/quantity_recipes.json').read_text(encoding='utf-8')))
