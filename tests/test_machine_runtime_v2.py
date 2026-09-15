import json
from pathlib import Path
import tempfile
import unittest

from word_factori import enhanced_runtime as runtime
from word_factori.client_core import InventoryView

SAFE = {"IFactory": -1, "Bend": -1, "Rotate_cw": 0, "Rotate_ccw": 0,
        "Reflect_hor": 0, "Reflect_vert": 0, "Merger2": 0, "Merger3": 0, "Merger4": 0}


class MachineRuntimeV2Tests(unittest.TestCase):
    def publish(self, path, **kwargs):
        return runtime.publish_runtime(path, "a" * 64, "b" * 64,
            [{"text": "VV", "module_counts": {}}],
            machine_counts=kwargs.get("counts", SAFE), checks_contract=kwargs.get("contract", "c" * 64))

    def test_publication_binds_complete_machine_inventory_and_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            self.publish(path)
            value = json.loads(path.read_text())
            self.assertEqual(2, value["schema"])
            self.assertEqual("free_word_machine_enforcement_v1", value["capability"])
            self.assertEqual("c" * 64, value["checks_contract"])
            self.assertEqual(SAFE, value["machine_counts"])
            self.assertFalse(self.publish(path))

    def test_incomplete_invalid_inventory_and_contract_never_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            for counts in ({"IFactory": -1}, {**SAFE, "extra": 0},
                           {**SAFE, "Bend": True}, {**SAFE, "Merger2": 1},
                           {**SAFE, "IFactory": 0}):
                with self.assertRaises(ValueError): self.publish(path, counts=counts)
            for contract in ("C" * 64, "x" * 64, None, "c" * 63):
                with self.assertRaises(ValueError): self.publish(path, contract=contract)
            self.assertFalse(path.exists())

    def test_inventory_maps_both_tagged_variants_and_starter_equipment(self):
        self.assertEqual(SAFE, runtime.machine_counts_for_view(InventoryView(set(), 0)))
        actual = runtime.machine_counts_for_view(InventoryView({"Rotation Access", "Merger3 Access"}, 0))
        self.assertEqual({**SAFE, "Rotate_cw": -1, "Rotate_ccw": -1, "Merger3": -1}, actual)

    def test_revision_exhaustion_cannot_publish_an_unsafe_integer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            self.publish(path)
            payload = json.loads(path.read_text())
            payload["revision"] = 9007199254740991
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError): self.publish(path, counts={**SAFE, "Merger2": -1})
            self.assertEqual(payload, json.loads(path.read_text()))
