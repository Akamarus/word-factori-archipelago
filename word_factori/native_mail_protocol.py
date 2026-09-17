"""Strict, bounded presentation-only protocol shared with the native Mail UI.

No network, filesystem, credentials or progression operations belong here.
Counters are limited to integers represented exactly by the native runner.
"""
from __future__ import annotations

import json
import math
import re

VERSION = 1
MANIFEST_BYTES = 4096
SNAPSHOT_BYTES = 256 * 1024
REQUEST_BYTES = 8192
MAX_ITEMS = MAX_CHAT = 50
MAX_WORDS = 20
MAX_NOTIFICATIONS = 3
MAX_ACKS = 32
MAX_TEXT = 512
MAX_ID = 128
MAX_SUBMIT_TEXT = 1024
MAX_COUNTER = 2**53 - 1
POLL_SECONDS = .25
HEARTBEAT_SECONDS = 1.0
STALE_SECONDS = 5.0
LIMITS = dict(manifest=MANIFEST_BYTES, hello=MANIFEST_BYTES,
              snapshot=SNAPSHOT_BYTES, request=REQUEST_BYTES)
CONNECTIONS = frozenset(('disconnected', 'connecting', 'connected', 'reconnecting',
                         'authenticating', 'error'))


def _require(condition):
    if not condition:
        raise ValueError('Invalid native Mail envelope')


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names.split()))


def _text(value, maximum=MAX_TEXT, *, empty=True):
    _require(type(value) is str and len(value) <= maximum and '\x00' not in value)
    _require(empty or bool(value.strip()))
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError as error:
        raise ValueError('Invalid native Mail text') from error


def _identity(value, nullable=False):
    if nullable and value is None:
        return
    _text(value, MAX_ID, empty=False)


def _uuid(value):
    _require(type(value) is str and re.fullmatch('[0-9a-f]{32}', value) is not None)


def _counter(value):
    _require(type(value) is int and 0 <= value <= MAX_COUNTER)


def _enum(value, choices):
    _require(type(value) is str and value in choices)


def _item(value):
    _keys(value, 'key direction item player location historical unread')
    _identity(value['key'])
    _enum(value['direction'], ('received', 'sent', 'self'))
    for field in ('item', 'player', 'location'):
        _text(value[field])
    for field in ('historical', 'unread'):
        _require(type(value[field]) is bool)


def _chat(value):
    _keys(value, 'key kind text')
    _identity(value['key'])
    _enum(value['kind'], ('chat', 'hint', 'command', 'error'))
    _text(value['text'])


def _word(value):
    _keys(value, 'name word status')
    _text(value['name'], empty=False)
    _text(value['word'], 12, empty=False)
    _enum(value['status'], ('Not completed', 'Sending', 'Completed'))


def _ack(value):
    _keys(value, 'sequence status message')
    _counter(value['sequence'])
    _enum(value['status'], ('queued', 'forwarded', 'rejected', 'uncertain'))
    _text(value['message'])


def validate_envelope(value, *, kind):
    _require(type(kind) is str and kind in LIMITS)
    fields = {
        'manifest': 'version session renderer revision heartbeat',
        'hello': 'version renderer heartbeat',
        'request': 'version session renderer room sequence action payload',
        'snapshot': 'version session renderer revision room contract connection items chat words notifications unread acks history',
    }
    _keys(value, fields[kind])
    _require(type(value['version']) is int and value['version'] == VERSION)
    _uuid(value['renderer'])
    if kind != 'hello':
        _uuid(value['session'])
    for field in ('heartbeat', 'revision', 'sequence', 'unread'):
        if field in value:
            _counter(value[field])
    if kind == 'snapshot':
        _identity(value['room'], nullable=True)
        _identity(value['contract'], nullable=True)
        _require((value['room'] is None) == (value['contract'] is None))
        _enum(value['connection'], CONNECTIONS)
        for field, count, validator in (
            ('items', MAX_ITEMS, _item), ('chat', MAX_CHAT, _chat),
            ('words', MAX_WORDS, _word), ('notifications', MAX_NOTIFICATIONS, _item),
            ('acks', MAX_ACKS, _ack),
        ):
            _require(type(value[field]) is list and len(value[field]) <= count)
            for row in value[field]:
                validator(row)
        _keys(value['history'], 'items chat')
        for cursor in value['history'].values():
            _identity(cursor, nullable=True)
    if kind == 'request':
        action, payload = value['action'], value['payload']
        _enum(action, ('submit-text', 'mark-read', 'history', 'disconnect', 'reconnect'))
        _identity(value['room'], nullable=action in ('disconnect', 'reconnect'))
        if action == 'submit-text':
            _keys(payload, 'text'); _text(payload['text'], MAX_SUBMIT_TEXT, empty=False)
        elif action == 'mark-read':
            _keys(payload, 'through_key'); _identity(payload['through_key'])
        elif action == 'history':
            _keys(payload, 'view filter cursor')
            _enum(payload['view'], ('items', 'chat'))
            _enum(payload['filter'], ('all', 'received', 'sent') if payload['view'] == 'items' else ('all',))
            _identity(payload['cursor'])
        else:
            _keys(payload, '')


def encode_envelope(value, *, kind):
    validate_envelope(value, kind=kind)
    try:
        raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (UnicodeError, TypeError, RecursionError) as error:
        raise ValueError('Invalid native Mail JSON') from error
    _require(len(raw) <= LIMITS[kind])
    return raw


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _bad_constant(_):
    raise ValueError('Nonfinite native Mail number')


def decode_envelope(raw, *, kind):
    _require(type(kind) is str and kind in LIMITS)
    _require(type(raw) is bytes and len(raw) <= LIMITS[kind])
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs,
                           parse_constant=_bad_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError('Invalid native Mail JSON') from error
    validate_envelope(value, kind=kind)
    return value


def heartbeat_fresh(last_advance, now):
    return (type(last_advance) in (int, float) and type(now) in (int, float)
            and math.isfinite(last_advance) and math.isfinite(now)
            and 0 <= now - last_advance < STALE_SECONDS)
