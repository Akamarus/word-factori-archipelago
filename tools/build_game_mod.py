import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from word_factori.mod import render_levels, write_campaign_identity, write_levels


OUTPUT = ROOT / "game_mod" / "word factori archipelago" / "levels.json"
IDENTITY_OUTPUT = ROOT / "game_mod" / "word factori archipelago" / "archipelago_campaign.json"


if __name__ == "__main__":
    write_levels(OUTPUT, render_levels({"Bender Access"}, 0))
    write_campaign_identity(IDENTITY_OUTPUT)
    print(f"Wrote {OUTPUT}")
    print(f"Wrote {IDENTITY_OUTPUT}")
