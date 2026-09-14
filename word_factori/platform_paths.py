"""Local Steam/Proton installation paths shared by setup and the Linux client.

This module deliberately has no Archipelago or platform-specific dependencies.
Discovery reports every valid installation/account pair; choosing one is a UI
decision, never an incidental result of directory ordering.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


APP_ID = "2072840"
MOD_NAME = "word factori archipelago"
CONFIG_DIRECTORY = "word-factori-archipelago"
CONFIG_FILENAME = "installation.json"
_MAX_VDF_BYTES = 2 * 1024 * 1024
_MAX_VDF_TOKENS = 20000
_MAX_VDF_DEPTH = 32


@dataclass(frozen=True)
class InstallationPaths:
    game_data: Path
    prefix: Path
    factori_root: Path

    @property
    def mod_folder(self) -> Path:
        return self.factori_root / "mods" / MOD_NAME

    @property
    def local_app_data(self) -> Path:
        return self.factori_root.parent


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _is_alias(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _has_alias_ancestor(path: Path) -> bool:
    return any(_is_alias(candidate) for candidate in (path, *path.parents))


def validate_installation(paths: InstallationPaths) -> InstallationPaths:
    """Require an existing game and one exact account inside an existing prefix."""
    if not isinstance(paths, InstallationPaths):
        raise ValueError("installation descriptor is invalid")
    game_data, prefix, factori = paths.game_data, paths.prefix, paths.factori_root
    if not all(isinstance(p, Path) and p.is_absolute() for p in (game_data, prefix, factori)):
        raise ValueError("installation paths must be absolute")
    if (game_data.name != "data.win" or not game_data.is_file()
            or _has_alias_ancestor(game_data)):
        raise ValueError("game data.win is missing or unsafe")
    if (not prefix.is_dir() or _has_alias_ancestor(prefix)
            or not (prefix / "drive_c" / "users").is_dir()):
        raise ValueError("Proton prefix has not been initialized")
    try:
        relative = factori.relative_to(prefix)
    except ValueError as error:
        raise ValueError("factori directory is outside the Proton prefix") from error
    parts = relative.parts
    if (len(parts) != 6 or parts[0] != "drive_c" or parts[1] != "users"
            or not parts[2] or tuple(parts[3:]) != ("AppData", "Local", "factori")):
        raise ValueError("factori directory is not a Proton user's AppData/Local/factori")
    if not factori.is_dir() or not _within(factori, prefix):
        raise ValueError("factori directory is missing or leaves the Proton prefix")
    # Discovery canonicalizes Steam-root aliases first. Below the selected
    # prefix, no component may redirect into another user or outside it.
    current = prefix
    for component in parts:
        current = current / component
        if _is_alias(current):
            raise ValueError("factori directory contains an unsafe symlink")
    if _has_alias_ancestor(paths.mod_folder):
        raise ValueError("mod directory contains an unsafe symlink")
    return paths


def validate_state_target(paths: InstallationPaths, target: Path) -> Path:
    """Recheck a native client's sidecar destination before reading or writing."""
    validate_installation(paths)
    if (not target.is_absolute()
            or not target.is_relative_to(paths.factori_root / "archipelago")
            or ".." in target.parts or _has_alias_ancestor(target)):
        raise ValueError("Client state path is unsafe; remove the redirection before reconnecting")
    return target


def config_path(environ: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    environment = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    xdg = environment.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if isinstance(xdg, str) and xdg else home / ".config"
    if not base.is_absolute():
        base = home / ".config"
    return base / CONFIG_DIRECTORY / CONFIG_FILENAME


def _configuration_file(path: Path | None) -> Path:
    result = config_path() if path is None else Path(path)
    if not result.is_absolute():
        raise ValueError("configuration path must be absolute")
    return result


def _refuse_symlink_path(path: Path) -> None:
    for candidate in (path, *path.parents):
        if _is_alias(candidate):
            raise ValueError("configuration path contains a symlink")


def load_installation(path: Path | None = None) -> InstallationPaths:
    destination = _configuration_file(path)
    _refuse_symlink_path(destination)
    try:
        if destination.stat().st_size > 65536:
            raise ValueError("installation configuration is too large")
        document = json.loads(destination.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("installation configuration is malformed") from error
    if not isinstance(document, dict) or set(document) != {"schema", "game_data", "prefix", "factori_root"}:
        raise ValueError("installation configuration has invalid fields")
    if type(document["schema"]) is not int or document["schema"] != 1:
        raise ValueError("installation configuration schema is unsupported")
    if not all(isinstance(document[key], str) and document[key] for key in ("game_data", "prefix", "factori_root")):
        raise ValueError("installation configuration has invalid paths")
    return validate_installation(InstallationPaths(
        Path(document["game_data"]), Path(document["prefix"]), Path(document["factori_root"])
    ))


def save_installation(paths: InstallationPaths, path: Path | None = None) -> None:
    validate_installation(paths)
    destination = _configuration_file(path)
    _refuse_symlink_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _refuse_symlink_path(destination)
    document = {
        "schema": 1, "game_data": str(paths.game_data),
        "prefix": str(paths.prefix), "factori_root": str(paths.factori_root),
    }
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=".installation-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(document, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _refuse_symlink_path(destination)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _vdf_tokens(source: str) -> list[str] | None:
    tokens: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if source.startswith("//", index):
            end = source.find("\n", index)
            index = len(source) if end < 0 else end + 1
            continue
        if char in "{}":
            tokens.append(char)
            index += 1
        elif char == '"':
            index += 1
            value: list[str] = []
            while index < len(source) and source[index] != '"':
                if source[index] == "\\" and index + 1 < len(source) and source[index + 1] in ('"', "\\"):
                    index += 1
                value.append(source[index])
                index += 1
            if index == len(source):
                return None
            tokens.append("".join(value))
            index += 1
        else:
            return None
        if len(tokens) > _MAX_VDF_TOKENS:
            return None
    return tokens


def _read_vdf(path: Path) -> dict | None:
    try:
        if path.stat().st_size > _MAX_VDF_BYTES:
            return None
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return None
    tokens = _vdf_tokens(source)
    if tokens is None:
        return None
    index = 0

    def block(depth: int, nested: bool) -> dict | None:
        nonlocal index
        if depth > _MAX_VDF_DEPTH:
            return None
        result: dict = {}
        while index < len(tokens):
            key = tokens[index]
            if key == "}":
                if not nested:
                    return None
                index += 1
                return result
            if key == "{" or index + 1 >= len(tokens) or key in result:
                return None
            index += 1
            value = tokens[index]
            index += 1
            if value == "{":
                value = block(depth + 1, True)
                if value is None:
                    return None
            elif value == "}":
                return None
            result[key] = value
        return None if nested else result

    document = block(0, False)
    return document if index == len(tokens) else None


def _safe_directory_name(name: object) -> bool:
    return (isinstance(name, str) and bool(name) and name not in (".", "..")
            and "/" not in name and "\\" not in name and ":" not in name
            and "\x00" not in name)


def _default_steam_roots() -> tuple[Path, ...]:
    home = Path.home()
    return (home / ".steam" / "steam", home / ".local" / "share" / "Steam",
            home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam")


def discover_installations(steam_roots=None) -> list[InstallationPaths]:
    """Find all validated app/account candidates in bounded Steam libraries."""
    roots = _default_steam_roots() if steam_roots is None else steam_roots
    libraries: list[Path] = []
    seen_libraries: set[Path] = set()

    def add_library(value: Path) -> None:
        library = Path(value).expanduser().resolve()
        if library.is_dir() and library not in seen_libraries:
            if len(libraries) >= 64:
                raise ValueError("Steam discovery exceeds 64 libraries")
            seen_libraries.add(library)
            libraries.append(library)

    for root in roots:
        add_library(Path(root))
    for root in tuple(libraries):
        metadata = _read_vdf(root / "steamapps" / "libraryfolders.vdf")
        folders = metadata.get("libraryfolders") if isinstance(metadata, dict) else None
        if not isinstance(folders, dict):
            continue
        for key, value in folders.items():
            if not key.isdecimal():
                continue
            directory = value.get("path") if isinstance(value, dict) else value
            if isinstance(directory, str) and Path(directory).is_absolute():
                add_library(Path(directory))

    results: list[InstallationPaths] = []
    seen_paths: set[tuple[Path, Path, Path]] = set()
    for library in libraries:
        steamapps = library / "steamapps"
        manifest = _read_vdf(steamapps / f"appmanifest_{APP_ID}.acf")
        app = manifest.get("AppState") if isinstance(manifest, dict) else None
        if not isinstance(app, dict) or app.get("appid") != APP_ID:
            continue
        game_dir = app.get("installdir")
        if not _safe_directory_name(game_dir):
            continue
        game_data = steamapps / "common" / game_dir / "data.win"
        prefix = steamapps / "compatdata" / APP_ID / "pfx"
        users = prefix / "drive_c" / "users"
        if not users.is_dir():
            continue
        try:
            accounts = []
            for entry in users.iterdir():
                if entry.is_dir():
                    accounts.append(entry)
                    if len(accounts) > 32:
                        raise ValueError("Steam discovery exceeds 32 Proton users")
        except OSError:
            continue
        for account in sorted(accounts, key=lambda p: p.name):
            factori = account / "AppData" / "Local" / "factori"
            candidate = InstallationPaths(game_data, prefix, factori)
            try:
                validate_installation(candidate)
            except (ValueError, OSError):
                continue
            identity = tuple(path.resolve() for path in (game_data, prefix, factori))
            if identity not in seen_paths:
                seen_paths.add(identity)
                results.append(candidate)
    return results


def _casefold_child(parent: Path, component: str) -> Path:
    exact = parent / component
    if exact.exists():
        return exact
    if not parent.is_dir():
        return exact
    try:
        matches = [entry for entry in parent.iterdir() if entry.name.casefold() == component.casefold()]
    except OSError:
        return exact
    if len(matches) > 1:
        raise ValueError("ambiguous case-insensitive Proton path")
    return matches[0] if matches else exact


def resolve_proton_path(value: str, prefix: Path) -> Path:
    """Map an absolute Windows drive path only within the selected prefix."""
    if not isinstance(value, str) or not isinstance(prefix, Path) or not prefix.is_absolute():
        raise ValueError("Windows path and absolute Proton prefix are required")
    if "\x00" in value or value.startswith(("\\\\", "//")):
        raise ValueError("network and device paths are not supported")
    match = re.fullmatch(r"([A-Za-z]):[\\/](.*)", value)
    if match is None:
        raise ValueError("an absolute Windows drive path is required")
    drive = match.group(1).lower()
    parts = re.split(r"[\\/]", match.group(2))
    if any(not part or part in (".", "..") or ":" in part or any(ord(c) < 32 for c in part) for part in parts):
        raise ValueError("Windows path contains unsafe components")
    if drive == "c":
        current = prefix / "drive_c"
    else:
        current = prefix / "dosdevices" / f"{drive}:"
        if not current.is_dir():
            raise ValueError("Windows drive has no mapping in this prefix")
    if not _within(current, prefix):
        raise ValueError("Windows drive mapping leaves the prefix")
    for part in parts:
        current = _casefold_child(current, part)
        if _is_alias(current):
            raise ValueError("Windows path crosses an aliased directory")
        if not _within(current, prefix):
            raise ValueError("Windows path leaves the prefix")
    return current


def selected_proton_mod(payload, paths: InstallationPaths) -> bool:
    """Accept only this integration's selected mod, in the chosen account."""
    if not isinstance(payload, Mapping):
        return False
    folder = payload.get("folder")
    if not isinstance(folder, str) or not folder.strip():
        return False
    folder = folder.strip()
    try:
        validate_installation(paths)
        expected = paths.mod_folder
        if (not expected.is_dir() or _is_alias(paths.factori_root / "mods")
                or _is_alias(expected) or not _within(expected, paths.factori_root)):
            return False
        if re.match(r"^[A-Za-z]:[\\/]", folder):
            selected = resolve_proton_path(folder, paths.prefix)
            return selected.resolve() == expected.resolve()
        parts = re.split(r"[\\/]", folder)
        return [part.casefold() for part in parts] in ([MOD_NAME], ["mods", MOD_NAME])
    except (ValueError, OSError):
        return False
