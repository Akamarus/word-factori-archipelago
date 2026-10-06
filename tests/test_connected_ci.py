import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    '0.6.7': 'debe4cf035c7c15efe6fb95f72343af0d420c68c',
    '0.6.8': '54803be064fc7e80c4628777ed0b46a9390f255f',
}


class ConnectedCITests(unittest.TestCase):
    def test_both_platforms_require_pinned_source_and_real_checks(self):
        flow = yaml.safe_load((ROOT / '.github/workflows/verify.yml').read_text())
        job = flow['jobs'].get('connected')
        self.assertIsNotNone(job, 'Required connected CI is missing')
        self.assertEqual(set(job['strategy']['matrix']['os']), {'windows-latest', 'ubuntu-latest'})
        self.assertLessEqual(job['timeout-minutes'], 15)
        self.assertEqual(flow['permissions'], {'contents': 'read'})
        steps = job['steps']
        ap = next(s for s in steps if s.get('with', {}).get('repository') == 'ArchipelagoMW/Archipelago')
        self.assertEqual(ap['with']['ref'], '${{ matrix.ap.ref }}')
        self.assertEqual({entry['version']: entry['ref'] for entry in job['strategy']['matrix']['ap']}, PINS)
        self.assertTrue(any(s.get('with', {}).get('python-version') == '3.12' for s in steps))
        commands = [s.get('run', '') for s in steps]
        build = next(i for i,c in enumerate(commands) if 'python tools/build_release.py' in c)
        check = next(i for i,c in enumerate(commands) if 'unittest tests.test_connected_multiworld' in c)
        self.assertLess(build, check)
        self.assertTrue(any('WF_AP_SOURCE' in c and 'is_file()' in c and 'raise' in c for c in commands[:check+1]))
        self.assertTrue(job['env']['WF_AP_SOURCE'])
        for seed in (160929, 160930):
            self.assertTrue(any(f'--seed {seed}' in c for c in commands))
        artifact = next(s for s in steps if s.get('uses', '').startswith('actions/upload-artifact@'))
        self.assertEqual(artifact['if'], 'always()')
        self.assertEqual(artifact['with']['retention-days'], 7)
        self.assertIn('${{ matrix.ap.version }}', artifact['with']['name'])
        self.assertNotIn('ap-source', artifact['with']['path'])

    def test_headless_dependency_versions_are_pinned(self):
        path = ROOT / 'tools/requirements-connected.txt'
        self.assertTrue(path.is_file())
        pins = {line for line in path.read_text().splitlines() if line and not line.startswith('#')}
        self.assertIn('websockets==13.1', pins)
        self.assertIn('PyYAML==6.0.3', pins)
        self.assertIn('pathspec==1.0.4', pins)
        self.assertIn('bsdiff4==1.2.6', pins)
        self.assertTrue(all('==' in line for line in pins))
        self.assertFalse(any('kivy' in line.lower() for line in pins))
