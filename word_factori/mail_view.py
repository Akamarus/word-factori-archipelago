"""Read-only Mail text and tab geometry; no game or network authority."""
from __future__ import annotations

TABS = (('Items', 'items', 'open-items'), ('Chat', 'chat', 'open-chat'),
        ('Type-a-Word', 'words', 'open-words'), ('Progress', 'progress', 'open-progress'),
        ('Status', 'status', 'open-status'))


def tab_rects(width: float) -> tuple[tuple[float, float, float, float], ...]:
    """Top-down, logical-pixel hitboxes; the widgets use these same dimensions."""
    columns = 3 if width < 650 else 5
    cell = width / columns
    return tuple(((i % columns)*cell + 4, (i // columns)*52, cell-8, 46)
                 for i in range(len(TABS)))


def tab_at(width: float, x: float, y: float) -> int | None:
    return next((i for i, (left, top, w, h) in enumerate(tab_rects(width))
                 if left <= x < left+w and top <= y < top+h), None)


def display(text: str) -> str:
    return text.replace('🔑', '[KEY]').replace('🚪', '[DOOR]')


def progress_blocks(payload) -> tuple[str, ...]:
    freshness = {'current': 'Current save observation',
                 'last_known': 'Last known progress; reconnect to refresh.',
                 'unavailable': 'Save progress unavailable'}
    blocks = [freshness.get(payload.get('progress_freshness'), freshness['unavailable'])]
    if payload.get('progress_status'):
        blocks.append(payload['progress_status'])
    rows = payload.get('progress_rows', ())
    if not rows:
        blocks.append('Connect and load the selected campaign to view progress.')
    page = None
    for row in rows:
        if row['page'] != page:
            page = row['page']
            blocks.append(f'Page {page}')
        blocks.append(display(f"{row['slot']}. {row['name']} — {row['target']}\n"
                              f"{row['kind']} • {row['completion']}\n"
                              f"{row['page_status']}\n{row['machine_status']}"))
    return tuple(blocks)


def status_blocks(payload) -> tuple[str, ...]:
    recovery = payload.get('recovery', {})
    return (f"Connection: {payload.get('connection_status', payload.get('connection', 'disconnected'))}",
            recovery.get('title', 'Status unavailable'),
            recovery.get('action', 'Check the regular Word Factori client.'),
            'Page access uses your local save. Universal Tracker reports logical reachability.',
            'Mail is read-only: checks and received upgrades continue while this panel is closed.')
