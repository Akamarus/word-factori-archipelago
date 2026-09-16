"""Room-bound, atomic native machine snapshots. Never reads or writes game saves."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import re
import time

from .mod import MODULES, _write_json
from .quantities import MODULE_FAMILIES, checked_vector
from .platform_paths import InstallationPaths, validate_installation, validate_ap_worlds

ORIGINAL_SHA256 = "d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978"
PATCH_PROTOCOL = "enhanced_v2"
PATCHED_SHA256 = "20ccd780854adcab416f903e8ffb1702930c16fd91c307ec316d746da1567bbe"
ENFORCEMENT_CAPABILITY = "free_word_machine_enforcement_v1"
RUNTIME_SCHEMA = 2
QUANTITY_CAPABILITY = "progressive_machine_enforcement_v1"
QUANTITY_SCHEMA = 3
MAX_REVISION = 2**53 - 1
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
    installer = "the Word Factori Linux installer" if installation is not None else "Install Word Factori Archipelago.cmd"
    missing = PatchReadiness(False, "receipt_missing", f"Native patch receipt is missing; run {installer}.")
    if installation is not None:
        try:
            validate_installation(installation)
        except (OSError, ValueError):
            return PatchReadiness(False, "path_unsafe", "Configured installation path is missing or unsafe; rerun the Linux installer.")
    try:
        receipt = json.loads((mod_folder / RECEIPT_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return missing
    except (OSError, ValueError, TypeError):
        return PatchReadiness(False, "receipt_invalid", "Native patch receipt is unreadable or invalid; rerun the installer.")
    try:
        if (not isinstance(receipt, dict) or receipt["protocol"] != PATCH_PROTOCOL
                or receipt.get("capability") != ENFORCEMENT_CAPABILITY
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
            try:
                validate_ap_worlds(installation, Path(receipt.get("ap_worlds", "")))
            except (OSError, ValueError, TypeError) as error:
                return PatchReadiness(False, "receipt_invalid",
                                      f"Native Archipelago directory is invalid: {error}. Rerun the Linux installer.")
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


def machine_counts_for_view(view) -> dict[str, int]:
    if view.machine_limits is not None:
        limits = checked_vector(view.machine_limits, allowance=True)
        return {"IFactory": -1, **{module: limits[family] for module, family in MODULE_FAMILIES.items()}}
    owned = set(view.owned_machines) | {"Bender Access"}
    return {"IFactory": -1, **{module: -1 if item in owned else 0
            for item, modules in MODULES.items() for module in modules}}


def runtime_context(room: str, layout: str, checks_contract: str, *, progressive: bool = False) -> dict:
    if type(progressive) is not bool:
        raise ValueError("progressive must be a boolean")
    if not all(valid_digest(value) for value in (room, layout, checks_contract)):
        raise ValueError("Enhanced runtime requires complete room, layout and checks identities")
    return {"schema": QUANTITY_SCHEMA if progressive else RUNTIME_SCHEMA, "mode": "enhanced", "room": room, "layout": layout,
            "checks_contract": checks_contract, "capability": QUANTITY_CAPABILITY if progressive else ENFORCEMENT_CAPABILITY}


def publish_runtime(path: Path, room: str, layout: str, levels: list[dict], *,
                    machine_counts: dict, checks_contract: str, progressive: bool = False) -> bool:
    context = runtime_context(room, layout, checks_contract, progressive=progressive)
    allowed = (-1,0,1,2,3,4) if progressive else (-1,0)
    if (not isinstance(machine_counts, dict) or set(machine_counts) != ALLOWED_MODULES
            or any(type(count) is not int or count not in allowed for count in machine_counts.values())
            or machine_counts["IFactory"] != -1):
        raise ValueError("Enhanced runtime requires complete machine inventory")
    if progressive and (machine_counts['Rotate_cw'] != machine_counts['Rotate_ccw']
                        or machine_counts['Reflect_hor'] != machine_counts['Reflect_vert']):
        raise ValueError("Directional variants must share a family allowance")
    if not isinstance(levels, list) or not levels:
        raise ValueError("Enhanced runtime requires levels")
    for entry in levels:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str) or not isinstance(entry.get("module_counts"), dict):
            raise ValueError("Invalid runtime level")
        for name, count in entry["module_counts"].items():
            if name not in ALLOWED_MODULES or type(count) is not int or not 0 <= count <= 10000:
                raise ValueError("Invalid runtime machine limit")
    payload = {**context, "levels": levels, "machine_counts": machine_counts}
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        revision = previous.get("revision") if isinstance(previous, dict) else None
        if type(revision) is not int or not 0 <= revision <= MAX_REVISION:
            previous, revision = {}, 0
    except (OSError, ValueError, TypeError):
        previous, revision = {}, 0
    if previous == {**payload, "revision": revision}:
        return False
    # Millisecond epoch also recovers after a lost/corrupt sidecar; persisted
    # revision orders rapid updates and clock rollback across reconnects.
    payload["revision"] = max(time.time_ns() // 1_000_000, revision + 1)
    if payload["revision"] > MAX_REVISION:
        raise ValueError("Enhanced runtime revision exhausted")
    _write_json(path, payload)
    return True
