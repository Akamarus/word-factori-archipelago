from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORLD_ARCHIVE = ROOT / "word_factori.apworld"
LEGACY_RELEASE_ARCHIVE = ROOT / "word-factori-archipelago-full-1.0.0.zip"
RELEASE_ARCHIVE = ROOT / "word-factori-archipelago-hybrid-1.1.0.zip"


def include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = relative.parts
    return (
        "__pycache__" not in parts
        and not path.name.endswith((".pyc", ".pyo"))
        and not (len(parts) >= 2 and parts[0] == "tests" and parts[1].startswith("output"))
        and not (len(parts) >= 2 and parts[0] == "tests" and parts[1].startswith("live-room"))
        and path not in {RELEASE_ARCHIVE, LEGACY_RELEASE_ARCHIVE}
    )


def write_world() -> None:
    with zipfile.ZipFile(WORLD_ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "word_factori").rglob("*")):
            if path.is_file() and include(path):
                archive.write(path, path.relative_to(ROOT).as_posix())


def write_release() -> None:
    roots = ["docs", "game_mod", "tests", "tools", "word_factori"]
    files = [ROOT / "README.md", ROOT / "LICENSE", ROOT / "install.ps1", WORLD_ARCHIVE]
    for root_name in roots:
        files.extend(path for path in (ROOT / root_name).rglob("*") if path.is_file())
    with zipfile.ZipFile(RELEASE_ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            if include(path):
                archive.write(path, path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    write_world()
    write_release()
    digest = hashlib.sha256(WORLD_ARCHIVE.read_bytes()).hexdigest()
    print(f"APWorld SHA-256: {digest}")
    print(f"Wrote {RELEASE_ARCHIVE}")
