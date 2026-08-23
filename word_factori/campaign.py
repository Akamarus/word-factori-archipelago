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
