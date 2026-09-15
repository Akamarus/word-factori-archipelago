import json
from pathlib import Path
import tempfile
import unittest

from word_factori.bridge import ReceivedItem
from word_factori.client_core import inventory_view
from word_factori import enhanced_runtime as runtime


class QuantityRuntimeTests(unittest.TestCase):
    def test_missing_upgrade_text_keeps_whole_alternative_routes(self):
        from word_factori.quantities import describe_missing, describe_allowances
        text=describe_missing((1,1,0,0,0,0),((2,1,0,0,0,0),(1,2,0,0,0,0)))
        self.assertEqual('1 Bender upgrade or 1 Rotation upgrade',text)
        self.assertEqual('ready',describe_missing((2,1,0,0,0,0),((2,1,0,0,0,0),)))
        self.assertIn('Bender: unlimited',describe_allowances((-1,0,0,0,0,0)))

    def test_inventory_preserves_distinct_tiers_but_not_retransmissions(self):
        items=[ReceivedItem(0,'Progressive Bender Access'),
               ReceivedItem(1,'Progressive Rotation Access'),
               ReceivedItem(2,'Progressive Rotation Access')]
        view=inventory_view(items+items, progressive=True)
        self.assertEqual((1,2,0,0,0,0),view.machine_limits)
        counts=runtime.machine_counts_for_view(view)
        self.assertEqual(1,counts['Bend'])
        self.assertEqual(2,counts['Rotate_cw'])
        self.assertEqual(2,counts['Rotate_ccw'])
        self.assertEqual(-1,counts['IFactory'])
        with self.assertRaises(ValueError):
            inventory_view(items+[ReceivedItem(2,'Progressive Merger2 Access')],progressive=True)

    def test_no_synthetic_bender_or_legacy_item_in_quantity_inventory(self):
        view=inventory_view([ReceivedItem(-1,'Bender Access')],progressive=True)
        self.assertEqual((0,0,0,0,0,0),view.machine_limits)

    def test_finite_publication_has_distinct_context_and_is_idempotent(self):
        view=inventory_view([ReceivedItem(0,'Progressive Bender Access')],progressive=True)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'runtime.json'
            kwargs=dict(machine_counts=runtime.machine_counts_for_view(view), checks_contract='c'*64, progressive=True)
            self.assertTrue(runtime.publish_runtime(path,'a'*64,'b'*64,[{'text':'C','module_counts':{}}],**kwargs))
            self.assertFalse(runtime.publish_runtime(path,'a'*64,'b'*64,[{'text':'C','module_counts':{}}],**kwargs))
            payload=json.loads(path.read_text())
            self.assertEqual(3,payload['schema'])
            self.assertEqual('progressive_machine_enforcement_v1',payload['capability'])
            for bad in (True,5,-2,1.5):
                kwargs['machine_counts']={**kwargs['machine_counts'],'Bend':bad}
                with self.assertRaises(ValueError):
                    runtime.publish_runtime(path,'a'*64,'b'*64,[{'text':'C','module_counts':{}}],**kwargs)
            self.assertEqual(payload,json.loads(path.read_text()))

    def test_shared_direction_allowances_cannot_disagree(self):
        counts=runtime.machine_counts_for_view(inventory_view([],progressive=True))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            runtime.publish_runtime(Path(tmp)/'x','a'*64,'b'*64,[{'text':'C','module_counts':{}}],
                machine_counts={**counts,'Rotate_cw':2,'Rotate_ccw':1},checks_contract='c'*64,progressive=True)
