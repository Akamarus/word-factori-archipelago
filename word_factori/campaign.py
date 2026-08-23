from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.resources import files
import json
from typing import Any


MACHINE_ITEMS = frozenset({
    "Bender Access",
    "Rotation Access",
    "Reflection Access",
    "Merger2 Access",
    "Merger3 Access",
    "Merger4 Access",
})
REGIONS = frozenset({
    "Starter Workshop",
    "Short Word Bench",
    "Main Factory",
    "Advanced Factory",
    "Challenge Board",
    "Final Contract",
})
KINDS = frozenset({"word", "challenge", "final", "discovery"})
MODULE_NAMES = frozenset({
    "IFactory",
    "Bend",
    "Rotate_cw",
    "Rotate_ccw",
    "Reflect_hor",
    "Reflect_vert",
    "Merger2",
    "Merger3",
    "Merger4",
})


@dataclass(frozen=True)
class CampaignRecord:
    stable_key: str
    index: int
    name: str
    target: str
    region: str
    world_tier: int
    kind: str
    required_route: frozenset[str] = frozenset()
    requirement_options: tuple[frozenset[str], ...] = ()
    module_limits: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class CampaignManifest:
    campaign_id: str
    version: str
    levels: tuple[CampaignRecord, ...]


def _record_from_payload(payload: dict[str, Any]) -> CampaignRecord:
    return CampaignRecord(
        stable_key=str(payload["stable_key"]),
        index=int(payload["index"]),
        name=str(payload["name"]),
        target=str(payload["target"]),
        region=str(payload["region"]),
        world_tier=int(payload["world_tier"]),
        kind=str(payload["kind"]),
        required_route=frozenset(map(str, payload.get("required_route", ()))),
        requirement_options=tuple(
            frozenset(map(str, option)) for option in payload.get("requirement_options", ())
        ),
        module_limits=tuple(
            sorted((str(name), int(count)) for name, count in payload.get("module_limits", {}).items())
        ),
    )


def manifest_from_payload(payload: dict[str, Any]) -> CampaignManifest:
    levels = payload.get("levels")
    if not isinstance(levels, list):
        raise ValueError("campaign levels must be an array")
    manifest = CampaignManifest(
        campaign_id=str(payload.get("campaign_id", "")),
        version=str(payload.get("version", "")),
        levels=tuple(_record_from_payload(record) for record in levels),
    )
    validate_campaign(manifest)
    return manifest


def validate_campaign(manifest: CampaignManifest) -> None:
    if not manifest.campaign_id or not manifest.version:
        raise ValueError("campaign identity and version are required")
    indices = [record.index for record in manifest.levels]
    if indices != list(range(len(manifest.levels))):
        raise ValueError("campaign indices must be contiguous from zero")
    if len({record.stable_key for record in manifest.levels}) != len(manifest.levels):
        raise ValueError("campaign stable keys must be unique")
    if len({record.name for record in manifest.levels}) != len(manifest.levels):
        raise ValueError("campaign location names must be unique")
    for record in manifest.levels:
        if record.kind not in KINDS or record.region not in REGIONS:
            raise ValueError(f"invalid campaign record {record.stable_key}")
        if not 0 <= record.world_tier <= 5:
            raise ValueError(f"invalid world tier for {record.stable_key}")
        if record.kind == "discovery" and not record.required_route:
            raise ValueError(f"discovery route is empty for {record.stable_key}")
        if record.kind in {"word", "final"} and not record.requirement_options:
            raise ValueError(f"recipe requirements are empty for {record.stable_key}")
        if not record.required_route <= MACHINE_ITEMS:
            raise ValueError(f"unsupported route item for {record.stable_key}")
        if any(not option <= MACHINE_ITEMS for option in record.requirement_options):
            raise ValueError(f"unsupported requirement item for {record.stable_key}")
        limits = dict(record.module_limits)
        if not set(limits) <= MODULE_NAMES or any(count < 0 for count in limits.values()):
            raise ValueError(f"invalid module limit for {record.stable_key}")


def manifest_to_payload(manifest: CampaignManifest) -> dict[str, Any]:
    levels: list[dict[str, Any]] = []
    for record in manifest.levels:
        payload: dict[str, Any] = {
            "stable_key": record.stable_key,
            "index": record.index,
            "name": record.name,
            "target": record.target,
            "region": record.region,
            "world_tier": record.world_tier,
            "kind": record.kind,
        }
        if record.required_route:
            payload["required_route"] = sorted(record.required_route)
        if record.requirement_options:
            payload["requirement_options"] = [sorted(option) for option in record.requirement_options]
        if record.module_limits:
            payload["module_limits"] = dict(record.module_limits)
        levels.append(payload)
    return {"campaign_id": manifest.campaign_id, "version": manifest.version, "levels": levels}


def campaign_digest(manifest: CampaignManifest) -> str:
    encoded = json.dumps(
        manifest_to_payload(manifest), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_campaign() -> CampaignManifest:
    payload = json.loads(files(__package__).joinpath("campaign.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("campaign root must be an object")
    return manifest_from_payload(payload)


def _load_pack_catalog() -> dict[str, Any]:
    payload = json.loads(files(__package__).joinpath("campaign_packs.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("catalog_version") != 1:
        raise ValueError("campaign level set catalog is invalid")
    sets = payload.get("sets")
    packs = payload.get("packs")
    if not isinstance(sets, dict) or not isinstance(packs, dict):
        raise ValueError("campaign level set catalog is invalid")
    return payload


def available_level_sets() -> tuple[str, ...]:
    catalog = _load_pack_catalog()
    return tuple(str(key) for key in catalog["sets"])


def campaign_for_level_set(level_set: str) -> CampaignManifest:
    """Assemble one curated set from bundled stable keys only."""
    if not isinstance(level_set, str):
        raise ValueError("campaign level set is invalid")
    catalog = _load_pack_catalog()
    definition = catalog["sets"].get(level_set)
    if not isinstance(definition, dict):
        raise ValueError(f"unknown campaign level set: {level_set}")
    pack_names = definition.get("packs")
    if not isinstance(pack_names, list) or not pack_names:
        raise ValueError("campaign level set has no curated packs")
    stable_keys: list[str] = []
    for pack_name in pack_names:
        pack = catalog["packs"].get(pack_name)
        if not isinstance(pack, dict) or not isinstance(pack.get("stable_keys"), list):
            raise ValueError("campaign level set references an invalid pack")
        stable_keys.extend(str(key) for key in pack["stable_keys"])
    if len(stable_keys) != len(set(stable_keys)):
        raise ValueError("campaign level set repeats stable keys")
    source = load_campaign()
    records = {record.stable_key: record for record in source.levels}
    if any(key not in records for key in stable_keys):
        raise ValueError("campaign level set references an unknown stable key")
    levels = tuple(records[key] for key in stable_keys)
    if [record.index for record in levels] != list(range(len(levels))):
        raise ValueError("campaign level set must preserve native sequential order")
    manifest = CampaignManifest(
        campaign_id=str(definition.get("campaign_id", "")),
        version=str(definition.get("manifest_version", "")),
        levels=levels,
    )
    validate_campaign(manifest)
    return manifest
