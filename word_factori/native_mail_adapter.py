"""Presentation and allowlisted actions; progression remains in the AP client."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
import hashlib
import time
import uuid

from . import native_mail_protocol as protocol


def room_token(identity):
    return hashlib.sha256(identity.encode('utf-8')).hexdigest() if identity is not None else None


def _key(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _text(value):
    # Native Draw text is plain text. Reject malformed code points at this boundary.
    return str(value).replace('\x00', '').encode('utf-8', 'replace').decode('utf-8')[:protocol.MAX_TEXT]


class NativeMailAdapter:
    def __init__(self, transport):
        self.transport = transport
        self.room = self.contract = None
        self._source = None
        self._unread = frozenset()
        self._boundaries = OrderedDict()
        self._cursors = OrderedDict()
        self._page = dict(items=None, chat=None)
        self._filter = 'all'
        self.clock = time.monotonic
        self._popup_deadlines = {}
        self._expired_popups = OrderedDict()

    def _remember(self, mapping, key, value, limit=512):
        mapping[key] = value
        while len(mapping) > limit:
            mapping.popitem(last=False)

    def _item(self, row):
        return dict(key=_key(row['key']), direction=row['direction'],
                    item=_text(row['item_name']), player=_text(row['other_player']),
                    location=_text(row['location_name']), historical=row['historical'],
                    unread=row['key'] in self._unread)

    def publish(self, value, *, room, contract, unread_keys=()):
        if (room, contract) != (self.room, self.contract):
            self._boundaries.clear(); self._cursors.clear()
            self._page = dict(items=None, chat=None)
            self._filter = 'all'
            self._popup_deadlines.clear(); self._expired_popups.clear()
        elif self._source is not None and value.connection_status != 'connected' and not value.word_order_rows:
            value = replace(value, word_order_rows=self._source.word_order_rows)
        self.room, self.contract = room, contract
        self._source = value
        self._unread = frozenset(unread_keys)
        self._publish_current()
        return True

    def _rows(self, view):
        rows = list(self._source.ledger_rows if view == 'items' else self._source.transcript_rows)
        if view == 'items' and self._filter != 'all':
            directions = ('received', 'self') if self._filter == 'received' else ('sent', 'self')
            rows = [row for row in rows if row['direction'] in directions]
        before = self._page[view]
        if before is not None:
            position = next((i for i, row in enumerate(rows) if row['key'] == before), None)
            rows = rows[:position] if position is not None else []
        page = rows[-50:]
        cursor = None
        if len(rows) > len(page):
            cursor = self._cursor(view, page[0]['key'])
        return page, cursor

    def _cursor(self, view, before):
        identity = (view, self._filter if view == 'items' else 'all', before)
        cursor = next((k for k, v in self._cursors.items() if v == identity), None)
        if cursor is None:
            cursor = uuid.uuid4().hex
            self._remember(self._cursors, cursor, identity, 128)
        return cursor

    def _publish_current(self):
        source = self._source
        if source is None:
            return
        items, item_cursor = self._rows('items')
        chat, chat_cursor = self._rows('chat')
        prefix = set()
        for row in source.ledger_rows:
            prefix.add(row['key'])
            self._remember(self._boundaries, _key(row['key']), frozenset(prefix))
        value = dict(version=1, session=self.transport.session,
                     renderer=self.transport.renderer or '0'*32, revision=0,
                     room=self.room, contract=self.contract, connection=source.connection_status,
                     items=[self._item(row) for row in items],
                     chat=[dict(key=_key(row['key']), kind=row['kind'], text=_text(row['text'])) for row in chat],
                     words=[dict(name=_text(row['name']), word=row['word'], status=row['status'])
                            for row in source.word_order_rows],
                     notifications=self._notifications(),
                     unread=len(self._unread), acks=[], history=dict(items=item_cursor, chat=chat_cursor))
        # Reserve the worst-case acknowledgment budget added by transport later.
        # Keep targets; oldest history gives way to the byte ceiling.
        while True:
            try:
                raw = protocol.encode_envelope(value, kind='snapshot')
                if len(raw) > protocol.SNAPSHOT_BYTES - 80*1024:
                    raise ValueError('Reserve acknowledgment space')
                break
            except ValueError:
                if not value['items'] and not value['chat']:
                    raise
                collection = 'items' if len(value['items']) >= len(value['chat']) else 'chat'
                value[collection].pop(0)
        # Advance from the actual retained boundary, not the pre-trimming page.
        for view, rows in (('items', items), ('chat', chat)):
            kept = len(value[view])
            if kept and kept < len(rows):
                value['history'][view] = self._cursor(view, rows[-kept]['key'])
        self.transport.publish(value)

    def _notifications(self):
        rows = []
        for row in self._source.visible_notifications + self._source.waiting_notifications:
            key = row['key']
            if row['historical'] or key not in self._unread or key in self._expired_popups:
                continue
            rows.append(self._item(row))
            self._popup_deadlines.setdefault(key, self.clock() + 6)
            if len(rows) == 3:
                break
        return rows

    async def process_once(self, context):
        expired = [key for key, deadline in self._popup_deadlines.items() if self.clock() >= deadline]
        if expired:
            for key in expired:
                self._popup_deadlines.pop(key)
                self._remember(self._expired_popups, key, True)
            self._publish_current()
        for request in self.transport.poll():
            status, message = 'forwarded', 'Handled by the client.'
            try:
                protocol.validate_envelope(request, kind='request')
                if (not self.transport.ready or request['session'] != self.transport.session
                        or request['renderer'] != self.transport.renderer
                        or request['room'] != self.room
                        or room_token(context.connected_identity) != self.room):
                    raise ValueError('Room or Mail session changed. Reopen Mail.')
                generation = context._connection_generation
                identity = context.connected_identity
                action, payload = request['action'], request['payload']
                if action == 'submit-text':
                    text = payload['text'].strip()
                    if text.startswith('/') and text not in ('/help', '/wf_status', '/wf_words'):
                        raise ValueError('Use the regular client for that command.')
                    if context.server is None or self._source.connection_status != 'connected':
                        raise ValueError('Connect in the regular client before sending.')
                    # No await separates identity validation and the existing synchronous router.
                    context.command_processor(context)(text)
                elif action == 'mark-read':
                    keys = self._boundaries.get(payload['through_key'])
                    if keys is None or not await context.mark_native_mail_read(keys, identity, generation):
                        raise ValueError('Read status could not be saved. Reopen Mail.')
                elif action == 'history':
                    cursor = ((payload['view'], payload['filter'], None) if payload['cursor'] == 'latest'
                              else self._cursors.get(payload['cursor']))
                    if cursor is None or cursor[:2] != (payload['view'], payload['filter']):
                        raise ValueError('History expired. Select Latest for current entries.')
                    self._page[cursor[0]] = cursor[2]
                    if cursor[0] == 'items':
                        self._filter = payload['filter']
                    self._publish_current()
                elif action == 'disconnect':
                    await context.disconnect()
                elif action == 'reconnect':
                    if not context.server_address or not context.auth:
                        raise ValueError('Set the server and slot in the regular client first.')
                    await context.connect(context.server_address)
            except ValueError as error:
                status, message = 'rejected', _text(error)
            except Exception:
                # Do not leak credentials through exception messages or retry uncertain chat.
                status, message = 'uncertain', 'Action could not be confirmed. Check the regular client before retrying.'
            # A failed publication is not a second dispatch or a second acknowledgment.
            self.transport.acknowledge(request, status, message)

    def close(self):
        self.transport.close()
