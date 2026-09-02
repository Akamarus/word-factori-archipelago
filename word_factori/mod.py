from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .campaign import CampaignManifest, campaign_digest
from .data import CAMPAIGN_DIGEST, CAMPAIGN_ID, CAMPAIGN_VERSION, LOCATIONS, LocationData
from .layout import CampaignLayout, validate_layout

MODULES = {
    "Bender Access": ("Bend",), "Rotation Access": ("Rotate_cw", "Rotate_ccw"),
    "Reflection Access": ("Reflect_hor", "Reflect_vert"), "Merger2 Access": ("Merger2",),
    "Merger3 Access": ("Merger3",), "Merger4 Access": ("Merger4",),
}
def render_levels(
    owned: set[str], world_access: int, *, locations: tuple[LocationData, ...] = LOCATIONS,
) -> list[dict]:
    levels = []
    for location in locations:
        limits = dict(location.module_limits)
        for item, modules in MODULES.items():
            if item not in owned:
                limits.update({module: 0 for module in modules})
            if location.kind == "discovery" and item not in location.required_route:
                limits.update({module: 0 for module in modules})
        if world_access < location.world_tier:
            limits["IFactory"] = 0
        levels.append({"text": location.target, "module_counts": dict(sorted(limits.items()))})
    return levels


def write_levels(path: Path, levels: list[dict]) -> None:
    _write_json(path, levels)


def write_campaign_identity(
    path: Path, manifest: CampaignManifest | None = None,
    layout: CampaignLayout | None = None,
) -> None:
    campaign_id = CAMPAIGN_ID if manifest is None else manifest.campaign_id
    version = CAMPAIGN_VERSION if manifest is None else manifest.version
    digest = CAMPAIGN_DIGEST if manifest is None else campaign_digest(manifest)
    level_count = len(LOCATIONS) if manifest is None else len(manifest.levels)
    payload = {
        "campaign_id": campaign_id,
        "manifest_version": version,
        "manifest_digest": digest,
        "level_count": level_count,
    }
    if layout is not None:
        if manifest is None:
            raise ValueError("layout identity requires a campaign manifest")
        validate_layout(manifest, layout)
        payload.update({
            "manifest_digest": layout.digest,
            "layout_digest": layout.digest,
            "base_manifest_digest": campaign_digest(manifest),
            "progression_model": layout.progression_model,
            "layout_algorithm": layout.algorithm,
            "page_size": layout.page_size,
            "page_unlock_count": layout.page_unlock_count,
        })
    _write_json(path, payload)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
