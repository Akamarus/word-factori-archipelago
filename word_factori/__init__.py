from __future__ import annotations

try:
    from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
except ModuleNotFoundError as error:
    if error.name != "BaseClasses":
        raise
else:
    from worlds.AutoWorld import WebWorld, World
    from worlds.generic.Rules import set_rule

    from .data import (
        CAMPAIGN_DIGEST, CAMPAIGN_ID, CAMPAIGN_VERSION, GAME, ITEM_NAME_TO_ID,
        ITEM_NAMES, ITEM_POOL, LOCATIONS, LOCATION_NAME_TO_ID, MACHINE_ITEMS,
        REGION_REQUIREMENTS,
    )
    from .options import WordFactoriOptions
    from .requirements import access_rule_for
    from . import Components as components


    class WordFactoriItem(Item):
        game = GAME


    class WordFactoriLocation(Location):
        game = GAME


    class WordFactoriWeb(WebWorld):
        game = GAME
        theme = "stone"
        tutorials = [Tutorial("Multiworld Setup Guide", "Install and play Word Factori Archipelago.", "English", "setup_en.md", "setup/en", ["OpenAI"])]


    class WordFactoriWorld(World):
        """Build words from I while Archipelago unlocks machines and campaign worlds."""
        game = GAME
        web = WordFactoriWeb()
        options_dataclass = WordFactoriOptions
        options: WordFactoriOptions
        item_name_to_id = ITEM_NAME_TO_ID
        location_name_to_id = LOCATION_NAME_TO_ID

        def generate_early(self) -> None:
            self.multiworld.push_precollected(self.create_item("Bender Access"))

        def create_regions(self) -> None:
            menu = Region("Menu", self.player, self.multiworld)
            regions = {name: Region(name, self.player, self.multiworld) for name in REGION_REQUIREMENTS}
            menu.connect(regions["Starter Workshop"], "Enter Starter Workshop")
            starter = regions["Starter Workshop"]
            for region_name, tier in REGION_REQUIREMENTS.items():
                if region_name == "Starter Workshop": continue
                starter.connect(
                    regions[region_name],
                    f"Open {region_name}",
                    lambda state, count=tier: state.has("Progressive World Access", self.player, count),
                )
            for data in LOCATIONS:
                location = WordFactoriLocation(self.player, data.name, data.code, regions[data.region])
                set_rule(location, access_rule_for(data, self.player))
                regions[data.region].locations.append(location)
            campaign_goal = int(self.options.goal.value) == 0
            victory_region = menu if campaign_goal else regions["Final Contract"]
            victory = WordFactoriLocation(self.player, "Victory", None, victory_region)
            victory.place_locked_item(WordFactoriItem("Victory", ItemClassification.progression, None, self.player))
            if campaign_goal:
                campaign = tuple(location.name for location in LOCATIONS[:30])
                campaign_count = int(self.options.campaign_count.value)
                set_rule(victory, lambda state: sum(state.can_reach_location(name, self.player) for name in campaign) >= campaign_count)
            else:
                set_rule(victory, lambda state: state.can_reach_location("PITCHFORK — Final Factory", self.player))
            victory_region.locations.append(victory)
            self.multiworld.regions += [menu, *regions.values()]

        def create_item(self, name: str) -> WordFactoriItem:
            if name == "Victory": return WordFactoriItem(name, ItemClassification.progression, None, self.player)
            classification = ItemClassification.progression if name in MACHINE_ITEMS or name == "Progressive World Access" else ItemClassification.filler
            return WordFactoriItem(name, classification, ITEM_NAME_TO_ID[name], self.player)

        def create_items(self) -> None:
            self.multiworld.itempool += [self.create_item(name) for name in ITEM_POOL]

        def get_filler_item_name(self) -> str:
            return "I Sticker"

        def set_rules(self) -> None:
            self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

        def fill_slot_data(self) -> dict:
            return {
                "implementation_version": "1.1.0",
                "campaign_id": CAMPAIGN_ID,
                "manifest_version": CAMPAIGN_VERSION,
                "manifest_digest": CAMPAIGN_DIGEST,
                "goal": int(self.options.goal.value),
                "campaign_count": int(self.options.campaign_count.value),
                "locations": [{"index": x.index, "name": x.name, "id": x.code, "kind": x.kind} for x in LOCATIONS],
                "mod_folder": "word factori archipelago",
                "reload_required_for_items": True,
            }
