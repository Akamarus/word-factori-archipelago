from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORLD_ARCHIVE = ROOT / "word_factori.apworld"
LEGACY_RELEASE_ARCHIVE = ROOT / "word-factori-archipelago-full-1.0.0.zip"
RELEASE_ARCHIVE = ROOT / "word-factori-archipelago-hybrid-1.2.0.zip"
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
        and "__pycache__" not in folded_parts
        and path.name.casefold() not in PROHIBITED_RELEASE_BASENAMES
        and not path.name.casefold().endswith((".pyc", ".pyo"))
        and not (len(parts) >= 2 and parts[0] == "tests" and parts[1].startswith("output"))
        and not (len(parts) >= 2 and parts[0] == "tests" and parts[1].startswith("live-room"))
        and path not in {RELEASE_ARCHIVE, LEGACY_RELEASE_ARCHIVE}
    )


def write_world() -> None:
    with zipfile.ZipFile(WORLD_ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "word_factori").rglob("*")):
            if path.is_file() and include(path):
                write_reproducible_file(archive, path)


def write_release() -> None:
    roots = ["docs", "game_mod", "tests", "tools", "word_factori"]
    files = [
        ROOT / "README.md", ROOT / "LICENSE", ROOT / "install.ps1",
        ROOT / "Install Word Factori Archipelago.cmd", WORLD_ARCHIVE,
    ]
    for root_name in roots:
        files.extend(path for path in (ROOT / root_name).rglob("*") if path.is_file())
    with zipfile.ZipFile(RELEASE_ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            if include(path):
                write_reproducible_file(archive, path)


if __name__ == "__main__":
    write_world()
    write_release()
    digest = hashlib.sha256(WORLD_ARCHIVE.read_bytes()).hexdigest()
    print(f"APWorld SHA-256: {digest}")
    print(f"Wrote {RELEASE_ARCHIVE}")
