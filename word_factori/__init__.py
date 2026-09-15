from __future__ import annotations

from copy import deepcopy

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
        REGION_REQUIREMENTS, locations_for_layout,
    )
    from .campaign import campaign_for_level_set
    from .client_core import resolve_room_campaign
    from .layout import ENHANCED_MACHINE_MODEL, build_layout, layout_slot_data
    from .options import CampaignCount, CustomLevelSet, Goal, WordFactoriOptions
    from .requirements import access_rule_for
    from .version import AUTHOR, VERSION
    from . import Components as components


    class WordFactoriItem(Item):
        game = GAME


    class WordFactoriLocation(Location):
        game = GAME


    class WordFactoriWeb(WebWorld):
        game = GAME
        theme = "stone"
        tutorials = [Tutorial("Multiworld Setup Guide", "Install and play Word Factori Archipelago.", "English", "setup_en.md", "setup/en", [AUTHOR])]


    class WordFactoriWorld(World):
        """Build words from I while Archipelago unlocks production machines."""
        game = GAME
        web = WordFactoriWeb()
        options_dataclass = WordFactoriOptions
        options: WordFactoriOptions
        item_name_to_id = ITEM_NAME_TO_ID
        location_name_to_id = LOCATION_NAME_TO_ID
        ut_can_gen_without_yaml = True

        @staticmethod
        def interpret_slot_data(slot_data: dict) -> dict:
            """Give UT the room contract, never a newly randomized approximation."""
            resolved = resolve_room_campaign(slot_data)
            if resolved.layout is None or slot_data.get("progression_model") != ENHANCED_MACHINE_MODEL:
                raise ValueError("Universal Tracker requires a matching 1.4.0-or-newer machine-only room")
            if slot_data.get("level_set") not in ("core_campaign", "discovery_labs"):
                raise ValueError("tracker room level_set is missing or invalid")
            goal = slot_data.get("goal")
            count = slot_data.get("campaign_count")
            if type(goal) is not int or goal not in (Goal.option_campaign_count, Goal.option_final_factory):
                raise ValueError("tracker room goal is missing or invalid")
            if type(count) is not int or not CampaignCount.range_start <= count <= CampaignCount.range_end:
                raise ValueError("tracker room campaign_count is missing or invalid")
            return deepcopy(slot_data)

        def selected_level_set(self) -> str:
            if hasattr(self, "_level_set"):
                return self._level_set
            return "core_campaign" if int(self.options.custom_level_set.value) == 0 else "discovery_labs"

        def selected_locations(self):
            return self._locations

        def generate_early(self) -> None:
            passthrough = getattr(self.multiworld, "re_gen_passthrough", {})
            if GAME in passthrough:
                # UT's RNG and YAML need not match the server. Restore both the
                # native page order and goal before creating locations/rules.
                slot_data = self.interpret_slot_data(passthrough[GAME])
                resolved = resolve_room_campaign(slot_data)
                self._level_set = slot_data["level_set"]
                self.options.custom_level_set = CustomLevelSet.from_any(self._level_set)
                self.options.goal = Goal.from_any(slot_data["goal"])
                self.options.campaign_count = CampaignCount.from_any(slot_data["campaign_count"])
                self._manifest = resolved.manifest
                self._layout = resolved.layout
                self._locations = resolved.locations
            else:
                self._level_set = self.selected_level_set()
                self._manifest = campaign_for_level_set(self._level_set)
                self._layout = build_layout(
                    self._manifest, self._level_set, "shuffled_pages", self.random,
                    integration_mode="enhanced",
                    machine_only=True,
                )
                self._locations = locations_for_layout(self._manifest, self._layout)
            self.multiworld.local_early_items[self.player]["Merger2 Access"] = 1
            self.multiworld.local_early_items[self.player]["Rotation Access"] = 1
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
                    # New rooms use machine/recipe rules at locations; region
                    # names organize content, not additional inventory gates.
                )
            locations = self.selected_locations()
            for data in locations:
                location = WordFactoriLocation(self.player, data.name, data.code, regions[data.region])
                set_rule(location, access_rule_for(data, locations, self.player, integration_mode=self._layout.integration_mode))
                regions[data.region].locations.append(location)
            campaign_goal = int(self.options.goal.value) == 0
            victory_region = menu if campaign_goal else regions["Final Contract"]
            victory = WordFactoriLocation(self.player, "Victory", None, victory_region)
            victory.place_locked_item(WordFactoriItem("Victory", ItemClassification.progression, None, self.player))
            if campaign_goal:
                campaign = tuple(
                    record.name for record in self._manifest.levels
                    if record.kind != "discovery"
                )
                campaign_count = int(self.options.campaign_count.value)
                set_rule(victory, lambda state: sum(state.can_reach_location(name, self.player) for name in campaign) >= campaign_count)
            else:
                final_name = next(
                    record.name for record in self._manifest.levels
                    if record.stable_key == "pitchfork-final"
                )
                set_rule(victory, lambda state: state.can_reach_location(final_name, self.player))
            victory_region.locations.append(victory)
            self.multiworld.regions += [menu, *regions.values()]

        def create_item(self, name: str) -> WordFactoriItem:
            if name == "Victory": return WordFactoriItem(name, ItemClassification.progression, None, self.player)
            classification = ItemClassification.progression if name in MACHINE_ITEMS or name == "Progressive World Access" else ItemClassification.filler
            return WordFactoriItem(name, classification, ITEM_NAME_TO_ID[name], self.player)

        def create_items(self) -> None:
            self.multiworld.itempool += [
                self.create_item(name) for name in ITEM_POOL[:len(self.selected_locations())]
            ]

        def get_filler_item_name(self) -> str:
            return "I Sticker"

        def set_rules(self) -> None:
            self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

        def fill_slot_data(self) -> dict:
            locations = self.selected_locations()
            return {
                **layout_slot_data(self._layout),
                "implementation_version": VERSION,
                "level_set": self._level_set,
                "campaign_id": self._manifest.campaign_id,
                "manifest_version": self._manifest.version,
                "manifest_digest": self._layout.digest,
                "level_count": len(locations),
                "goal": int(self.options.goal.value),
                "campaign_count": int(self.options.campaign_count.value),
                "locations": [
                    {
                        "slot_index": location.slot_index,
                        "stable_key": location.stable_key,
                        "name": location.name,
                        "id": location.code,
                        "kind": location.kind,
                    }
                    for location in locations
                ],
                "mod_folder": "word factori archipelago",
                "reload_required_for_items": self._layout.integration_mode != "enhanced",
            }
