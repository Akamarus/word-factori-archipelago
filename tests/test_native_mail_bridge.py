"""Native execution assertions supplement these build-boundary checks."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeMailBridgeTests(unittest.TestCase):
    def test_production_composition_refuses_incomplete_sources(self):
        from tools import enhanced_hooks
        transform = getattr(enhanced_hooks, 'transform_production_sources', None)
        self.assertIsNotNone(transform, 'Mail is not composed into the production patch')
        with self.assertRaises(ValueError):
            transform({}, ROOT)
    def test_production_panel_requires_full_native_tabs_and_shared_input_guards(self):
        from tools import mail_hooks
        helpers = getattr(mail_hooks, 'production_mail_helpers', None)
        self.assertIsNotNone(helpers, 'Production Mail UI is not implemented')
        source = helpers(ROOT)
        for function in ('wf_mail_ui_step','wf_mail_ui_draw','wf_mail_ui_frame',
                         'wf_mail_blocks_input','wf_mail_editor_should_yield'):
            self.assertIn('function ' + function + '(', source)
        for tab in ('Items','Chat','Type-a-Word','Status'):
            self.assertIn('"' + tab + '"', source)
        self.assertNotIn('wf_probe_frame', source)
    def test_authored_bridge_has_bounded_lifecycle_and_no_progression_actions(self):
        path = ROOT / 'tools/native_mail_bridge.gml'
        self.assertTrue(path.exists(), 'Native bridge is not implemented')
        source = path.read_text(encoding='utf-8')
        for function in ('wf_mail_bridge_step', 'wf_mail_bridge_ready', 'wf_mail_submit',
                         'wf_mail_bridge_shutdown', 'wf_mail_snapshot_valid'):
            self.assertIn('function ' + function + '(', source)
        for forbidden in ('send_location', 'LocationChecks', 'game_save(', 'execute_shell(', 'http_'):
            self.assertNotIn(forbidden, source)

    def test_bridge_probe_cannot_pass_without_all_assertions(self):
        from tools import run_mail_native_probe as probe
        required = getattr(probe, 'BRIDGE_ASSERTIONS', ())
        self.assertGreater(len(required), 10, 'Native bridge acceptance is not implemented')
        base = [dict(name=n, passed=True) for n in probe.REQUIRED_ASSERTIONS]
        extra = [dict(name=n, passed=True) for n in required]
        probe.validate_result(dict(supported=True, case='bridge', tests=base+extra))
        for index in range(len(extra)):
            with self.assertRaises(ValueError):
                probe.validate_result(dict(supported=True, case='bridge',
                                           tests=base+extra[:index]+extra[index+1:]))
