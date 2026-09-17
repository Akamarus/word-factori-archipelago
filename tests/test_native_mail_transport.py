import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.native_mail_fixtures import mail_snapshot, mail_request, mail_item
from word_factori.native_mail_protocol import encode_envelope, decode_envelope


class NativeMailTransportTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('word_factori.native_mail_transport')
        except ModuleNotFoundError:
            self.fail('Native Mail transport is not implemented')
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'archipelago_mail'
        self.now = 0.0
        self.transport = self.module.NativeMailTransport(self.root, 'a'*32, clock=lambda: self.now)
        self.transport.start(); self.addCleanup(self.transport.close)

    def hello(self, heartbeat=0, renderer='b'*32):
        (self.root / 'hello.json').write_bytes(encode_envelope(
            dict(version=1, renderer=renderer, heartbeat=heartbeat), kind='hello'))

    def tick(self, delta=.25):
        self.now += delta
        return self.transport.poll()

    def pair(self):
        self.transport.publish(mail_snapshot())
        self.hello(); self.tick()
        self.hello(1); self.tick(1)
        self.assertTrue(self.transport.ready)

    def request(self, value):
        (self.root / 'request.json').write_bytes(encode_envelope(value, kind='request'))

    def read(self, name):
        return decode_envelope((self.root / (name+'.json')).read_bytes(), kind=name)

    def test_stale_startup_hello_does_not_authorize_requests(self):
        self.hello(); self.request(mail_request()); self.transport.publish(mail_snapshot())
        self.assertEqual((), self.tick())
        self.assertEqual((), self.tick(1))
        self.assertFalse(self.transport.ready)

    def test_pair_publishes_matching_manifest_snapshot_and_independent_heartbeat(self):
        self.pair()
        first = self.read('manifest'); snapshot = self.read('snapshot')
        self.assertEqual(first['revision'], snapshot['revision'])
        self.assertEqual('b'*32, first['renderer'])
        raw = (self.root/'snapshot.json').read_bytes()
        self.tick(1)
        self.assertGreater(self.read('manifest')['heartbeat'], first['heartbeat'])
        self.assertEqual(raw, (self.root/'snapshot.json').read_bytes())
        self.transport.publish(mail_snapshot())
        self.assertEqual(first['revision'], self.read('manifest')['revision'])

    def test_duplicate_pending_and_completed_requests_never_redispatch(self):
        self.pair(); request = mail_request(); self.request(request)
        self.assertEqual((request,), self.tick())
        self.assertEqual((), self.tick())
        self.transport.acknowledge(request, 'forwarded', 'Sent')
        self.assertEqual((), self.tick())
        self.assertEqual('forwarded', self.read('snapshot')['acks'][-1]['status'])

    def test_wrong_identity_room_and_old_sequences_are_not_dispatched(self):
        self.pair()
        for field, wrong in [('session', 'c'*32), ('renderer', 'c'*32), ('room', 'room-B')]:
            request = mail_request(); request[field] = wrong; self.request(request)
            self.assertEqual((), self.tick())
        valid = mail_request(sequence=10); self.request(valid); self.assertEqual((valid,), self.tick())
        self.transport.acknowledge(valid, 'forwarded', '')
        self.request(mail_request(sequence=9)); self.assertEqual((), self.tick())

    def test_only_one_pending_request_and_ack_identity_is_checked(self):
        self.pair(); first = mail_request(); self.request(first); self.tick()
        self.request(mail_request(2)); self.assertEqual((), self.tick())
        with self.assertRaises(ValueError):
            self.transport.acknowledge(mail_request(2), 'forwarded', '')
        self.transport.acknowledge(first, 'forwarded', '')
        self.assertEqual((mail_request(2),), self.tick())

    def test_mark_read_and_history_require_issued_boundaries(self):
        self.pair()
        req = mail_request(action='mark-read'); req['payload'] = dict(through_key='missing')
        self.request(req); self.assertEqual((), self.tick())
        snap = mail_snapshot(); snap['items'] = [mail_item()]
        self.transport.publish(snap)
        req['sequence'] = 2; req['payload']['through_key'] = 'delivery-1'
        self.request(req); self.assertEqual((req,), self.tick())
        self.transport.acknowledge(req, 'forwarded', '')
        req = mail_request(3, 'history'); req['payload'] = dict(view='items', filter='all', cursor='invented')
        self.request(req); self.assertEqual((), self.tick())

    def test_second_client_refused_and_lock_released_on_close(self):
        other = self.module.NativeMailTransport(self.root, 'c'*32, clock=lambda: self.now)
        with self.assertRaises((ValueError, OSError)):
            other.start()
        self.transport.close(); other.start(); other.close()

    def test_latest_history_control_is_allowed_after_pairing(self):
        self.pair()
        request = mail_request(action='history')
        request['payload'] = dict(view='items', filter='all', cursor='latest')
        self.request(request)
        self.assertEqual((request,), self.tick())

    def test_conflicting_live_renderer_suspends_mail(self):
        self.pair(); self.hello(0, 'c'*32); self.tick()
        self.hello(1, 'c'*32); self.tick()
        self.assertFalse(self.transport.ready)
        self.request(mail_request()); self.assertEqual((), self.tick())

    def test_stale_heartbeat_disables_requests_and_new_renderer_can_pair(self):
        self.pair(); self.tick(5); self.assertFalse(self.transport.ready)
        self.request(mail_request()); self.assertEqual((), self.tick())
        self.hello(0, 'c'*32); self.tick()
        self.hello(1, 'c'*32); self.tick(1)
        self.assertTrue(self.transport.ready)
        self.assertEqual('c'*32, self.read('manifest')['renderer'])

    def test_poll_is_rate_limited_and_malformed_file_does_not_dispatch(self):
        self.pair(); self.request(mail_request())
        self.assertEqual((), self.transport.poll())
        (self.root/'request.json').write_bytes(b'{'*9000)
        self.assertEqual((), self.tick())
        self.assertFalse(self.transport.ready)

    def test_interrupted_snapshot_replacement_does_not_advance_manifest(self):
        self.pair(); old = self.read('manifest')
        snap = mail_snapshot(); snap['unread'] = 1
        with patch.object(self.module.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):
                self.transport.publish(snap)
        self.assertEqual(old, self.read('manifest'))
        self.assertEqual([], list(self.root.glob('*.tmp')))

    def test_close_during_dispatch_does_not_write_late_ack(self):
        self.pair(); request = mail_request(); self.request(request); self.tick()
        before = (self.root/'snapshot.json').read_bytes(); self.transport.close()
        self.transport.acknowledge(request, 'uncertain', 'Closed')
        self.assertEqual(before, (self.root/'snapshot.json').read_bytes())

    def test_hardlinked_request_is_refused_without_reading_or_writing_target(self):
        import os
        self.pair(); outside = Path(self.temp.name)/'private.json'
        outside.write_bytes(encode_envelope(mail_request(), kind='request'))
        os.link(outside, self.root/'request.json')
        self.assertEqual((), self.tick())
        self.assertFalse(self.transport.ready)
        self.assertEqual('hello', json.loads(outside.read_bytes())['payload']['text'])

    def test_ack_ring_is_bounded_but_evicted_sequences_stay_rejected(self):
        self.pair()
        for index in range(1, 36):
            self.hello(index+1)
            req = mail_request(index); self.request(req)
            self.assertEqual((req,), self.tick())
            self.transport.acknowledge(req, 'forwarded', '')
        self.assertEqual(32, len(self.read('snapshot')['acks']))
        self.request(mail_request(1)); self.assertEqual((), self.tick())
