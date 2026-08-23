from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_release import LEGACY_RELEASE_ARCHIVE, RELEASE_ARCHIVE, WORLD_ARCHIVE, include
from tools.derive_requirements import derive
from word_factori.campaign import load_campaign
from word_factori.data import CAMPAIGN_DIGEST, CAMPAIGN_ID, CAMPAIGN_VERSION, LOCATIONS


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_archive_matches_disk(archive_path: Path, roots: tuple[str, ...] | None = None) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        archived = {name: digest(archive.read(name)) for name in archive.namelist()}
    if roots is None:
        disk_paths = [path for path in (ROOT / "word_factori").rglob("*") if path.is_file() and include(path)]
    else:
        disk_paths = [ROOT / name for name in ("README.md", "LICENSE", "install.ps1", "word_factori.apworld")]
        for root in roots:
            disk_paths.extend(path for path in (ROOT / root).rglob("*") if path.is_file() and include(path))
    disk = {path.relative_to(ROOT).as_posix(): digest(path.read_bytes()) for path in disk_paths}
    if archived != disk:
        raise AssertionError(f"archive parity failed for {archive_path.name}")


def main(*, verify_installed: bool = False) -> None:
    if RELEASE_ARCHIVE.name != "word-factori-archipelago-hybrid-1.1.0.zip":
        raise AssertionError("unexpected hybrid release name")
    if not LEGACY_RELEASE_ARCHIVE.is_file():
        raise AssertionError("stable 1.0.0 release archive was not preserved")
    verify_archive_matches_disk(WORLD_ARCHIVE)
    verify_archive_matches_disk(RELEASE_ARCHIVE, ("docs", "game_mod", "tests", "tools", "word_factori"))

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

    with zipfile.ZipFile(RELEASE_ARCHIVE) as archive:
        names = archive.namelist()
        prohibited = [name for name in names if name.casefold().endswith(("data.win", "recipes.data", "save.json"))]
        if prohibited:
            raise AssertionError(f"proprietary/user data entered release: {prohibited}")
        if any(name.startswith("tests/output") or "__pycache__" in name for name in names):
            raise AssertionError("generated output or caches entered release")

    print(f"APWorld SHA-256 {digest(WORLD_ARCHIVE.read_bytes())}")
    print(f"Release SHA-256 {digest(RELEASE_ARCHIVE.read_bytes())}")
    installed_text = ", installed-copy parity" if verify_installed else ""
    print(f"Release verification passed: source parity, JSON/index integrity, fresh recipe derivation{installed_text}, and data exclusions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-installed", action="store_true")
    args = parser.parse_args()
    main(verify_installed=args.verify_installed)
