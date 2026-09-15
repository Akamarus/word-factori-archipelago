import importlib
import copy
import itertools
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
    def __init__(self, value):
        self.value = value

    @classmethod
    def from_any(cls, value):
        if isinstance(value, str):
            value = getattr(cls, "option_" + value)
        return cls(value)


class _Range(_Choice):
    pass

class _DefaultOnToggle(_Choice):
    default = 1


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
    options.DefaultOnToggle = _DefaultOnToggle

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
        self.local_early_items = {1: {}}

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
    def test_recipe_checks_default_on(self):
        self.assertEqual(1, world_options.RecipeChecks.default)

    def make_world(self, seed, *, campaign_layout=1, level_set=0, goal=0, integration_mode=0, recipe_checks=False, passthrough=None):
        multiworld = _MultiWorld(seed)
        if passthrough is not None:
            multiworld.re_gen_passthrough = passthrough
        world = word_factori.WordFactoriWorld(multiworld, 1)
        world.options = types.SimpleNamespace(
            campaign_layout=_OptionValue(campaign_layout),
            custom_level_set=_OptionValue(level_set),
            goal=_OptionValue(goal),
            campaign_count=_OptionValue(25),
            integration_mode=_OptionValue(integration_mode),
            recipe_checks=_OptionValue(recipe_checks),
        )
        world.generate_early()
        return world

    def test_tracker_restores_room_layout_options_and_ids_without_using_rng(self):
        for level_set in (0, 1):
            for goal in (0, 1):
                with self.subTest(level_set=level_set, goal=goal):
                    original = self.make_world(104729, level_set=level_set, goal=goal)
                    original.options.campaign_count.value = 29
                    slot = original.fill_slot_data()
                    passthrough = word_factori.WordFactoriWorld.interpret_slot_data(slot)
                    restored = self.make_world(65539, level_set=1-level_set, goal=1-goal,
                                              passthrough={original.game: passthrough})
                    self.assertTrue(restored.ut_can_gen_without_yaml)
                    self.assertEqual(original.selected_locations(), restored.selected_locations())
                    self.assertEqual(slot, restored.fill_slot_data())
                    self.assertEqual(random.Random(65539).getstate(), restored.random.getstate())
                    self.assertEqual(1, len(restored.multiworld.precollected))
                    victory = self.victory_location(restored)
                    campaign = [r.name for r in original._manifest.levels if r.kind != "discovery"]
                    if goal == 0:
                        self.assertFalse(victory.access_rule(_ReachabilityState(campaign[:28])))
                        self.assertTrue(victory.access_rule(_ReachabilityState(campaign[:29])))
                    else:
                        final = next(r.name for r in original._manifest.levels if r.stable_key == "pitchfork-final")
                        self.assertTrue(victory.access_rule(_ReachabilityState({final})))
                        self.assertFalse(victory.access_rule(_ReachabilityState(set())))

    def test_tracker_rejects_invalid_room_instead_of_shuffling_a_replacement(self):
        slot = self.make_world(13).fill_slot_data()
        for field, value in (("layout_digest", "bad"), ("manifest_digest", "bad"),
                             ("level_order", []), ("goal", None), ("goal", True),
                             ("goal", 2), ("campaign_count", 19), ("campaign_count", 31),
                             ("campaign_count", True), ("level_set", None),
                             ("progression_model", "enhanced_four_of_six_v1")):
            with self.subTest(field=field, value=value):
                invalid = {**slot, field: value}
                with self.assertRaises(ValueError):
                    word_factori.WordFactoriWorld.interpret_slot_data(invalid)
                with self.assertRaises(ValueError):
                    self.make_world(17, passthrough={word_factori.GAME: invalid})
        for field in ("goal", "campaign_count", "level_set", "progression_model"):
            invalid = {k: v for k, v in slot.items() if k != field}
            with self.subTest(missing=field), self.assertRaises(ValueError):
                word_factori.WordFactoriWorld.interpret_slot_data(invalid)

    def test_tracker_payload_is_detached_and_other_games_do_not_affect_generation(self):
        slot = self.make_world(31).fill_slot_data()
        saved = copy.deepcopy(slot)
        payload = word_factori.WordFactoriWorld.interpret_slot_data(slot)
        payload["level_order"].reverse()
        self.assertEqual(saved, slot)
        self.assertEqual(saved, self.make_world(31, passthrough={"Other Game": {}}).fill_slot_data())

    def test_tracker_and_generated_world_agree_for_every_machine_inventory(self):
        for level_set in (0, 1):
            original = self.make_world(43, level_set=level_set)
            restored = self.make_world(71, passthrough={original.game: original.fill_slot_data()})
            original.create_regions()
            restored.create_regions()
            machines = tuple(word_factori.MACHINE_ITEMS)
            class State:
                def __init__(self, world, owned):
                    self.owned = owned
                    self.locations = {loc.name: loc for reg in world.multiworld.regions for loc in reg.locations}
                    self.cache = {}
                def has_all(self, needs, player):
                    return set(needs) <= self.owned
                def can_reach_location(self, name, player):
                    if name not in self.cache:
                        self.cache[name] = self.locations[name].access_rule(self)
                    return self.cache[name]
            for mask in itertools.product((False, True), repeat=len(machines)):
                owned = {machine for machine, enabled in zip(machines, mask) if enabled}
                expected, actual = State(original, owned), State(restored, owned)
                for name in expected.locations:
                    with self.subTest(level_set=level_set, inventory=owned, location=name):
                        self.assertEqual(expected.can_reach_location(name, 1), actual.can_reach_location(name, 1))

    def test_every_page_requires_four_of_its_own_previous_page_not_four_anywhere(self):
        for level_set in (0, 1):
            world = self.make_world(47, level_set=level_set)
            world.create_regions()
            locations = world.selected_locations()
            by_name = {loc.name: loc for reg in world.multiworld.regions for loc in reg.locations}
            class State(_ReachabilityState):
                def has_all(self, needs, player): return True
            for page_start in range(6, len(locations), 6):
                preceding = [loc.name for loc in locations[page_start-6:page_start]]
                unrelated = {loc.name for loc in locations if loc.name not in preceding}
                for chosen in itertools.combinations(preceding, 4):
                    for target in locations[page_start:page_start+6]:
                        rule = by_name[target.name].access_rule
                        self.assertFalse(rule(State(unrelated | set(chosen[:3]))))
                        self.assertTrue(rule(State(chosen)))

    def test_enhanced_room_emits_matching_rules_and_contract(self):
        world = self.make_world(29, integration_mode=1)
        world.create_regions()
        slot = world.fill_slot_data()
        self.assertEqual("enhanced", slot["integration_mode"])
        self.assertEqual(4, slot["tutorial_page_unlock_count"])
        self.assertFalse(slot["reload_required_for_items"])
        class State:
            def has_all(self, needs, player): return True
            def can_reach_location(self, name, player): return False
        by_name = {loc.name: loc for reg in world.multiworld.regions for loc in reg.locations}
        for data in world.selected_locations()[:6]:
            self.assertTrue(by_name[data.name].access_rule(State()))

    def victory_location(self, world):
        world.create_regions()
        return next(
            location
            for region in world.multiworld.regions
            for location in region.locations
            if location.name == "Victory"
        )

    def test_slot_data_describes_authoritative_native_layout(self):
        slot_data = self.make_world(104729).fill_slot_data()

        self.assertIs(slot_data["recipe_checks"], False)
        self.assertEqual("machines_enhanced_four_of_six_v1", slot_data["progression_model"])
        self.assertEqual(6, slot_data["page_size"])
        self.assertEqual("enhanced", slot_data["integration_mode"])
        self.assertEqual(4, slot_data["tutorial_page_unlock_count"])
        self.assertEqual(4, slot_data["later_page_unlock_count"])
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

    def test_recipe_checks_add_187_locations_and_fillers_without_changing_native_count(self):
        for level_set, expected in ((0, 217), (1, 227)):
            world = self.make_world(104729, level_set=level_set, recipe_checks=True)
            world.create_regions()
            world.create_items()
            slot = world.fill_slot_data()
            self.assertEqual(expected, len(world.multiworld.itempool))
            self.assertEqual(30 if level_set == 0 else 40, slot["level_count"])
            self.assertEqual(expected, sum(len(region.locations) for region in world.multiworld.regions) - 1)

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

    def test_generate_early_requests_two_local_early_starter_rewards(self):
        world = self.make_world(31339)

        self.assertEqual(
            {"Merger2 Access": 1, "Rotation Access": 1},
            world.multiworld.local_early_items[world.player],
        )

    def test_obsolete_option_attributes_cannot_generate_a_second_mode(self):
        slot_data = self.make_world(7, campaign_layout=0).fill_slot_data()
        self.assertEqual("enhanced_balanced_pages_v1", slot_data["layout_algorithm"])
        self.assertEqual("enhanced", slot_data["integration_mode"])

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
