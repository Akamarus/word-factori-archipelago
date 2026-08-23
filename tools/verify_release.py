from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_release import (
    PROHIBITED_RELEASE_BASENAMES,
    RELEASE_ARCHIVE,
    RELEASE_MANIFEST,
    WORLD_ARCHIVE,
    include,
)
from tools.derive_requirements import derive
from word_factori.campaign import available_level_sets, campaign_for_level_set, load_campaign
from word_factori.data import CAMPAIGN_DIGEST, CAMPAIGN_ID, CAMPAIGN_VERSION, LOCATIONS


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_prohibited_release_entries(names: list[str]) -> list[str]:
    prohibited = []
    for name in names:
        parts = tuple(part.casefold() for part in Path(name).parts)
        if ".superpowers" in parts or (parts and parts[-1] in PROHIBITED_RELEASE_BASENAMES):
            prohibited.append(name)
    return prohibited


def verify_archive_matches_disk(archive_path: Path, roots: tuple[str, ...] | None = None) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        archived = {name: digest(archive.read(name)) for name in archive.namelist()}
    if roots is None:
        disk_paths = [path for path in (ROOT / "word_factori").rglob("*") if path.is_file() and include(path)]
    else:
        disk_paths = [
            ROOT / name
            for name in (
                "README.md",
                "LICENSE",
                "install.ps1",
                "Install Word Factori Archipelago.cmd",
                "word_factori.apworld",
                "release-manifest.json",
            )
        ]
        for root in roots:
            disk_paths.extend(path for path in (ROOT / root).rglob("*") if path.is_file() and include(path))
    disk = {path.relative_to(ROOT).as_posix(): digest(path.read_bytes()) for path in disk_paths}
    if archived != disk:
        raise AssertionError(f"archive parity failed for {archive_path.name}")


def verify_headless_modules() -> None:
    for name in (
        "word_factori.campaign",
        "word_factori.client_messages",
        "word_factori.overlay_model",
        "word_factori.overlay_protocol",
        "word_factori.overlay_renderer",
    ):
        importlib.import_module(name)
    if any(name == "kivy" or name.startswith("kivy.") for name in sys.modules):
        raise AssertionError("headless release verification imported Kivy")


def load_release_manifest() -> dict[str, str]:
    try:
        payload = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AssertionError(f"release manifest is unreadable: {error}") from error
    files = payload.get("files") if isinstance(payload, dict) and payload.get("format") == 1 else None
    if not isinstance(files, dict) or not all(
        isinstance(name, str)
        and PurePosixPath(name).as_posix() == name
        and not PurePosixPath(name).is_absolute()
        and ".." not in PurePosixPath(name).parts
        and "\\" not in name
        and name != RELEASE_MANIFEST.name
        and isinstance(checksum, str)
        and len(checksum) == 64
        and all(character in "0123456789abcdef" for character in checksum)
        for name, checksum in files.items()
    ):
        raise AssertionError("release manifest has an invalid schema")
    return files


def is_runtime_cache(name: str) -> bool:
    parts = Path(name).parts
    return "__pycache__" in parts or name.casefold().endswith((".pyc", ".pyo"))


def main(*, verify_installed: bool = False) -> None:
    verify_headless_modules()
    if RELEASE_ARCHIVE.name != "word-factori-archipelago-hybrid-1.2.0.zip":
        raise AssertionError("unexpected hybrid release name")
    verify_archive_matches_disk(WORLD_ARCHIVE)
    release_archive_present = RELEASE_ARCHIVE.is_file()
    if release_archive_present:
        verify_archive_matches_disk(RELEASE_ARCHIVE, ("docs", "game_mod", "tests", "tools", "word_factori"))
    manifest_files = load_release_manifest()

    game_mod = ROOT / "game_mod" / "word factori archipelago"
    payloads = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in game_mod.glob("*.json")}
    if [level["text"] for level in payloads["levels.json"]] != [location.target for location in LOCATIONS]:
        raise AssertionError("game mod indices do not match AP locations")
    identity = payloads.get("archipelago_campaign.json", {})
    expected_identity = {
        "campaign_id": CAMPAIGN_ID,
        "manifest_version": CAMPAIGN_VERSION,
        "manifest_digest": CAMPAIGN_DIGEST,
        "level_count": len(LOCATIONS),
    }
    if identity != expected_identity:
        raise AssertionError("game mod campaign identity does not match AP manifest")
    if len(LOCATIONS) != 40:
        raise AssertionError("hybrid campaign must contain 40 locations")
    if available_level_sets() != ("core_campaign", "discovery_labs"):
        raise AssertionError("curated level set catalog changed unexpectedly")
    if tuple(len(campaign_for_level_set(key).levels) for key in available_level_sets()) != (30, 40):
        raise AssertionError("curated level set sizes are invalid")
    if payloads["recipes.json"] != {"include_vanilla": True}:
        raise AssertionError("game mod does not use vanilla recipes through the supported flag")

    installed_recipes = Path(r"C:\Program Files (x86)\Steam\steamapps\common\word factori\recipes.data")
    if installed_recipes.is_file():
        generated = derive(installed_recipes)
        manifest = load_campaign()
        stored = {
            record.target: [sorted(option) for option in record.requirement_options]
            for record in manifest.levels
            if record.kind in {"word", "final"}
        }
        if generated != stored:
            raise AssertionError("stored requirements differ from a fresh installed-game derivation")

    if verify_installed:
        installed_world = Path(r"C:\ProgramData\Archipelago\custom_worlds\word_factori.apworld")
        installed_mod = Path.home() / "AppData" / "Local" / "factori" / "mods" / "word factori archipelago"
        if not installed_world.is_file() or digest(installed_world.read_bytes()) != digest(WORLD_ARCHIVE.read_bytes()):
            raise AssertionError("installed APWorld differs from release APWorld")
        for source in game_mod.glob("*.json"):
            installed = installed_mod / source.name
            if not installed.is_file() or digest(installed.read_bytes()) != digest(source.read_bytes()):
                raise AssertionError(f"installed mod differs at {source.name}")

    if release_archive_present:
        with zipfile.ZipFile(RELEASE_ARCHIVE) as archive:
            names = archive.namelist()
            actual_files = set(names)
            expected_files = set(manifest_files) | {RELEASE_MANIFEST.name}
            if actual_files != expected_files:
                raise AssertionError("release entries differ from release-manifest.json")
            for name, expected in manifest_files.items():
                if digest(archive.read(name)) != expected:
                    raise AssertionError(f"release manifest hash differs at {name}")
    else:
        names = [
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file() and not is_runtime_cache(path.relative_to(ROOT).as_posix())
        ]
        expected_files = set(manifest_files) | {RELEASE_MANIFEST.name}
        if set(names) != expected_files:
            raise AssertionError("extracted entries differ from release-manifest.json")
        for name, expected in manifest_files.items():
            if digest((ROOT / name).read_bytes()) != expected:
                raise AssertionError(f"extracted release manifest hash differs at {name}")
    prohibited = find_prohibited_release_entries(names)
    if prohibited:
        raise AssertionError(f"proprietary/user data entered release: {prohibited}")
    if any(name.startswith("tests/output") or "__pycache__" in name for name in names):
        raise AssertionError("generated output or caches entered release")
    for required in (
        "word_factori/campaign_packs.json",
        "word_factori/client_messages.py",
        "word_factori/overlay_renderer.py",
        "docs/testing/full-ingame-client-acceptance.md",
    ):
        if required not in names:
            raise AssertionError(f"release is missing {required}")

    print(f"APWorld SHA-256 {digest(WORLD_ARCHIVE.read_bytes())}")
    if release_archive_present:
        print(f"Release SHA-256 {digest(RELEASE_ARCHIVE.read_bytes())}")
    else:
        print("Release archive not present; validated extracted manifest and hygiene")
    installed_text = ", installed-copy parity" if verify_installed else ""
    parity_text = "source parity" if release_archive_present else "extracted manifest/hygiene"
    print(f"Release verification passed: {parity_text}, JSON/index integrity, fresh recipe derivation{installed_text}, and data exclusions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-installed", action="store_true")
    args = parser.parse_args()
    main(verify_installed=args.verify_installed)
