import copy
from dataclasses import FrozenInstanceError, replace
import importlib
import unittest
from unittest.mock import patch

from word_factori.campaign import campaign_for_level_set
from word_factori.client_core import InventoryView, ResolvedCampaign
from word_factori.data import locations_for_manifest, MACHINE_ITEMS


class ProgressPresentationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('word_factori.progress_presentation'),
                             'Shared progress presentation is missing')
        self.api = importlib.import_module('word_factori.progress_presentation')
        manifest = campaign_for_level_set('discovery_labs')
        self.campaign = ResolvedCampaign(manifest, None, locations_for_manifest(manifest), False)
        self.inventory = InventoryView(set(MACHINE_ITEMS), 0)

    def build(self, slots=frozenset(), **kwargs):
        return self.api.build_progress(kwargs.pop('campaign', self.campaign),
            kwargs.pop('inventory', self.inventory), local_slots=slots,
            checked=kwargs.pop('checked', frozenset()), pending=kwargs.pop('pending', frozenset()),
            freshness=kwargs.pop('freshness', 'current'), **kwargs)

    def test_server_completion_does_not_unlock_page(self):
        result = self.build(checked=frozenset(l.code for l in self.campaign.locations))
        self.assertEqual(result.rows[6].completion, 'Completed')
        self.assertEqual(result.rows[6].page_status, 'Locked: finish 4 more on page 1')

    def test_four_of_six_and_earliest_blocking_page(self):
        self.assertEqual(self.build(frozenset((0, 2, 5))).rows[6].page_status,
                         'Locked: finish 1 more on page 1')
        result = self.build(frozenset((0, 2, 4, 5, 6, 7)))
        self.assertEqual(result.rows[6].page_status, 'Unlocked in save')
        self.assertEqual(result.rows[18].page_status, 'Locked: finish 2 more on page 2')
        self.assertEqual(self.build().rows[0].page_status, 'Unlocked in save')

    def test_partial_final_page(self):
        result = self.build(frozenset(range(36)))
        self.assertEqual(len(result.rows), 40)
        self.assertEqual((result.rows[-1].page, result.rows[-1].slot), (7, 4))
        self.assertEqual(result.rows[-1].page_status, 'Unlocked in save')

    def test_unknown_save_is_not_locked(self):
        result = self.build(None, freshness='unavailable')
        self.assertTrue(all(r.page_status == 'Save progress unavailable' for r in result.rows))
        self.assertEqual(result.freshness, 'unavailable')

    def test_completion_precedence(self):
        a, b = (l.code for l in self.campaign.locations[:2])
        result = self.build(checked=frozenset((a,)), pending=frozenset((a, b)))
        self.assertEqual([r.completion for r in result.rows[:3]],
                         ['Completed', 'Sending', 'Not completed'])

    def test_normal_alternative_routes(self):
        loc = replace(self.campaign.locations[0], requirement_options=(
            frozenset(('Rotation Access',)), frozenset(('Bender Access', 'Merger2 Access'))))
        campaign = replace(self.campaign, locations=(loc,))
        result = self.build(campaign=campaign, inventory=InventoryView(set(), 0))
        text = result.rows[0].machine_status
        self.assertIn('Rotation', text)
        self.assertIn('Bender + Merger2', text)
        self.assertIn(' or ', text)
        ready = self.build(campaign=campaign, inventory=InventoryView({'Rotation Access'}, 0))
        self.assertEqual(ready.rows[0].machine_status, 'Machines ready')

    def test_progressive_quantities_and_unlimited(self):
        # CC needs one reusable Bender, not two independent factories.
        empty = InventoryView(set(), 0, (0, 0, 0, 0, 0, 0))
        self.assertEqual(self.api.word_machine_status('CC', empty),
                         'Need 1 more Bender upgrade or 1 more Rotation upgrade + 2 more Merger2 upgrades')
        one = InventoryView({'Bender Access'}, 0, (1, 0, 0, 0, 0, 0))
        unlimited = InventoryView(set(MACHINE_ITEMS), 0, (-1,) * 6)
        self.assertEqual(self.api.word_machine_status('CC', one), 'Machines ready')
        self.assertEqual(self.api.word_machine_status('PITCHFORK', unlimited), 'Machines ready')

    def test_lab_restrictions(self):
        loc = replace(self.campaign.locations[0], target='A', kind='discovery',
                      required_route=frozenset(('Bender Access',)))
        result = self.build(campaign=replace(self.campaign, locations=(loc,)),
                            inventory=InventoryView(set(MACHINE_ITEMS), 0, (-1,) * 6))
        self.assertEqual(result.rows[0].kind, 'Campaign lab')
        self.assertEqual(result.rows[0].machine_status, "No verified route under this level's restrictions")

    def test_word_machine_status(self):
        self.assertEqual(self.api.word_machine_status('II', InventoryView(set(), 0)), 'Machines ready')
        self.assertEqual(self.api.word_machine_status('CC', InventoryView(set(), 0)),
                         'Need Bender or Merger2 + Rotation')

    def test_no_io_or_input_mutation(self):
        before = copy.deepcopy(self.campaign)
        with patch('builtins.open', side_effect=AssertionError('unexpected IO')):
            result = self.build()
        self.assertEqual(before, self.campaign)
        self.assertEqual(self.inventory.owned_machines, set(MACHINE_ITEMS))
        with self.assertRaises(FrozenInstanceError):
            result.rows[0].target = 'MUTATED'

    def test_bounds_and_stable_order(self):
        reordered = replace(self.campaign, locations=tuple(reversed(self.campaign.locations)))
        self.assertEqual(self.build(), self.build(campaign=reordered))
        for locations in ((self.campaign.locations[0],) * 2,
                          self.campaign.locations + (self.campaign.locations[0],),
                          (replace(self.campaign.locations[0], slot_index=True),)):
            with self.subTest(locations=len(locations)), self.assertRaises(ValueError):
                self.build(campaign=replace(self.campaign, locations=locations))
        for slots in (frozenset((-1,)), frozenset((40,)), frozenset((True,))):
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                self.build(slots)

    def test_stale_and_empty_routes_never_claim_current_readiness(self):
        result = self.build(freshness='last_known')
        self.assertIn('Last known', result.summary)
        loc = replace(self.campaign.locations[0], requirement_options=())
        result = self.build(campaign=replace(self.campaign, locations=(loc,)))
        self.assertIn('No verified route', result.rows[0].machine_status)
        with self.assertRaises(ValueError):
            self.build(freshness='invented')


if __name__ == '__main__':
    unittest.main()
