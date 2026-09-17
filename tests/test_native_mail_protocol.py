import copy
import importlib
import json
import unittest

from tests.native_mail_fixtures import mail_manifest, mail_snapshot, mail_request, mail_item


class NativeMailProtocolTests(unittest.TestCase):
    def setUp(self):
        try:
            self.p = importlib.import_module('word_factori.native_mail_protocol')
        except ModuleNotFoundError:
            self.fail('Native Mail protocol is not implemented')

    def roundtrip(self, value, kind):
        return self.p.decode_envelope(self.p.encode_envelope(value, kind=kind), kind=kind)

    def rejected(self, value, kind):
        with self.assertRaises(ValueError):
            self.p.encode_envelope(value, kind=kind)
        with self.assertRaises(ValueError):
            self.p.decode_envelope(json.dumps(value).encode(), kind=kind)

    def test_roundtrip_preserves_unicode_targets_and_all_row_types(self):
        value = mail_snapshot()
        value.update(items=[mail_item()], notifications=[mail_item()],
                     chat=[dict(key='chat-1', kind='hint', text='Hello café')],
                     words=[dict(name='Order 1', word='A!', status='Sending')],
                     acks=[dict(sequence=1, status='forwarded', message='Sent')])
        self.assertEqual(value, self.roundtrip(value, 'snapshot'))
        for kind, data in [('manifest', mail_manifest()), ('request', mail_request()),
                           ('hello', dict(version=1, renderer='b'*32, heartbeat=0))]:
            self.assertEqual(data, self.roundtrip(data, kind))

    def test_rejects_wrong_versions_ids_boolean_negative_or_inexact_counters(self):
        for field, values in [('version', [True, 2, '1']), ('session', ['', 'A'*32, 'x'*32]),
                              ('renderer', [None, 'b'*31]),
                              ('revision', [True, -1, 1.0, 2**53]),
                              ('heartbeat', [True, -1, float('inf')])]:
            for wrong in values:
                with self.subTest(field=field, value=wrong):
                    value = mail_manifest(); value[field] = wrong
                    self.rejected(value, 'manifest')

    def test_unknown_or_missing_fields_fail_closed_even_nested(self):
        for kind, factory in [('manifest', mail_manifest), ('snapshot', mail_snapshot), ('request', mail_request)]:
            value = factory(); value['password'] = 'never-send'
            self.rejected(value, kind)
            for field in factory():
                value = factory(); del value[field]
                self.rejected(value, kind)
        value = mail_snapshot(); value['items'] = [mail_item()]
        value['items'][0]['raw_packet'] = {}
        self.rejected(value, 'snapshot')
        self.rejected(mail_manifest(), 'unknown')

    def test_request_action_payload_pairs_and_room_binding(self):
        for action, payload in [('mark-read', dict(through_key='delivery-1')),
                                ('history', dict(view='items', filter='sent', cursor='page-1')),
                                ('disconnect', {}), ('reconnect', {})]:
            value = mail_request(action=action); value['payload'] = payload
            self.assertEqual(value, self.roundtrip(value, 'request'))
        for action, payload in [('grant-item', {}), ('reconnect', dict(password='secret')),
                                ('history', dict(view='chat', filter='sent', cursor='x')),
                                ('submit-text', dict(text='')), ('mark-read', dict(through_key=''))]:
            value = mail_request(action=action); value['payload'] = payload
            self.rejected(value, 'request')
        value = mail_request(); value['room'] = None
        self.rejected(value, 'request')
        value.update(action='reconnect', payload={})
        self.assertEqual(value, self.roundtrip(value, 'request'))

    def test_text_and_row_boundaries(self):
        for field, maximum, row in [('items', 50, mail_item()), ('notifications', 3, mail_item()),
                                   ('chat', 50, dict(key='c', kind='chat', text='x')),
                                   ('words', 20, dict(name='Order', word='A'*12, status='Completed')),
                                   ('acks', 32, dict(sequence=1, status='queued', message=''))]:
            value = mail_snapshot(); value[field] = [copy.deepcopy(row) for _ in range(maximum)]
            self.roundtrip(value, 'snapshot')
            value[field].append(row); self.rejected(value, 'snapshot')
        for field, maximum in [('item', 512), ('key', 128)]:
            value = mail_snapshot(); value['items'] = [mail_item()]
            value['items'][0][field] = 'x'*maximum; self.roundtrip(value, 'snapshot')
            value['items'][0][field] += 'x'; self.rejected(value, 'snapshot')
        self.roundtrip(mail_request(text='x'*1024), 'request')
        self.rejected(mail_request(text='x'*1025), 'request')
        self.rejected(mail_request(text='\ud800'), 'request')

    def test_rejects_bad_json_duplicate_keys_depth_and_byte_limits(self):
        for raw in [b'\xff', b'{', b'{"version":1,"version":1}', b'NaN', b'null',
                    b'['*1000+b']'*1000, b' '*4097]:
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                self.p.decode_envelope(raw, kind='manifest')
        value = mail_manifest()
        raw = json.dumps(value).encode()
        self.assertEqual(value, self.p.decode_envelope(raw+b' '*(4096-len(raw)), kind='manifest'))
        value = mail_snapshot()
        huge = dict(key='k', direction='received', item='😀'*512, player='😀'*512,
                    location='😀'*512, historical=False, unread=True)
        value['items'] = [huge]*50
        self.rejected(value, 'snapshot')

    def test_freshness_requires_observed_advance_and_monotonic_time(self):
        self.assertFalse(self.p.heartbeat_fresh(None, 0))
        self.assertTrue(self.p.heartbeat_fresh(10, 14.999))
        for now in [15, 9, float('nan'), float('inf')]:
            self.assertFalse(self.p.heartbeat_fresh(10, now))
