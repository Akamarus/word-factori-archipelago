from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads(
    (ROOT / "word_factori" / "archipelago.json").read_text(encoding="utf-8")
)["world_version"]
WORLD_ARCHIVE = ROOT / "word_factori.apworld"
LEGACY_RELEASE_ARCHIVE = ROOT / "word-factori-archipelago-full-1.0.0.zip"
RELEASE_ARCHIVE = ROOT / f"word-factori-archipelago-{VERSION}.zip"
RELEASE_MANIFEST = ROOT / "release-manifest.json"
WORLD_SOURCE_NAMES = (
    "word_factori/Components.py",
    "word_factori/__init__.py",
    "word_factori/archipelago.json",
    "word_factori/bridge.py",
    "word_factori/campaign.json",
    "word_factori/campaign.py",
    "word_factori/campaign_packs.json",
    "word_factori/capabilities.py",
    "word_factori/client.py",
    "word_factori/client_core.py",
    "word_factori/client_messages.py",
    "word_factori/data.py",
    "word_factori/dispatch.py",
    "word_factori/dispatch_store.py",
    "word_factori/enhanced_runtime.py",
    "word_factori/docs/setup_en.md",
    "word_factori/layout.py",
    "word_factori/mod.py",
    "word_factori/options.py",
    "word_factori/overlay_model.py",
    "word_factori/overlay_preferences.py",
    "word_factori/overlay_protocol.py",
    "word_factori/overlay_renderer.py",
    "word_factori/overlay_supervisor.py",
    "word_factori/recipe_graph.py",
    "word_factori/requirements.py",
    "word_factori/save.py",
    "word_factori/version.py",
    "word_factori/window_tracker.py",
)
WORLD_SOURCE_FILES = tuple(ROOT / name for name in WORLD_SOURCE_NAMES)
PROHIBITED_RELEASE_BASENAMES = {
    "data.win",
    "fredokaone.ttf",
    "letters.ttf",
    "recipes.data",
    "save.json",
}
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def write_reproducible_file(archive: zipfile.ZipFile, path: Path) -> None:
    info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(info, path.read_bytes())


def include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = relative.parts
    folded_parts = tuple(part.casefold() for part in parts)
    return (
        ".superpowers" not in folded_parts
        and folded_parts[:2] != ("docs", "superpowers")
        and folded_parts[:2] != ("docs", "testing")
        and "__pycache__" not in folded_parts
        and path.name.casefold() not in PROHIBITED_RELEASE_BASENAMES
        and not path.name.casefold().endswith((".pyc", ".pyo"))
        and not (len(parts) >= 2 and parts[0] == "tests" and parts[1].startswith("output"))
        and not (len(parts) >= 2 and parts[0] == "tests" and parts[1].startswith("live-room"))
        and path not in {RELEASE_ARCHIVE, LEGACY_RELEASE_ARCHIVE}
    )


def write_world() -> None:
    with zipfile.ZipFile(WORLD_ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in WORLD_SOURCE_FILES:
            if not path.is_file():
                raise FileNotFoundError(f"required APWorld source is missing: {path.relative_to(ROOT)}")
            write_reproducible_file(archive, path)


def write_release() -> None:
    roots = ["docs/images", "examples", "game_mod"]
    files = [
        ROOT / "README.md", ROOT / "LICENSE", ROOT / "install.ps1",
        ROOT / "Install Word Factori Archipelago.cmd", WORLD_ARCHIVE,
        ROOT / "docs/enhanced-playtest.md",
    ]
    for root_name in roots:
        files.extend(path for path in (ROOT / root_name).rglob("*") if path.is_file())
    files = sorted(set(path for path in files if include(path) and path != RELEASE_MANIFEST))
    manifest = {
        "format": 1,
        "files": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
    }
    RELEASE_MANIFEST.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    files.append(RELEASE_MANIFEST)
    with zipfile.ZipFile(RELEASE_ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            write_reproducible_file(archive, path)


if __name__ == "__main__":
    write_world()
    write_release()
    digest = hashlib.sha256(WORLD_ARCHIVE.read_bytes()).hexdigest()
    print(f"APWorld SHA-256: {digest}")
    print(f"Wrote {RELEASE_ARCHIVE}")
