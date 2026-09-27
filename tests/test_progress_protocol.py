import copy
import json
import unittest

from tests.test_native_mail_adapter import RecordingTransport
from word_factori.native_mail_adapter import NativeMailAdapter
from word_factori import native_mail_protocol as native, overlay_protocol as overlay
from word_factori.overlay_model import OverlayState, OverlaySnapshot, snapshot, apply_action, OverlayAction


ROW = dict(code=975301000, page=1, slot=1, name='Complete I', target='I',
           kind='Campaign level', completion='Not completed', page_status='Unlocked in save',
           machine_status='Machines ready')
RECOVERY = dict(code='ready', severity='info', title='Ready', action='Keep the client open.')


class ProgressProtocolTests(unittest.TestCase):
    def setUp(self):
        self.assertIn('progress_rows', OverlaySnapshot.__dataclass_fields__)

    def pair(self):
        value = snapshot(OverlayState(), progress_rows=(ROW,), progress_status='0 of 40',
                         progress_freshness='current', recovery=RECOVERY,
                         word_order_rows=({'name': 'Order 1', 'word': 'CC', 'status': 'Sending',
                                           'machine_status': 'Need Bender'},))
        windows = overlay.decode_parent_message(overlay.encode_parent_message(overlay.snapshot_message(value))).payload
        transport = RecordingTransport()
        NativeMailAdapter(transport).publish(value, room='room', contract='contract')
        return windows, transport.values[-1]

    def test_round_trip_and_cross_platform_parity(self):
        windows, linux = self.pair()
        for field in ('progress_rows', 'progress_status', 'progress_freshness', 'recovery'):
            self.assertEqual(windows[field], linux[field])
        self.assertEqual(windows['word_order_rows'], linux['words'])
        self.assertEqual(linux['progress_rows'][0], ROW)

    def test_malformed_and_oversized_progress_rejected_by_both(self):
        windows, linux = self.pair()
        changes = [dict(code=True), dict(page=0), dict(slot=7), dict(completion='invented'),
                   dict(kind='recipe'), dict(machine_status='x'*513), dict(extra='forbidden')]
        for change in changes:
            for system, payload in (('windows', windows), ('linux', linux)):
                candidate = copy.deepcopy(payload)
                candidate['progress_rows'][0].update(change)
                with self.subTest(system=system, change=change), self.assertRaises(ValueError):
                    if system == 'windows':
                        overlay.encode_parent_message(overlay.ParentMessage('snapshot', candidate))
                    else:
                        native.encode_envelope(candidate, kind='snapshot')
        for count in (2, 41):
            candidate = copy.deepcopy(linux)
            candidate['progress_rows'] *= count
            with self.assertRaises(ValueError):
                native.encode_envelope(candidate, kind='snapshot')

    def test_old_windows_snapshot_has_explicit_unavailable_defaults(self):
        windows, _ = self.pair()
        for key in ('progress_rows', 'progress_status', 'progress_freshness', 'recovery'):
            windows.pop(key)
        for row in windows['word_order_rows']:
            row.pop('machine_status')
        decoded = overlay.decode_parent_message(json.dumps(dict(version=3, type='snapshot', payload=windows))).payload
        self.assertEqual(decoded['progress_rows'], [])
        self.assertEqual(decoded['progress_freshness'], 'unavailable')

    def test_native_version_mismatch_rejected(self):
        _, value = self.pair()
        value['version'] = 1
        with self.assertRaises(ValueError):
            native.encode_envelope(value, kind='snapshot')

    def test_progress_and_status_do_not_accept_text_input(self):
        for action, view in (('open-progress', 'progress'), ('open-status', 'status')):
            state = apply_action(OverlayState(), OverlayAction(action))
            value = snapshot(state)
            decoded = overlay.decode_parent_message(overlay.encode_parent_message(overlay.snapshot_message(value))).payload
            self.assertEqual(decoded['active_view'], view)
            self.assertTrue(decoded['is_open'])
            self.assertFalse(decoded['accepts_keyboard'])

