from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from word_factori.campaign import (
    CampaignManifest,
    load_campaign,
    manifest_to_payload,
)
from word_factori.data import MACHINE_ITEMS
from word_factori.recipe_graph import RecipeGraph, minimal_capability_sets


def derive(recipe_path: Path) -> dict[str, list[list[str]]]:
    graph = RecipeGraph.from_encoded_file(recipe_path)
    manifest = load_campaign()
    validate_discovery_routes(graph, manifest)
    requirements = {}
    targets = dict.fromkeys(
        record.target for record in manifest.levels if record.kind in {"word", "final"}
    )
    for target in targets:
        minima = minimal_capability_sets(graph, target, MACHINE_ITEMS)
        if not minima:
            raise ValueError(f"no reachable capability set for {target}")
        requirements[target] = [sorted(requirement) for requirement in minima]
    return requirements


def validate_discovery_routes(graph: RecipeGraph, manifest: CampaignManifest) -> None:
    for record in manifest.levels:
        if record.kind != "discovery":
            continue
        reachable = graph.reachable(record.required_route)
        if not all(symbol in reachable for symbol in set(record.target)):
            raise ValueError(f"discovery route cannot produce {record.stable_key}")


def refresh_manifest_requirements(
    manifest: CampaignManifest,
    derived: dict[str, list[list[str]]],
) -> CampaignManifest:
    levels = []
    for record in manifest.levels:
        if record.kind in {"word", "final"}:
            options = derived.get(record.target)
            if not options:
                raise ValueError(f"no derived requirements for {record.stable_key}")
            record = replace(
                record,
                requirement_options=tuple(frozenset(option) for option in options),
            )
        levels.append(record)
    return replace(manifest, levels=tuple(levels))


def write_manifest(path: Path, manifest: CampaignManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(manifest_to_payload(manifest), stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh capability-only Word Factori reachability without exporting recipes.")
    parser.add_argument("recipe_path", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()
    result = derive(args.recipe_path)
    manifest = refresh_manifest_requirements(load_campaign(), result)
    write_manifest(args.output_path, manifest)
    print(f"Derived {len(result)} targets and validated 10 Discovery Labs into {args.output_path}")


if __name__ == "__main__":
    main()
