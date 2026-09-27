import unittest
import zipfile
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from tools import build_release

ROOT = Path(__file__).resolve().parents[1]


class ReleasePolishDocsTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('WF_AP_SOURCE'), 'real AP example generation requires WF_AP_SOURCE')
    def test_both_shipped_yaml_examples_generate_with_real_options(self):
        # Separate interpreter: unit tests install intentionally lightweight AP stubs.
        script = """
import os, shutil, sys
from pathlib import Path
from tools import verify_connected_multiworld as r
run=Path(sys.argv[1])/'run'
r.create_run_directory(run)
r.stage_core(Path(os.environ['WF_AP_SOURCE']),run/'ap')
shutil.copyfile(r.ROOT/'word_factori.apworld',run/'word_factori.apworld')
r.player_yaml=lambda name, progressive: (r.ROOT/'examples'/('WordFactoriProgressive.yaml' if progressive else 'WordFactori.yaml')).read_text(encoding='utf-8')
world,wf=r.worker_setup(run,os.environ.get('WF_AP_DEPS'),160931)
assert len(world.worlds)==2
assert world.worlds[2].options.progressive_machines.value
assert len(world.worlds[2].fill_slot_data()['word_orders'])==3
"""
        with tempfile.TemporaryDirectory(prefix='wf-examples-') as temp:
            result = subprocess.run([sys.executable, '-c', script, temp], cwd=ROOT, capture_output=True,
                                    text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout[-2000:]+result.stderr[-8000:])

    def test_examples_offer_normal_and_complete_optional_setup(self):
        normal = yaml.safe_load((ROOT / 'examples/WordFactori.yaml').read_text())['Word Factori']
        progressive = yaml.safe_load((ROOT / 'examples/WordFactoriProgressive.yaml').read_text())['Word Factori']
        self.assertFalse(normal['progressive_machines'])
        self.assertTrue(progressive['progressive_machines'])
        self.assertTrue(progressive['recipe_checks'])
        self.assertTrue(progressive['type_a_word_checks'])
        self.assertEqual(progressive['type_a_word_count'], 3)
        self.assertGreaterEqual(len(set(progressive['type_a_word_words'])), 3)
        from word_factori.word_orders import normalize_word_list
        self.assertGreaterEqual(len(normalize_word_list(progressive['type_a_word_words'])), 3)

    def test_package_includes_examples_and_all_presentation_dependencies(self):
        build_release.write_world()
        build_release.write_release()
        with zipfile.ZipFile(build_release.WORLD_ARCHIVE) as world:
            for name in ('mail_view', 'progress_protocol', 'progress_presentation', 'recovery_presentation'):
                self.assertIn(f'word_factori/{name}.py', world.namelist())
        with zipfile.ZipFile(build_release.RELEASE_ARCHIVE) as release:
            for name in ('WordFactori', 'WordFactoriProgressive'):
                self.assertIn(f'examples/{name}.yaml', release.namelist())
