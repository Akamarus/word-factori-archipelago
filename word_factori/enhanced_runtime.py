"""Room-bound, atomic native machine snapshots. Never reads or writes game saves."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time

from .mod import MODULES, _write_json

ORIGINAL_SHA256 = "d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978"
PATCH_PROTOCOL = "enhanced_v1"
PATCHED_SHA256 = "5a964d5155f8f7acc63fd90bc81882a0559c4586f5de4fd9a0657badd8594194"
RUNTIME_NAME = "archipelago_runtime.json"
RECEIPT_NAME = "archipelago_enhanced_install.json"
ALLOWED_MODULES = frozenset(module for modules in MODULES.values() for module in modules) | {"IFactory"}


def valid_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def patch_ready(mod_folder: Path) -> bool:
    """A stale receipt cannot enable an unpatched or subsequently updated game."""
    try:
        receipt = json.loads((mod_folder / RECEIPT_NAME).read_text(encoding="utf-8"))
        if receipt["protocol"] != PATCH_PROTOCOL or receipt["original_sha256"] != ORIGINAL_SHA256:
            return False
        if receipt["patched_sha256"] != PATCHED_SHA256:
            return False
        path = Path(receipt["game_data"])
        if not path.is_absolute() or path.name.lower() != "data.win":
            return False
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest() == receipt["patched_sha256"]
    except (OSError, ValueError, TypeError, KeyError):
        return False


def publish_runtime(path: Path, room: str, layout: str, levels: list[dict]) -> bool:
    if not valid_digest(room) or not valid_digest(layout):
        raise ValueError("Enhanced runtime requires complete room and layout identities")
    if not isinstance(levels, list) or not levels:
        raise ValueError("Enhanced runtime requires levels")
    for entry in levels:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str) or not isinstance(entry.get("module_counts"), dict):
            raise ValueError("Invalid runtime level")
        for name, count in entry["module_counts"].items():
            if name not in ALLOWED_MODULES or type(count) is not int or not 0 <= count <= 10000:
                raise ValueError("Invalid runtime machine limit")
    payload = {"schema": 1, "mode": "enhanced", "room": room, "layout": layout, "levels": levels}
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        revision = previous.get("revision") if isinstance(previous, dict) else None
        if type(revision) is not int or not 0 <= revision < 2**53 - 1:
            previous, revision = {}, 0
    except (OSError, ValueError, TypeError):
        previous, revision = {}, 0
    if previous == {**payload, "revision": revision}:
        return False
    # Millisecond epoch also recovers after a lost/corrupt sidecar; persisted
    # revision orders rapid updates and clock rollback across reconnects.
    payload["revision"] = max(time.time_ns() // 1_000_000, revision + 1)
    _write_json(path, payload)
    return True
