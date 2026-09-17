import asyncio
from dataclasses import replace
import hashlib
import importlib
from types import SimpleNamespace
import unittest

from tests.native_mail_fixtures import mail_request
from word_factori.dispatch import DispatchEvent, DispatchDirection
from word_factori.dispatch_store import DispatchLedger
from word_factori.overlay_model import OverlayState, snapshot
from word_factori.native_mail_protocol import decode_envelope, encode_envelope


class RecordingTransport:
    session = 'a'*32
    renderer = 'b'*32
    ready = True
    def __init__(self):
        self.values = []; self.requests = []; self.acks = []
    def publish(self, value):
        self.values.append(decode_envelope(encode_envelope(value, kind='snapshot'), kind='snapshot'))
    def poll(self):
        values, self.requests = self.requests, []
        return tuple(values)
    def acknowledge(self, request, status, message):
        self.acks.append((request['sequence'], status, message))
    def close(self):
        self.ready = False


def presentation(count=0, *, text='Bender Access', words=()):
    events = tuple(DispatchEvent(f'room-A:receive:{i}', DispatchDirection.RECEIVED,
                                1, text, 2, 'Other player', 'Other game', i,
                                'Other location', i, None, False) for i in range(count))
    return snapshot(OverlayState(connection_status='connected'),
                    DispatchLedger('room-A', events), word_order_rows=words)


class NativeMailAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        try:
            self.module = importlib.import_module('word_factori.native_mail_adapter')
        except ModuleNotFoundError:
            self.fail('Native Mail adapter is not implemented')
        self.transport = RecordingTransport()
        self.adapter = self.module.NativeMailAdapter(self.transport)
        self.room = hashlib.sha256(b'room-A').hexdigest()
        self.sent = []
        self.ctx = SimpleNamespace(connected_identity='room-A', _connection_generation=1,
                                   server=object(), server_address='localhost:38281', auth='Player',
                                   command_processor=lambda ctx: self.sent.append)

    def publish(self, value=None, **kw):
        self.adapter.publish(value or presentation(), room=self.room, contract='contract-A', **kw)

    async def submit(self, text, sequence=1, room=None):
        req = mail_request(sequence, text=text); req['room'] = room or self.room
        self.transport.requests.append(req)
        await self.adapter.process_once(self.ctx)

    def test_words_survive_trimming_and_no_credentials_or_raw_packets(self):
        words = [dict(name='Order 1', word='HELLO!', status='Sending')]
        self.publish(presentation(200, text='😀'*2000, words=words))
        sent = self.transport.values[-1]
        self.assertEqual(words, sent['words'])
        self.assertLessEqual(len(sent['items']), 50)
        self.assertEqual(512, len(sent['items'][0]['item']))
        self.assertEqual({'key','direction','item','player','location','historical','unread'}, set(sent['items'][0]))

    async def test_chat_and_safe_commands_route_but_credentials_and_arbitrary_commands_do_not(self):
        self.publish()
        for index, text in enumerate(['hello', '!hint Bender', '/help', '/wf_status', '/wf_words'], 1):
            await self.submit(text, index)
        self.assertEqual(['hello', '!hint Bender', '/help', '/wf_status', '/wf_words'], self.sent)
        for index, text in enumerate(['/connect other', '/password secret', '/wf_overlay restart', '/help secret'], 6):
            await self.submit(text, index)
            self.assertEqual('rejected', self.transport.acks[-1][1])
        self.assertEqual(5, len(self.sent))

    async def test_wrong_room_offline_and_stale_transport_cannot_submit(self):
        self.publish(); await self.submit('wrong', room='other-room')
        self.ctx.server = None; await self.submit('offline', 2)
        self.ctx.server = object(); self.transport.ready = False
        await self.submit('stale', 3)
        self.assertEqual([], self.sent)

    async def test_mark_read_uses_only_keys_through_the_displayed_boundary(self):
        self.publish(presentation(2), unread_keys={'room-A:receive:0', 'room-A:receive:1'})
        boundary = self.transport.values[-1]['items'][-1]['key']
        self.publish(presentation(3), unread_keys={'room-A:receive:0','room-A:receive:1','room-A:receive:2'})
        received = []
        async def mark(keys, identity, generation):
            received.append((keys, identity, generation)); return True
        self.ctx.mark_native_mail_read = mark
        req = mail_request(action='mark-read'); req.update(room=self.room, payload=dict(through_key=boundary))
        self.transport.requests.append(req); await self.adapter.process_once(self.ctx)
        self.assertEqual([(frozenset({'room-A:receive:0','room-A:receive:1'}), 'room-A', 1)], received)

    async def test_history_is_bounded_and_invalid_cursor_is_rejected(self):
        self.publish(presentation(120))
        first = self.transport.values[-1]
        self.assertEqual(50, len(first['items']))
        req = mail_request(action='history'); req.update(room=self.room, payload=dict(
            view='items', filter='all', cursor=first['history']['items']))
        self.transport.requests.append(req); await self.adapter.process_once(self.ctx)
        second = self.transport.values[-1]
        self.assertEqual(50, len(second['items']))
        self.assertTrue(set(x['key'] for x in first['items']).isdisjoint(x['key'] for x in second['items']))
        req['sequence']=2; req['payload']['cursor']='invalid'
        self.transport.requests.append(req); await self.adapter.process_once(self.ctx)
        self.assertEqual('rejected', self.transport.acks[-1][1])

    async def test_latest_history_returns_from_older_page(self):
        self.publish(presentation(120))
        first = self.transport.values[-1]
        req = mail_request(action='history'); req.update(room=self.room, payload=dict(
            view='items', filter='all', cursor=first['history']['items']))
        self.transport.requests.append(req); await self.adapter.process_once(self.ctx)
        req['sequence'] = 2; req['payload']['cursor'] = 'latest'
        self.transport.requests.append(req); await self.adapter.process_once(self.ctx)
        self.assertEqual(first['items'], self.transport.values[-1]['items'])

    async def test_byte_trimmed_history_has_no_gaps_and_reserves_ack_space(self):
        value = presentation(100, text='😀'*512)
        value = replace(value, ledger_rows=tuple(dict(row, other_player='😀'*512,
                        location_name='😀'*512) for row in value.ledger_rows))
        self.publish(value)
        seen = set()
        for sequence in range(1, 20):
            page = self.transport.values[-1]
            self.assertLessEqual(len(encode_envelope(page, kind='snapshot')), 256*1024-80*1024)
            seen.update(row['key'] for row in page['items'])
            if page['history']['items'] is None:
                break
            req = mail_request(sequence, action='history'); req.update(room=self.room, payload=dict(
                view='items', filter='all', cursor=page['history']['items']))
            self.transport.requests.append(req); await self.adapter.process_once(self.ctx)
        self.assertEqual(100, len(seen))

    def test_room_change_clears_prior_boundaries_and_notifications_are_not_historical(self):
        value = presentation(2)
        event = DispatchEvent('room-A:receive:0', DispatchDirection.RECEIVED, 1, 'Item', 2,
                              'Other', 'Game', 1, 'Location', 0, None, True)
        value = replace(value, visible_notifications=({'key': event.key,'direction':'received',
                        'item_name':'Item','other_player':'Other','location_name':'Location','historical':True},))
        self.publish(value)
        self.assertEqual([], self.transport.values[-1]['notifications'])
        self.adapter.publish(presentation(), room='room-B', contract='contract-B')
        self.assertEqual([], self.transport.values[-1]['items'])

    async def test_reconnect_requires_existing_configuration_and_uses_no_payload_credentials(self):
        self.publish(); calls=[]
        async def connect(address): calls.append(address)
        self.ctx.connect=connect
        req=mail_request(action='reconnect'); req.update(room=self.room, payload={})
        self.transport.requests.append(req); await self.adapter.process_once(self.ctx)
        self.assertEqual(['localhost:38281'],calls)
        self.ctx.auth=None
        req['sequence']=2; self.transport.requests.append(req); await self.adapter.process_once(self.ctx)
        self.assertEqual('rejected',self.transport.acks[-1][1])

    def test_offline_same_room_retains_targets_but_changed_room_clears_them(self):
        words = [dict(name='Order', word='CAT', status='Not completed')]
        self.publish(presentation(words=words))
        offline = replace(presentation(), connection_status='disconnected')
        self.publish(offline)
        self.assertEqual(words, self.transport.values[-1]['words'])
        self.adapter.publish(offline, room='new-room', contract='new-contract')
        self.assertEqual([], self.transport.values[-1]['words'])

    async def test_ack_write_failure_does_not_repeat_ack_or_action(self):
        self.publish()
        calls = []
        def fail(request, status, message):
            calls.append(status)
            raise OSError('interrupted replacement')
        self.transport.acknowledge = fail
        with self.assertRaises(OSError):
            await self.submit('hello')
        self.assertEqual(['hello'], self.sent)
        self.assertEqual(['forwarded'], calls)

    async def test_waiting_delivery_replaces_expired_popup_without_replaying_it(self):
        now = [0.0]
        self.adapter.clock = lambda: now[0]
        value = presentation(4)
        value = replace(value, visible_notifications=value.ledger_rows[:3],
                        waiting_notifications=value.ledger_rows[3:])
        unread = {row['key'] for row in value.ledger_rows}
        self.publish(value, unread_keys=unread)
        first = self.transport.values[-1]['notifications']
        now[0] = 7
        await self.adapter.process_once(self.ctx)
        second = self.transport.values[-1]['notifications']
        self.assertEqual(1, len(second))
        self.assertNotIn(second[0]['key'], {row['key'] for row in first})
