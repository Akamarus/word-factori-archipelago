from __future__ import annotations

import argparse
import base64
import hashlib
import itertools
import json
from pathlib import Path
import string
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from word_factori.recipe_graph import (
    MACHINE_CAPABILITIES,
    RecipeGraph,
    physical_recipe_payload,
)


ALPHABET_LOGIC_VERSION = 1


def build_catalog(payload: Mapping[str, object]) -> dict[str, object]:
    graph = RecipeGraph.from_payload(physical_recipe_payload(payload))
    capabilities = tuple(sorted(set(MACHINE_CAPABILITIES.values())))
    subsets = tuple(
        frozenset(combination)
        for count in range(len(capabilities) + 1)
        for combination in itertools.combinations(capabilities, count)
    )
    reachable_by_subset = {owned: graph.reachable(owned) for owned in subsets}

    alphabet: dict[str, list[list[str]]] = {}
    for letter in string.ascii_uppercase:
        solutions = [owned for owned in subsets if letter in reachable_by_subset[owned]]
        minimal = [
            owned for owned in solutions
            if not any(other < owned for other in solutions)
        ]
        if not minimal:
            raise ValueError(f"letter {letter} is unreachable with all machine capabilities")
        alphabet[letter] = [sorted(option) for option in minimal]

    canonical = json.dumps(
        alphabet, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "version": ALPHABET_LOGIC_VERSION,
        "digest": hashlib.sha256(canonical).hexdigest(),
        "alphabet": alphabet,
    }


def _decode(path: Path) -> Mapping[str, object]:
    payload = json.loads(base64.b64decode(path.read_bytes()))
    if not isinstance(payload, dict):
        raise ValueError("decoded recipe payload is not an object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build minimal machine requirements for every letter"
    )
    parser.add_argument("recipe_path", type=Path)
    parser.add_argument(
        "output_path",
        type=Path,
        nargs="?",
        default=Path("word_factori/data/alphabet_requirements.json"),
    )
    args = parser.parse_args()
    catalog = build_catalog(_decode(args.recipe_path))
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
