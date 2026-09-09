"""Bundle a local opt-in playtest, with a delta only, never game binaries."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_release import RELEASE_ARCHIVE
from tools.enhanced_delta import apply_delta, build_delta
from tools.enhanced_hooks import verify_original
from word_factori.enhanced_runtime import PATCHED_SHA256

PLAYER_YAML = """name: JackEnhanced
game: Word Factori
description: Enhanced first-page playtest; requires the native patch
requires:
  version: 0.6.7
Word Factori:
  integration_mode: enhanced
  campaign_layout: shuffled_pages
  custom_level_set: discovery_labs
  goal: campaign_count
  campaign_count: 25
  accessibility: items
"""


def build_playtest(original_path: Path, patched_path: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Output already exists; choose a fresh playtest archive")
    original = original_path.read_bytes()
    verify_original(original)
    patched = patched_path.read_bytes()
    if hashlib.sha256(patched).hexdigest() != PATCHED_SHA256:
        raise ValueError("Patched game does not match the client and installer")
    installer = (ROOT / "tools/install_enhanced.ps1").read_bytes()
    if PATCHED_SHA256.encode() not in installer:
        raise ValueError("Installer does not identify the tested patch")
    delta = build_delta(original, patched)
    if apply_delta(original, delta) != patched:
        raise ValueError("Delta reconstruction failed")
    with zipfile.ZipFile(RELEASE_ARCHIVE) as base:
        entries = {name: base.read(name) for name in base.namelist()}
    entries.update({
        "START HERE.md": (ROOT / "docs/enhanced-playtest.md").read_bytes(),
        "docs/enhanced-playtest.md": (ROOT / "docs/enhanced-playtest.md").read_bytes(),
        "Enhanced Player.yaml": PLAYER_YAML.encode(),
        "Install or Update Playtest.cmd": (ROOT / "tools/Install or Update Playtest.cmd").read_bytes(),
        "enhanced/install_enhanced.ps1": installer,
        "enhanced/Install Enhanced Patch.cmd": (ROOT / "tools/Install Enhanced Patch.cmd").read_bytes(),
        "enhanced/Restore Original Game.cmd": (ROOT / "tools/Restore Original Game.cmd").read_bytes(),
        "enhanced/enhanced.patch.gz": gzip.compress(json.dumps(delta, separators=(",", ":")).encode(), mtime=0),
    })
    forbidden = {"data.win", "recipes.data", "fredokaone.ttf", "letters.ttf", "save.json"}
    for name in entries:
        parts = Path(name).parts
        if Path(name).is_absolute() or ".." in parts or Path(name).name.lower() in forbidden or name.lower().endswith((".exe", ".dll", ".win", ".ogg")):
            raise ValueError(f"Prohibited player payload: {name}")
    manifest = {"format": 1, "status": "local enhanced playtest; full visual acceptance pending",
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(entries.items())}}
    entries["playtest-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return {"archive": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "size": output.stat().st_size, "delta_size": len(entries["enhanced/enhanced.patch.gz"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--patched", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_playtest(args.original, args.patched, args.output), indent=2))
