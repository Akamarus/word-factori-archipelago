"""Synthetic graph tests; no proprietary recipe data in test fixtures."""
import unittest

from tools.build_alphabet_catalog import build_native_catalog
from word_factori.symbols import TARGET_CHARACTERS, TARGET_TOKENS


class SymbolCatalogBuilderTests(unittest.TestCase):
    def table(self):
        return {'snapshots': {'edges': [
            {'machine': 'oBend', 'inputs': ['I'], 'output': TARGET_TOKENS[c]}
            for c in TARGET_CHARACTERS if c != 'I'
        ]}}

    def test_all_symbols_use_native_output_aliases_and_minimal_capabilities(self):
        result = build_native_catalog(self.table())
        self.assertEqual(2, result['version'])
        self.assertEqual(set(TARGET_CHARACTERS), set(result['alphabet']))
        self.assertEqual([[]], result['alphabet']['I'])
        self.assertEqual([['Bender Access']], result['alphabet']['9'])
        self.assertEqual([['Bender Access']], result['alphabet']['🔑'])

    def test_unreachable_cycle_does_not_create_a_route(self):
        native = self.table()
        native['snapshots']['edges'] = [e for e in native['snapshots']['edges'] if e['output'] != '62']
        native['snapshots']['edges'].append({'machine': 'oMerger2', 'inputs': ['62', 'I'], 'output': '62'})
        with self.assertRaisesRegex(ValueError, 'No native route to 9'):
            build_native_catalog(native)

    def test_failed_native_probe_is_not_accepted(self):
        native = self.table()
        native['failure'] = 'runtime error'
        with self.assertRaisesRegex(ValueError, 'probe failed'):
            build_native_catalog(native)
