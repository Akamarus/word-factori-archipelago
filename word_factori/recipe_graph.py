from __future__ import annotations

import base64
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


MACHINE_CAPABILITIES = {
    "oBend": "Bender Access",
    "oRotate_cw": "Rotation Access",
    "oRotate_ccw": "Rotation Access",
    "oReflect_hor": "Reflection Access",
    "oReflect_vert": "Reflection Access",
    "oMerger2": "Merger2 Access",
    "oMerger3": "Merger3 Access",
    "oMerger4": "Merger4 Access",
}
ORIENTATION_SUFFIXES = {
    (0, False): "", (1, False): "1", (2, False): "2", (3, False): "3",
    (0, True): "01", (1, True): "11", (2, True): "21", (3, True): "31",
}


@dataclass(frozen=True)
class RecipeEdge:
    output: str
    inputs: tuple[str, ...]
    capability: str


class RecipeGraph:
    def __init__(
        self,
        initial: Iterable[str],
        edges: Iterable[RecipeEdge],
        bases: Iterable[str],
        aliases: Mapping[str, str] | None = None,
        zero_cost_variants: Mapping[str, Iterable[str]] | None = None,
    ):
        self.initial = frozenset(initial)
        self.edges = tuple(edges)
        self.bases = tuple(sorted(set(bases), key=len, reverse=True))
        self.aliases = dict(aliases or {})
        self.zero_cost_variants = {key: frozenset(value) for key, value in (zero_cost_variants or {}).items()}

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "RecipeGraph":
        factory = payload.get("oIFactory", {})
        initial = {
            _clean_output(output)
            for output in factory.values()
        } if isinstance(factory, dict) else {"I"}
        edges: list[RecipeEdge] = []
        bases = set(initial)
        for machine, capability in MACHINE_CAPABILITIES.items():
            recipes = payload.get(machine, {})
            if not isinstance(recipes, dict):
                continue
            for raw_inputs, raw_output in recipes.items():
                output = _clean_output(raw_output)
                edges.append(RecipeEdge(output, tuple(str(raw_inputs).split()), capability))
                if machine not in {"oRotate_cw", "oRotate_ccw", "oReflect_hor", "oReflect_vert"}:
                    bases.add(output)

        zero_cost: dict[str, set[str]] = {}
        symmetry_suffixes = {
            "horizontal_symmetries": ("01",),
            "vertical_symmetries": ("21",),
            "rotate2_symmetries": ("2",),
            "rotate4_symmetries": ("1", "2", "3"),
        }
        for field, suffixes in symmetry_suffixes.items():
            values = payload.get(field, ())
            if isinstance(values, list):
                for base in values:
                    bases.add(str(base))
                    zero_cost.setdefault(str(base), set()).update(f"{base}{suffix}" for suffix in suffixes)
        aliases = payload.get("aliases", {})
        return cls(initial, edges, bases, aliases if isinstance(aliases, dict) else {}, zero_cost)

    @classmethod
    def from_encoded_file(cls, path: Path) -> "RecipeGraph":
        payload = json.loads(base64.b64decode(path.read_bytes()))
        if not isinstance(payload, dict):
            raise ValueError("decoded recipe payload is not an object")
        return cls.from_payload(payload)

    def reachable(self, capabilities: Iterable[str]) -> frozenset[str]:
        capabilities = frozenset(capabilities)
        known = set(self.initial)
        while True:
            expanded = set(known)
            for token in known:
                expanded.update(self.zero_cost_variants.get(token, ()))
                parsed = self._parse_orientation(token)
                if parsed is not None:
                    base, rotation, mirrored = parsed
                    if "Rotation Access" in capabilities:
                        expanded.add(_oriented(base, rotation + 1, mirrored))
                        expanded.add(_oriented(base, rotation - 1, mirrored))
                    if "Reflection Access" in capabilities:
                        expanded.add(_oriented(base, rotation, not mirrored))
                        expanded.add(_oriented(base, rotation + 2, not mirrored))
            for alias, canonical in self.aliases.items():
                if alias in known or canonical in known:
                    expanded.update((alias, canonical))
            for edge in self.edges:
                if edge.capability in capabilities and all(value in known for value in edge.inputs):
                    expanded.add(edge.output)
            if expanded == known:
                return frozenset(known)
            known = expanded

    def _parse_orientation(self, token: str) -> tuple[str, int, bool] | None:
        for base in self.bases:
            if not token.startswith(base):
                continue
            suffix = token[len(base):]
            for orientation, encoded in ORIENTATION_SUFFIXES.items():
                if suffix == encoded:
                    return base, orientation[0], orientation[1]
        return None


def _clean_output(output: object) -> str:
    return str(output).removeprefix("__")


def _oriented(base: str, rotation: int, mirrored: bool) -> str:
    return f"{base}{ORIENTATION_SUFFIXES[(rotation % 4, mirrored)]}"


def minimal_capability_sets(
    graph: RecipeGraph,
    target: str,
    capabilities: Iterable[str],
) -> tuple[frozenset[str], ...]:
    ordered = tuple(sorted(set(capabilities)))
    minima: list[frozenset[str]] = []
    for count in range(len(ordered) + 1):
        for combination in itertools.combinations(ordered, count):
            candidate = frozenset(combination)
            if any(existing <= candidate for existing in minima):
                continue
            if all(symbol in graph.reachable(candidate) for symbol in set(target)):
                minima.append(candidate)
    return tuple(minima)
