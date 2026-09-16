import unittest
from tests import test_world_layout as fixtures
import word_factori


class StaticGroupTests(unittest.TestCase):
    def test_groups_are_registered_before_generation(self):
        world = word_factori.WordFactoriWorld
        self.assertIn("item_name_groups", vars(world), "item groups must exist at class registration")
        self.assertIn("location_name_groups", vars(world), "location groups must exist at class registration")
        self.assertIn("Bender Access", world.item_name_groups["Machines"])
        self.assertIn("Progressive Bender Access", world.item_name_groups["Machines"])
        self.assertEqual(6, len(world.item_name_groups["Progressive Machines"]))
        self.assertEqual(6, len(world.item_name_groups["Stickers"]))
        self.assertEqual(40, len(world.location_name_groups["Campaign Levels"]))
        self.assertEqual(187, len(world.location_name_groups["Recipe Discoveries"]))
        self.assertEqual(20, len(world.location_name_groups["Word Orders"]))
        for members in world.item_name_groups.values():
            self.assertTrue(set(members) <= world.item_name_to_id.keys())
        for members in world.location_name_groups.values():
            self.assertTrue(set(members) <= world.location_name_to_id.keys())

    def test_optional_settings_and_shuffling_do_not_mutate_groups(self):
        cls = word_factori.WordFactoriWorld
        self.assertIn("location_name_groups", vars(cls))
        before = {key: frozenset(value) for key,value in cls.location_name_groups.items()}
        for seed in (19, 47):
            fixtures.WorldLayoutTests().make_world(seed, recipe_checks=False)
        self.assertEqual(before, cls.location_name_groups)
