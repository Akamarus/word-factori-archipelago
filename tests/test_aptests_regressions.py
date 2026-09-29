import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

import yaml
from word_factori.word_orders import choose_word_orders

ROOT = Path(__file__).resolve().parents[1]


class APTestsRegressions(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('WF_AP_SOURCE') and os.environ.get('WF_KH_APWORLD'),
                         'opt-in mixed Kingdom Hearts generation')
    def test_slow_mixed_world_seed_generates_with_required_accessibility(self):
        with tempfile.TemporaryDirectory(prefix='wf-mixed-regression-') as temporary:
            output = Path(temporary) / 'result'
            command = [sys.executable, str(ROOT / 'tools/verify_aptests_regressions.py'),
                       '--ap-source', os.environ['WF_AP_SOURCE'], '--output', str(output),
                       '--case', 'ut-38', '--kingdom-hearts', os.environ['WF_KH_APWORLD']]
            if os.environ.get('WF_AP_DEPS'):
                command += ['--dependency-path', os.environ['WF_AP_DEPS']]
            result = subprocess.run(command, capture_output=True, text=True, timeout=90,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            rows = json.loads((output / 'report.json').read_text())
            self.assertEqual(1, len(rows))
            self.assertEqual('pass', rows[0]['status'])
            self.assertEqual(['Word Factori', 'Kingdom Hearts'], rows[0]['games'])

    @unittest.skipUnless(os.environ.get('WF_AP_SOURCE'), 'opt-in real AP accessibility fault')
    def test_runner_rejects_beatable_world_with_unreachable_required_check(self):
        with tempfile.TemporaryDirectory(prefix='wf-aptests-fault-') as temporary:
            output = Path(temporary) / 'result'
            command = [sys.executable, str(ROOT / 'tools/verify_aptests_regressions.py'),
                       '--ap-source', os.environ['WF_AP_SOURCE'], '--output', str(output),
                       '--case', '127', '--fault-inaccessible']
            if os.environ.get('WF_AP_DEPS'):
                command += ['--dependency-path', os.environ['WF_AP_DEPS']]
            result = subprocess.run(command, capture_output=True, text=True, timeout=90,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn('configured accessibility is not satisfied',
                          (output / '127/worker.log').read_text(encoding='utf-8'))

    def test_meta_supports_every_randomized_word_count_including_symbols(self):
        meta = yaml.safe_load((ROOT / 'docs/testing/aptests-meta.yaml').read_text(encoding='utf-8'))
        options = meta['Word Factori']
        self.assertNotIn('type_a_word_checks', options)
        self.assertNotIn('type_a_word_count', options)
        for count in range(1, 21):
            orders = choose_word_orders(options['type_a_word_words'], count, random.Random(42))
            self.assertEqual(count, len(orders))
            self.assertEqual(count, len({order.word for order in orders}))
        self.assertTrue({'99', '()', '++', 'I2'} <= {order.word for order in orders})

    @unittest.skipUnless(os.environ.get('WF_AP_SOURCE'), 'opt-in real AP generation regression')
    def test_exported_progressive_seeds_generate_and_restore_saved_slot_data(self):
        with tempfile.TemporaryDirectory(prefix='wf-aptests-') as temporary:
            output = Path(temporary) / 'result'
            command = [sys.executable, str(ROOT / 'tools/verify_aptests_regressions.py'),
                       '--ap-source', os.environ['WF_AP_SOURCE'], '--output', str(output)]
            if os.environ.get('WF_AP_DEPS'):
                command += ['--dependency-path', os.environ['WF_AP_DEPS']]
            result = subprocess.run(command, capture_output=True, text=True, timeout=180,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            rows = json.loads((output / 'report.json').read_text())
            self.assertEqual({17,117,127,298,326,365,407,431,495}, {row['run'] for row in rows})
            self.assertTrue(all(row['status'] == 'pass' for row in rows))
