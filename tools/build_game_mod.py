import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from word_factori.campaign import campaign_for_level_set
from word_factori.data import locations_for_layout
from word_factori.layout import fixed_layout
from word_factori.mod import render_levels, write_campaign_identity, write_levels


OUTPUT = ROOT / "game_mod" / "word factori archipelago" / "levels.json"
IDENTITY_OUTPUT = ROOT / "game_mod" / "word factori archipelago" / "archipelago_campaign.json"


if __name__ == "__main__":
    manifest = campaign_for_level_set("discovery_labs")
    layout = fixed_layout(manifest, "discovery_labs")
    locations = locations_for_layout(manifest, layout)
    write_levels(OUTPUT, render_levels({"Bender Access"}, 0, locations=locations))
    write_campaign_identity(IDENTITY_OUTPUT, manifest, layout)
    print(f"Wrote {OUTPUT}")
    print(f"Wrote {IDENTITY_OUTPUT}")
