from collections import Counter
import itertools
import unittest

from tests import test_world_layout as fixtures
from word_factori.quantities import PROGRESSIVE_ITEMS
from word_factori.client_core import resolve_room_campaign


class ProgressiveWorldTests(unittest.TestCase):
    def test_reported_recipe_inventories_match_tracker_and_constructive_logic(self):
        # Native production evidence: docs/feedback-2026-09-16.md.
        cases = (
            ('Bender: [5] -> S', (2,2,0,1,1,1), True),
            ('Bender: [J2] -> S', (2,2,0,1,1,1), False),
            ('Merger2: [3, I] -> B', (1,2,0,1,1,1), True),
            ('Merger2: [4, I] -> H', (1,2,0,1,1,1), True),
        )
        original = self.world(recipe_checks=True)
        restored = fixtures.WorldLayoutTests().make_world(99, passthrough={original.game: original.fill_slot_data()})
        class State:
            def __init__(self, counts): self.counts = dict(zip(PROGRESSIVE_ITEMS, counts))
            def count(self, name, player): return self.counts.get(name, 0)
            # Isolate recipe arithmetic from page access, which has its own tests.
            def can_reach_location(self, *args): return True
        for world in (original, restored):
            world.create_regions()
            for name, inventory, expected in cases:
                with self.subTest(recipe=name, restored=world is restored):
                    self.assertEqual(expected, world.get_location(name).access_rule(State(inventory)))

    def test_start_inventory_from_pool_is_declared_for_archipelago_processing(self):
        self.assertIn('start_inventory_from_pool',fixtures.world_options.WordFactoriOptions.__annotations__)

    def test_fill_orders_own_upgrades_by_viable_path_without_locking_locations(self):
        from word_factori.quantity_layout import upgrade_path
        world=self.world()
        world.create_items()
        pool=[i for i in world.multiworld.itempool if i.name in PROGRESSIVE_ITEMS]
        other=world.create_item('Progressive Rotation Access'); other.player=2
        pool.insert(3,other)
        records={r.stable_key:r for r in world._manifest.levels}
        path=upgrade_path(tuple(records[k] for k in world._layout.ordered_stable_keys))
        self.assertNotEqual(list(path),[i.name for i in pool if i.player==1])
        world.fill_hook(pool,[],[],[])
        self.assertIs(other,pool[3])
        self.assertEqual(list(path),[i.name for i in pool if i.player==1])

    def world(self, **kwargs):
        return fixtures.WorldLayoutTests().make_world(271828, progressive_machines=True, **kwargs)

    def test_core_pool_has_29_upgrades_and_starting_bender(self):
        world = self.world()
        world.create_items()
        counts = Counter(i.name for i in world.multiworld.itempool)
        self.assertEqual(30, sum(counts.values()))
        self.assertEqual(4, counts['Progressive Bender Access'])
        for name in PROGRESSIVE_ITEMS[1:]:
            self.assertEqual(5, counts[name])
        self.assertEqual(['Progressive Bender Access'], [i.name for i in world.multiworld.precollected])
        self.assertFalse(any(name.endswith(' Access') and name not in PROGRESSIVE_ITEMS for name in counts))

    def test_tracker_restores_quantity_mode_even_when_local_option_is_off(self):
        original = self.world(level_set=1, recipe_checks=True, type_a_word_checks=True,
                              type_a_word_count=1, type_a_word_words=['CVC'])
        slot = original.fill_slot_data()
        self.assertIs(slot.get('progressive_machines'), True)
        restored = fixtures.WorldLayoutTests().make_world(9, passthrough={original.game:slot})
        self.assertEqual(slot, restored.fill_slot_data())

    def test_corrupt_or_disabled_quantity_contract_is_rejected(self):
        slot = self.world().fill_slot_data()
        self.assertIn('quantity_catalog_digest', slot)
        for name, value in (('progressive_machines',False),('quantity_catalog_digest','0'*64),
                            ('quantity_model',999),('quantity_budget_digest','0'*64)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                resolve_room_campaign({**slot,name:value})

    def test_recipe_requires_counts_not_only_first_copy(self):
        world = self.world(recipe_checks=True)
        world.create_regions()
        location = world.get_location('Bender: [H] -> A')
        class State:
            inventory = {'Progressive Bender Access':1}
            def count(self, name, player): return self.inventory.get(name,0)
            def has_all(self, *args): return True
            def can_reach_location(self, *args): return True
        state=State()
        self.assertFalse(location.access_rule(state))
        state.inventory={'Progressive Bender Access':1,'Progressive Rotation Access':1,'Progressive Merger3 Access':1}
        self.assertTrue(location.access_rule(state))

    def test_off_pool_remains_unchanged(self):
        world = fixtures.WorldLayoutTests().make_world(2)
        world.create_items()
        self.assertEqual(30, len(world.multiworld.itempool))
        self.assertFalse(any(i.name in PROGRESSIVE_ITEMS for i in world.multiworld.itempool))

    def test_quantity_campaign_does_not_recursively_recheck_previous_locations(self):
        world=self.world()
        world.create_regions()
        class State:
            def count(self,name,player): return 5
            def can_reach_location(self,*args):
                raise AssertionError('quantity campaign should share its page calculation')
        self.assertTrue(world.get_location('PITCHFORK — Final Factory').access_rule(State()))

    def test_starting_page_can_use_the_two_early_upgrades(self):
        class State:
            def count(self,name,player):
                return int(name in {'Progressive Bender Access','Progressive Merger2 Access','Progressive Rotation Access'})
        for seed in range(30):
            world=fixtures.WorldLayoutTests().make_world(seed, progressive_machines=True)
            world.create_regions()
            reachable=[loc for loc in world.selected_locations()[:6] if world.get_location(loc.name).access_rule(State())]
            with self.subTest(seed=seed):
                self.assertGreaterEqual(len(reachable),4)

    def test_tracker_matches_quantities_page_gates_and_victory(self):
        class State:
            def __init__(self,world,counts):
                self.world,self.counts=world,dict(zip(PROGRESSIVE_ITEMS,counts))
            def count(self,name,player): return self.counts.get(name,0)
            def can_reach_location(self,name,player): return self.world.get_location(name).access_rule(self)
        for level_set,goal in itertools.product((0,1),repeat=2):
            original=self.world(level_set=level_set,goal=goal,recipe_checks=True,
                                type_a_word_checks=True,type_a_word_count=1,type_a_word_words=['CVC'])
            restored=fixtures.WorldLayoutTests().make_world(88,passthrough={original.game:original.fill_slot_data()})
            original.create_regions(); restored.create_regions()
            for counts in ((1,0,0,0,0,0),(1,1,0,1,0,0),(2,3,1,2,1,0),(5,5,5,5,5,5)):
                left,right=State(original,counts),State(restored,counts)
                for region in original.multiworld.regions:
                    for loc in region.locations:
                        self.assertEqual(left.can_reach_location(loc.name,1),right.can_reach_location(loc.name,1))
                if counts == (5,5,5,5,5,5):
                    self.assertTrue(left.can_reach_location('Victory',1))
                if counts == (1,0,0,0,0,0):
                    self.assertFalse(left.can_reach_location('Victory',1))
                    self.assertFalse(any(left.can_reach_location(loc.name,1) for loc in original.selected_locations()[6:]))


if __name__ == '__main__':
    unittest.main()
