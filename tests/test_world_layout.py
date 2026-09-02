import importlib
import random
import sys
import types
import unittest


class _Item:
    def __init__(self, name, classification, code, player):
        self.name = name
        self.classification = classification
        self.code = code
        self.player = player


class _Location:
    def __init__(self, player, name, code, parent):
        self.player = player
        self.name = name
        self.code = code
        self.parent = parent
        self.access_rule = lambda state: True
        self.item = None

    def place_locked_item(self, item):
        self.item = item


class _Entrance:
    def __init__(self, target, name, access_rule):
        self.target = target
        self.name = name
        self.access_rule = access_rule


class _Region:
    def __init__(self, name, player, multiworld):
        self.name = name
        self.player = player
        self.multiworld = multiworld
        self.locations = []
        self.exits = []

    def connect(self, target, name, access_rule=None):
        self.exits.append(_Entrance(target, name, access_rule or (lambda state: True)))


class _World:
    def __init__(self, multiworld, player):
        self.multiworld = multiworld
        self.player = player
        self.random = multiworld.random


class _Choice:
    pass


class _Range:
    pass


class _PerGameCommonOptions:
    pass


def _install_archipelago_stubs():
    base_classes = types.ModuleType("BaseClasses")
    base_classes.Item = _Item
    base_classes.ItemClassification = types.SimpleNamespace(
        progression="progression", filler="filler"
    )
    base_classes.Location = _Location
    base_classes.Region = _Region
    base_classes.Tutorial = lambda *args, **kwargs: (args, kwargs)

    auto_world = types.ModuleType("worlds.AutoWorld")
    auto_world.WebWorld = type("WebWorld", (), {})
    auto_world.World = _World

    rules = types.ModuleType("worlds.generic.Rules")
    rules.set_rule = lambda location, rule: setattr(location, "access_rule", rule)

    generic = types.ModuleType("worlds.generic")
    generic.__path__ = []
    worlds = types.ModuleType("worlds")
    worlds.__path__ = []

    launcher = types.ModuleType("worlds.LauncherComponents")
    launcher.Component = lambda *args, **kwargs: (args, kwargs)
    launcher.Type = types.SimpleNamespace(CLIENT="client")
    launcher.components = []
    launcher.launch = lambda *args, **kwargs: None

    options = types.ModuleType("Options")
    options.Choice = _Choice
    options.PerGameCommonOptions = _PerGameCommonOptions
    options.Range = _Range

    sys.modules.update({
        "BaseClasses": base_classes,
        "Options": options,
        "worlds": worlds,
        "worlds.AutoWorld": auto_world,
        "worlds.generic": generic,
        "worlds.generic.Rules": rules,
        "worlds.LauncherComponents": launcher,
    })


_install_archipelago_stubs()
import word_factori

word_factori = importlib.reload(word_factori)

from word_factori.campaign import campaign_for_level_set
from word_factori.data import BASE_ID
from word_factori import options as world_options


class _MultiWorld:
    def __init__(self, seed):
        self.random = random.Random(seed)
        self.regions = []
        self.itempool = []
        self.completion_condition = {}
        self.precollected = []

    def push_precollected(self, item):
        self.precollected.append(item)


class _OptionValue:
    def __init__(self, value):
        self.value = value


class _ReachabilityState:
    def __init__(self, reachable):
        self.reachable = set(reachable)

    def can_reach_location(self, name, player):
        return name in self.reachable


class WorldLayoutTests(unittest.TestCase):
    def make_world(self, seed, *, campaign_layout=1, level_set=0, goal=0):
        multiworld = _MultiWorld(seed)
        world = word_factori.WordFactoriWorld(multiworld, 1)
        world.options = types.SimpleNamespace(
            campaign_layout=_OptionValue(campaign_layout),
            custom_level_set=_OptionValue(level_set),
            goal=_OptionValue(goal),
            campaign_count=_OptionValue(25),
        )
        world.generate_early()
        return world

    def victory_location(self, world):
        world.create_regions()
        return next(
            location
            for region in world.multiworld.regions
            for location in region.locations
            if location.name == "Victory"
        )

    def test_campaign_layout_option_defaults_to_shuffled_pages(self):
        option = world_options.CampaignLayoutOption
        self.assertEqual(0, option.option_fixed_pages)
        self.assertEqual(1, option.option_shuffled_pages)
        self.assertEqual(1, option.default)

    def test_slot_data_describes_authoritative_native_layout(self):
        slot_data = self.make_world(104729).fill_slot_data()

        self.assertEqual("four_of_six_v1", slot_data["progression_model"])
        self.assertEqual(6, slot_data["page_size"])
        self.assertEqual(4, slot_data["page_unlock_count"])
        self.assertEqual(slot_data["manifest_digest"], slot_data["layout_digest"])
        self.assertEqual(
            list(range(len(slot_data["locations"]))),
            [entry["slot_index"] for entry in slot_data["locations"]],
        )
        self.assertEqual(
            {BASE_ID + 1000 + index for index in range(len(slot_data["locations"]))},
            {entry["id"] for entry in slot_data["locations"]},
        )
        self.assertEqual(
            slot_data["level_order"],
            [entry["stable_key"] for entry in slot_data["locations"]],
        )

    def test_slot_data_is_seed_deterministic_and_changes_across_seeds(self):
        first = self.make_world(65537).fill_slot_data()
        repeated = self.make_world(65537).fill_slot_data()
        other = self.make_world(65539).fill_slot_data()

        self.assertEqual(first, repeated)
        self.assertNotEqual(first["level_order"], other["level_order"])

    def test_generate_early_caches_one_layout_for_later_world_methods(self):
        world = self.make_world(31337)
        locations = world.selected_locations()
        first = world.fill_slot_data()
        for _ in range(100):
            world.random.random()
        self.assertIs(locations, world.selected_locations())
        self.assertEqual(first, world.fill_slot_data())

    def test_fixed_layout_option_preserves_canonical_level_order(self):
        slot_data = self.make_world(7, campaign_layout=0).fill_slot_data()
        manifest = campaign_for_level_set("core_campaign")
        self.assertEqual(
            [record.stable_key for record in manifest.levels],
            slot_data["level_order"],
        )

    def test_campaign_count_goal_counts_only_canonical_non_discovery_names(self):
        world = self.make_world(101, level_set=1, goal=0)
        victory = self.victory_location(world)
        manifest = campaign_for_level_set("discovery_labs")
        canonical = [record.name for record in manifest.levels if record.kind != "discovery"]
        discoveries = [record.name for record in manifest.levels if record.kind == "discovery"]

        self.assertTrue(victory.access_rule(_ReachabilityState(canonical[:25])))
        self.assertFalse(
            victory.access_rule(_ReachabilityState([*canonical[:24], *discoveries]))
        )

    def test_final_factory_goal_uses_stable_pitchfork_location_name(self):
        world = self.make_world(103, level_set=1, goal=1)
        victory = self.victory_location(world)
        manifest = campaign_for_level_set("discovery_labs")
        final_name = next(
            record.name for record in manifest.levels
            if record.stable_key == "pitchfork-final"
        )

        self.assertTrue(victory.access_rule(_ReachabilityState({final_name})))
        self.assertFalse(victory.access_rule(_ReachabilityState(set())))


if __name__ == "__main__":
    unittest.main()
