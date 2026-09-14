"""Room-bound, atomic native machine snapshots. Never reads or writes game saves."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import re
import time

from .mod import MODULES, _write_json
from .platform_paths import InstallationPaths

ORIGINAL_SHA256 = "d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978"
PATCH_PROTOCOL = "enhanced_v1"
PATCHED_SHA256 = "5a964d5155f8f7acc63fd90bc81882a0559c4586f5de4fd9a0657badd8594194"
RUNTIME_NAME = "archipelago_runtime.json"
RECEIPT_NAME = "archipelago_enhanced_install.json"
ALLOWED_MODULES = frozenset(module for modules in MODULES.values() for module in modules) | {"IFactory"}


def valid_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


@dataclass(frozen=True)
class PatchReadiness:
    ready: bool
    code: str
    message: str


def patch_readiness(mod_folder: Path, installation: InstallationPaths | None = None) -> PatchReadiness:
    """Explain why a receipt cannot authorize this exact game installation."""
    missing = PatchReadiness(False, "receipt_missing", "Native patch receipt is missing; run the Word Factori Linux installer.")
    try:
        receipt = json.loads((mod_folder / RECEIPT_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return missing
    except (OSError, ValueError, TypeError):
        return PatchReadiness(False, "receipt_invalid", "Native patch receipt is unreadable or invalid; rerun the installer.")
    try:
        if (not isinstance(receipt, dict) or receipt["protocol"] != PATCH_PROTOCOL
                or receipt["original_sha256"] != ORIGINAL_SHA256
                or receipt["patched_sha256"] != PATCHED_SHA256):
            raise ValueError("unsupported receipt")
        path = Path(receipt["game_data"])
        if not path.is_absolute() or path.name.lower() != "data.win":
            raise ValueError("invalid game path")
        if installation is not None:
            if (mod_folder != installation.mod_folder
                    or receipt.get("platform") != "linux" or path != installation.game_data
                    or receipt.get("prefix") != str(installation.prefix)
                    or receipt.get("factori_root") != str(installation.factori_root)):
                raise ValueError("receipt does not match selected installation")
            worlds = Path(receipt.get("ap_worlds", ""))
            if not worlds.is_absolute() or worlds.name != "custom_worlds" or not worlds.is_dir():
                raise ValueError("receipt has no native Archipelago worlds directory")
            backup = installation.game_data.with_name("data.wf-ap-original.win")
            if not backup.is_file() or _digest(backup) != ORIGINAL_SHA256:
                return PatchReadiness(False, "backup_invalid", "Native patch backup is missing or invalid; rerun the installer.")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != PATCHED_SHA256:
            detail = "The game is unpatched after restore" if digest == ORIGINAL_SHA256 else "The game binary hash changed"
            return PatchReadiness(False, "game_hash_mismatch", f"{detail}; rerun the native patch installer.")
        return PatchReadiness(True, "ready", "Native patch is ready.")
    except (OSError, ValueError, TypeError, KeyError):
        return PatchReadiness(False, "receipt_invalid", "Native patch receipt does not match the selected installation; rerun the installer.")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def patch_ready(mod_folder: Path, installation: InstallationPaths | None = None) -> bool:
    return patch_readiness(mod_folder, installation).ready


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
