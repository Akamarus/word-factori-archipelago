"""Shared strict validation for read-only progress fields in both Mail wires."""
from .progress_presentation import FRESHNESS, MAX_ROWS, MAX_TEXT

PROGRESS_FIELDS = frozenset(('progress_rows', 'progress_status', 'progress_freshness', 'recovery'))
ROW_FIELDS = frozenset(('code', 'page', 'slot', 'name', 'target', 'kind', 'completion', 'page_status', 'machine_status'))


def _require(ok):
    if not ok:
        raise ValueError('Invalid Mail progress presentation')


def text(value):
    _require(type(value) is str and len(value) <= MAX_TEXT and '\0' not in value)
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError as error:
        raise ValueError('Invalid Mail progress text') from error


def unavailable_fields():
    return dict(progress_rows=[], progress_status='Progress unavailable; use the matching client release.',
                progress_freshness='unavailable', recovery=dict(code='mail_stale', severity='warning',
                title='Progress unavailable', action='Use the matching client and installer release.'))


def validate_progress_fields(value):
    rows = value['progress_rows']
    _require(type(rows) is list and len(rows) <= MAX_ROWS)
    seen, slots = set(), set()
    for row in rows:
        _require(type(row) is dict and set(row) == ROW_FIELDS)
        for field, maximum in (('code', 2**53 - 1), ('page', 7), ('slot', 6)):
            _require(type(row[field]) is int and 1 <= row[field] <= maximum)
        _require(row['code'] not in seen and (row['page'], row['slot']) not in slots)
        seen.add(row['code']); slots.add((row['page'], row['slot']))
        for field in ROW_FIELDS - {'code', 'page', 'slot'}:
            text(row[field])
        _require(row['kind'] in ('Campaign level', 'Campaign lab', 'Campaign challenge', 'Final factory'))
        _require(row['completion'] in ('Completed', 'Sending', 'Not completed'))
    text(value['progress_status'])
    _require(type(value['progress_freshness']) is str and value['progress_freshness'] in FRESHNESS)
    recovery = value['recovery']
    _require(type(recovery) is dict and set(recovery) == {'code', 'severity', 'title', 'action'})
    for field in recovery:
        text(recovery[field])
    _require(recovery['severity'] in ('info', 'warning', 'error'))
