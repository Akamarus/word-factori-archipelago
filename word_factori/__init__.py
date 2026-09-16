from __future__ import annotations

from copy import deepcopy
from collections import Counter, defaultdict, deque

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
        REGION_REQUIREMENTS, locations_for_layout, STICKER_NAMES,
    )
    from .campaign import campaign_for_level_set
    from .client_core import resolve_room_campaign
    from .layout import ENHANCED_MACHINE_MODEL, RECIPE_MODEL, WORD_ORDER_MODEL, build_layout, layout_slot_data
    from .options import (
        CampaignCount, CustomLevelSet, Goal, RecipeChecks, TypeAWordChecks,
        TypeAWordCount, TypeAWordWords, WordFactoriOptions,
        ProgressiveMachines,
    )
    from .recipe_checks import RECIPE_CATALOG_DIGEST, RECIPE_CHECKS
    from .requirements import access_rule_for
    from .word_orders import (
        WORD_ORDER_NAME_TO_ID, choose_word_orders, orders_slot_data,
    )
    from .version import AUTHOR, VERSION
    from .quantities import PROGRESSIVE_ITEMS, QUANTITY_MODEL
    from .quantity_contract import check_budgets, quantity_rule, quantity_slot_data, campaign_quantity_rules
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
        location_name_to_id = {
            **LOCATION_NAME_TO_ID,
            **{check.name: check.code for check in RECIPE_CHECKS},
            **WORD_ORDER_NAME_TO_ID,
        }
        item_name_groups = {
            "Machines": set(MACHINE_ITEMS) | set(PROGRESSIVE_ITEMS),
            "Progressive Machines": set(PROGRESSIVE_ITEMS),
            "Stickers": set(STICKER_NAMES),
        }
        location_name_groups = {
            "Campaign Levels": set(LOCATION_NAME_TO_ID),
            "Recipe Discoveries": {check.name for check in RECIPE_CHECKS},
            "Word Orders": set(WORD_ORDER_NAME_TO_ID),
        }
        ut_can_gen_without_yaml = True

        @staticmethod
        def interpret_slot_data(slot_data: dict) -> dict:
            """Give UT the room contract, never a newly randomized approximation."""
            resolved = resolve_room_campaign(slot_data)
            if resolved.layout is None or slot_data.get("progression_model") not in {ENHANCED_MACHINE_MODEL, RECIPE_MODEL, WORD_ORDER_MODEL, QUANTITY_MODEL}:
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
                self.options.recipe_checks = RecipeChecks.from_any(slot_data.get("recipe_checks", False))
                self.options.progressive_machines = ProgressiveMachines.from_any(resolved.progressive_machines)
                self.options.type_a_word_checks = TypeAWordChecks.from_any(bool(resolved.word_orders))
                self.options.type_a_word_count = TypeAWordCount.from_any(len(resolved.word_orders) or TypeAWordCount.default)
                self.options.type_a_word_words = TypeAWordWords.from_any([order.word for order in resolved.word_orders])
                self._manifest = resolved.manifest
                self._layout = resolved.layout
                self._locations = resolved.locations
                self.word_orders = resolved.word_orders
            else:
                self._level_set = self.selected_level_set()
                self._manifest = campaign_for_level_set(self._level_set)
                if bool(self.options.type_a_word_checks.value):
                    try:
                        self.word_orders = choose_word_orders(
                            self.options.type_a_word_words.value,
                            self.options.type_a_word_count.value,
                            self.random,
                        )
                    except (TypeError, ValueError) as error:
                        raise ValueError(
                            f"Type-a-Word options for player {self.player} are invalid: {error}"
                        ) from error
                else:
                    self.word_orders = ()
                self._layout = build_layout(
                    self._manifest, self._level_set, "shuffled_pages", self.random,
                    integration_mode="enhanced",
                    machine_only=True,
                    recipe_checks=bool(self.options.recipe_checks.value),
                    type_a_word_checks=bool(self.word_orders),
                    progressive_machines=bool(self.options.progressive_machines.value),
                )
                self._locations = locations_for_layout(self._manifest, self._layout)
            self._quantity_budgets = (check_budgets(self._locations, self.word_orders, bool(self.options.recipe_checks.value))
                                      if self.options.progressive_machines.value else None)
            prefix = 'Progressive ' if self._quantity_budgets is not None else ''
            self.multiworld.local_early_items[self.player][prefix + "Merger2 Access"] = 1
            self.multiworld.local_early_items[self.player][prefix + "Rotation Access"] = 1
            self.multiworld.push_precollected(self.create_item(prefix + "Bender Access"))

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
            quantity_rules = (campaign_quantity_rules(locations, self._quantity_budgets, self.player)
                              if self._quantity_budgets is not None else {})
            for data in locations:
                location = WordFactoriLocation(self.player, data.name, data.code, regions[data.region])
                set_rule(location, access_rule_for(data, locations, self.player, integration_mode=self._layout.integration_mode,
                    quantity_budgets=self._quantity_budgets[data.code] if self._quantity_budgets is not None else None))
                if quantity_rules:
                    set_rule(location, quantity_rules[data.code])
                regions[data.region].locations.append(location)
            if bool(self.options.recipe_checks.value):
                journal = Region("Recipe Journal", self.player, self.multiworld)
                menu.connect(journal, "Open Recipe Journal")
                i_factory = next(data.name for data in locations if data.stable_key == "complete-i")
                for check in RECIPE_CHECKS:
                    location = WordFactoriLocation(self.player, check.name, check.code, journal)
                    set_rule(location, lambda state, options=check.requirement_options: (
                        state.can_reach_location(i_factory, self.player)
                        and any(state.has_all(option, self.player) for option in options)
                    ))
                    if self._quantity_budgets is not None:
                        check_rule = quantity_rule(self._quantity_budgets[check.code], self.player)
                        set_rule(location, lambda state, rule=check_rule: state.can_reach_location(i_factory,self.player) and rule(state))
                    journal.locations.append(location)
                regions["Recipe Journal"] = journal
            for order in self.word_orders:
                region_name = f"Word Order: {order.word}"
                order_region = Region(region_name, self.player, self.multiworld)
                menu.connect(order_region, f"Open {region_name}")
                location = WordFactoriLocation(
                    self.player, order.name, order.code, order_region,
                )
                set_rule(location, lambda state, routes=order.requirements: any(
                    all(state.has(capability, self.player) for capability in route)
                    for route in routes
                ))
                if self._quantity_budgets is not None:
                    set_rule(location, quantity_rule(self._quantity_budgets[order.code], self.player))
                order_region.locations.append(location)
                regions[region_name] = order_region
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
            classification = ItemClassification.progression if name in (*MACHINE_ITEMS, *PROGRESSIVE_ITEMS) or name == "Progressive World Access" else ItemClassification.filler
            return WordFactoriItem(name, classification, ITEM_NAME_TO_ID[name], self.player)

        def create_items(self) -> None:
            count = (
                len(self.selected_locations())
                + (len(RECIPE_CHECKS) if bool(self.options.recipe_checks.value) else 0)
                + len(self.word_orders)
            )
            if self._quantity_budgets is not None:
                pool = [item for index,item in enumerate(PROGRESSIVE_ITEMS) for _ in range(4 if index == 0 else 5)]
                if len(pool) > count:
                    raise ValueError('progressive machines require at least 29 locations')
                self.multiworld.itempool += [self.create_item(name) for name in pool + ['I Sticker'] * (count-len(pool))]
                return
            self.multiworld.itempool += [self.create_item(name) for name in (
                list(ITEM_POOL[:len(self.selected_locations())]) + ["I Sticker"] * (count - len(self.selected_locations()))
            )]

        def get_filler_item_name(self) -> str:
            return "I Sticker"

        def fill_hook(self, progitempool, usefulitempool, filleritempool, fill_locations):
            if self._quantity_budgets is None:
                return
            from .quantity_layout import upgrade_path
            records = {record.stable_key:record for record in self._manifest.levels}
            path = upgrade_path(tuple(records[key] for key in self._layout.ordered_stable_keys))
            if path is None:
                raise ValueError('Progressive campaign has no verified upgrade path')
            positions = [i for i,item in enumerate(progitempool)
                         if item.player == self.player and item.name in PROGRESSIVE_ITEMS]
            available = defaultdict(deque)
            for i in positions:
                available[progitempool[i].name].append(progitempool[i])
            # Early placement and configured starting inventory already removed
            # some copies. Skip those earliest tiers in the constructive path.
            skipped = Counter(path)
            for name,items in available.items():
                skipped[name] -= len(items)
            ordered = []
            for name in path:
                if skipped[name] > 0:
                    skipped[name] -= 1
                elif available[name]:
                    ordered.append(available[name].popleft())
            if len(ordered) != len(positions):
                raise ValueError('Progressive item pool exceeds its verified path')
            # AP fills in reverse order. Keep its shuffled locations and every
            # other player's item positions; this never preplaces a check.
            for index,item in zip(positions,ordered):
                progitempool[index] = item

        def set_rules(self) -> None:
            self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

        def fill_slot_data(self) -> dict:
            locations = self.selected_locations()
            recipe_checks = bool(self.options.recipe_checks.value)
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
                "recipe_checks": recipe_checks,
                **({"recipe_catalog_digest": RECIPE_CATALOG_DIGEST} if recipe_checks else {}),
                **orders_slot_data(self.word_orders),
                **quantity_slot_data(bool(self.options.progressive_machines.value), locations, self.word_orders, recipe_checks),
            }
