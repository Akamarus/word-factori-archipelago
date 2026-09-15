from __future__ import annotations

import argparse
import base64
import hashlib
import itertools
import json
from pathlib import Path
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from word_factori.recipe_graph import (
    MACHINE_ARITIES,
    MACHINE_CAPABILITIES,
    RecipeGraph,
    physical_recipe_payload,
)


FIRST_RECIPE_CODE = 975302000
CATALOG_MACHINES = ("oBend", "oMerger2", "oMerger3", "oMerger4")
MACHINE_NAMES = {
    "oBend": "Bender",
    "oMerger2": "Merger2",
    "oMerger3": "Merger3",
    "oMerger4": "Merger4",
}


def _identity(item: Mapping[str, object]) -> tuple[str, tuple[str, ...], str]:
    return str(item["machine"]), tuple(str(value) for value in item["inputs"]), str(item["output"])


def _existing_ids(output_path: Path) -> dict[tuple[str, tuple[str, ...], str], int]:
    if not output_path.is_file():
        return {}
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    recipes = payload.get("recipes", ()) if isinstance(payload, dict) else ()
    if not isinstance(recipes, list):
        raise ValueError("existing recipe catalog has no recipe list")
    result: dict[tuple[str, tuple[str, ...], str], int] = {}
    for item in recipes:
        if not isinstance(item, dict) or not isinstance(item.get("code"), int):
            raise ValueError("existing recipe catalog contains a malformed recipe")
        identity = _identity(item)
        if identity in result or item["code"] in result.values():
            raise ValueError("existing recipe catalog contains duplicate identities or codes")
        result[identity] = item["code"]
    return result


def _native_token(token: str, payload: Mapping[str, object]) -> str:
    aliases = payload.get("aliases", {})
    if isinstance(aliases, dict):
        inverse_aliases = {str(value): str(key) for key, value in aliases.items()}
        token = inverse_aliases.get(token, token)
    digits = "".join(character for character in token[1:] if character.isdigit())
    codes = [0, 0, 0]
    for index, digit in enumerate(digits):
        if index >= len(codes):
            raise ValueError(f"recipe token has too many orientation digits: {token}")
        codes[index] = int(digit)
    character = token.replace(digits, "") if digits else token
    rotate4 = payload.get("rotate4_symmetries", ())
    rotate2 = payload.get("rotate2_symmetries", ())
    horizontal = payload.get("horizontal_symmetries", ())
    vertical = payload.get("vertical_symmetries", ())
    modulus = 1 if character in rotate4 else 2 if character in rotate2 else 4
    rotation, horizontally_reflected, vertically_reflected = codes
    if character in horizontal:
        horizontally_reflected = 0
    if character in vertical and horizontally_reflected:
        rotation += 2
        horizontally_reflected = 0
    rotation %= modulus
    canonical = f"{character}{rotation}{horizontally_reflected}{vertically_reflected}"
    while len(canonical) > 1 and canonical.endswith("0"):
        canonical = canonical[:-1]
    return canonical


def build_catalog(payload: Mapping[str, object], output_path: Path) -> dict[str, object]:
    graph = RecipeGraph.from_payload(physical_recipe_payload(payload))
    capabilities = tuple(sorted(set(MACHINE_CAPABILITIES.values())))
    subsets = tuple(
        frozenset(combination)
        for count in range(len(capabilities) + 1)
        for combination in itertools.combinations(capabilities, count)
    )
    reachable_by_subset = {owned: graph.reachable(owned) for owned in subsets}

    recipes: list[dict[str, object]] = []
    for machine in CATALOG_MACHINES:
        machine_recipes = payload.get(machine, {})
        if not isinstance(machine_recipes, dict):
            raise ValueError(f"{machine} recipe group is not an object")
        capability = MACHINE_CAPABILITIES[machine]
        for raw_inputs, raw_output in machine_recipes.items():
            cleaned_output = str(raw_output).removeprefix("__")
            if len(cleaned_output) != 1 or not ("A" <= cleaned_output <= "Z"):
                continue
            inputs = tuple(sorted(_native_token(token, payload) for token in str(raw_inputs).split()))
            if len(inputs) != MACHINE_ARITIES[machine]:
                continue
            solutions = [
                owned
                for owned in subsets
                if capability in owned and all(token in reachable_by_subset[owned] for token in inputs)
            ]
            minimal = [owned for owned in solutions if not any(other < owned for other in solutions)]
            recipes.append({
                "machine": machine,
                "inputs": list(inputs),
                "output": cleaned_output,
                "hidden": str(raw_output).startswith("__"),
                "requirements": [sorted(option) for option in minimal],
            })

    recipes.sort(key=lambda item: _identity(item))
    old_ids = _existing_ids(output_path)
    next_code = max((FIRST_RECIPE_CODE - 1, *old_ids.values())) + 1
    for item in recipes:
        identity = _identity(item)
        if identity in old_ids:
            item["code"] = old_ids[identity]
        else:
            item["code"] = next_code
            next_code += 1
        tokens = ", ".join(item["inputs"])
        item["name"] = f"{MACHINE_NAMES[str(item['machine'])]}: [{tokens}] -> {item['output']}"

    canonical = json.dumps(recipes, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"digest": hashlib.sha256(canonical).hexdigest(), "recipes": recipes}


def _decode(path: Path) -> Mapping[str, object]:
    payload = json.loads(base64.b64decode(path.read_bytes()))
    if not isinstance(payload, dict):
        raise ValueError("decoded recipe payload is not an object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the packaged letter recipe catalog")
    parser.add_argument("recipe_path", type=Path)
    parser.add_argument("output_path", type=Path, nargs="?", default=Path("word_factori/letter_recipes.json"))
    args = parser.parse_args()
    catalog = build_catalog(_decode(args.recipe_path), args.output_path)
    args.output_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
