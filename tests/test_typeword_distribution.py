import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import build_release, verify_release


class TypeWordDistributionTests(unittest.TestCase):
    def test_built_world_contains_order_logic_and_alphabet_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'word_factori.apworld'
            with patch.object(build_release, 'WORLD_ARCHIVE', destination):
                build_release.write_world()
            with zipfile.ZipFile(destination) as archive:
                self.assertIn('word_factori/word_orders.py', archive.namelist())
                self.assertIn('word_factori/data/alphabet_requirements.json', archive.namelist())

    def test_arbitrary_proprietary_binary_raw_source_and_save_names_are_rejected(self):
        names = ['probe/production.win', 'dump/CodeEntries/native.gml', 'player.save',
                 'data.wf-ap-original.win', 'probe-tools/results.json']
        self.assertEqual(names, verify_release.find_prohibited_release_entries(names))
        for name in names:
            self.assertFalse(build_release.include(build_release.ROOT / name))
