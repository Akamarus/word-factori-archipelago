from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Mapping

from .recipe_graph import MACHINE_CAPABILITIES


_MACHINE_NAMES = {
    "oBend": "Bender",
    "oMerger2": "Merger2",
    "oMerger3": "Merger3",
    "oMerger4": "Merger4",
}
_MACHINE_ARITIES = {"oBend": 1, "oMerger2": 2, "oMerger3": 3, "oMerger4": 4}
_CANONICAL_TOKEN = re.compile(r"\S(?:[123]|[0-3]1)?").fullmatch


def _recipe_name(machine: str, inputs: tuple[str, ...], output: str) -> str:
    return f"{_MACHINE_NAMES[machine]}: [{', '.join(inputs)}] -> {output}"


@dataclass(frozen=True)
class RecipeCheck:
    code: int
    name: str
    machine: str
    inputs: tuple[str, ...]
    output: str
    requirement_options: tuple[frozenset[str], ...]


def _load_catalog() -> tuple[tuple[RecipeCheck, ...], str]:
    raw = files(__package__).joinpath("letter_recipes.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {"digest", "recipes"}:
        raise ValueError("recipe catalog must contain only digest and recipes")
    digest, recipes = payload["digest"], payload["recipes"]
    if not isinstance(digest, str) or not isinstance(recipes, list):
        raise ValueError("recipe catalog digest or recipe list is malformed")
    canonical = json.dumps(recipes, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != digest:
        raise ValueError("recipe catalog digest does not match its contents")

    checks: list[RecipeCheck] = []
    hidden_count = 0
    for item in recipes:
        if not isinstance(item, dict) or set(item) != {"code", "name", "machine", "inputs", "output", "hidden", "requirements"}:
            raise ValueError("recipe catalog entry has an invalid shape")
        code, name, machine = item["code"], item["name"], item["machine"]
        inputs, output, hidden, requirements = item["inputs"], item["output"], item["hidden"], item["requirements"]
        if not isinstance(code, int) or code < 975302000 or not isinstance(name, str) or not name:
            raise ValueError("recipe catalog code or name is invalid")
        if machine not in _MACHINE_NAMES:
            raise ValueError("recipe catalog machine is invalid")
        if (
            not isinstance(inputs, list)
            or len(inputs) != _MACHINE_ARITIES[machine]
            or not all(isinstance(token, str) and _CANONICAL_TOKEN(token) is not None for token in inputs)
            or inputs != sorted(inputs)
        ):
            raise ValueError("recipe catalog inputs are invalid")
        if not isinstance(output, str) or len(output) != 1 or not ("A" <= output <= "Z") or not isinstance(hidden, bool):
            raise ValueError("recipe catalog output or visibility is invalid")
        input_tuple = tuple(inputs)
        if name != _recipe_name(machine, input_tuple, output):
            raise ValueError("recipe catalog name does not match its identity")
        if not isinstance(requirements, list) or not requirements:
            raise ValueError("recipe catalog requirements are invalid")
        options: list[frozenset[str]] = []
        for option in requirements:
            if not isinstance(option, list) or not option or not all(isinstance(value, str) for value in option):
                raise ValueError("recipe catalog requirement option is invalid")
            frozen = frozenset(option)
            if len(frozen) != len(option) or not frozen <= frozenset(MACHINE_CAPABILITIES.values()):
                raise ValueError("recipe catalog requirement option contains invalid capabilities")
            if MACHINE_CAPABILITIES[machine] not in frozen:
                raise ValueError("recipe catalog requirement omits its own machine")
            options.append(frozen)
        if any(left < right for left in options for right in options):
            raise ValueError("recipe catalog requirements contain a non-minimal option")
        checks.append(RecipeCheck(code, name, machine, input_tuple, output, tuple(options)))
        hidden_count += hidden

    expected_counts = {"oBend": 24, "oMerger2": 86, "oMerger3": 58, "oMerger4": 19}
    actual_counts = {machine: sum(check.machine == machine for check in checks) for machine in expected_counts}
    if len(checks) != 187 or actual_counts != expected_counts or hidden_count != 119:
        raise ValueError("recipe catalog does not match the expected letter recipe inventory")
    if len({check.code for check in checks}) != len(checks) or len({check.name for check in checks}) != len(checks):
        raise ValueError("recipe catalog contains duplicate codes or names")
    if len({(check.machine, check.inputs, check.output) for check in checks}) != len(checks):
        raise ValueError("recipe catalog contains duplicate recipe identities")
    if len({(check.machine, " ".join(check.inputs), check.output) for check in checks}) != len(checks):
        raise ValueError("recipe catalog contains duplicate observation keys")
    return tuple(checks), digest


RECIPE_CHECKS, RECIPE_CATALOG_DIGEST = _load_catalog()
_CHECK_BY_OBSERVATION = {(check.machine, " ".join(check.inputs), check.output): check.code for check in RECIPE_CHECKS}


def discovered_recipe_codes(journal: object) -> frozenset[int]:
    if not isinstance(journal, Mapping):
        raise ValueError("recipe journal must be an object")
    found: set[int] = set()
    recognized = {check.machine for check in RECIPE_CHECKS}
    for machine, observations in journal.items():
        if machine not in recognized:
            continue
        if not isinstance(observations, Mapping):
            raise ValueError(f"recognized recipe journal group {machine} must be an object")
        for raw_inputs, raw_output in observations.items():
            if not isinstance(raw_inputs, str) or not isinstance(raw_output, str):
                raise ValueError(f"recognized recipe journal group {machine} contains a malformed observation")
            code = _CHECK_BY_OBSERVATION.get((machine, raw_inputs, raw_output))
            if code is not None:
                found.add(code)
    return frozenset(found)
