import unittest

from tests import test_progress_protocol as fixtures
from tests.test_progress_protocol import ROW, RECOVERY
from word_factori.overlay_model import OverlayState, OverlayAction, apply_action, snapshot


class ProgressRendererTests(unittest.TestCase):
    def view(self):
        try:
            from word_factori import mail_view
        except ImportError:
            self.fail('Shared Mail view presentation is missing')
        return mail_view

    def test_tabs_wrap_without_overlapping_and_stay_in_bounds(self):
        view = self.view()
        for width in (225, 320, 600, 860, 1280):
            rects = view.tab_rects(width)
            self.assertEqual(len(rects), 5)
            self.assertEqual(len({r[1] for r in rects}), 2 if width < 650 else 1)
            for i, (x, y, w, h) in enumerate(rects):
                self.assertGreaterEqual(x, 0)
                self.assertLessEqual(x+w, width)
                self.assertGreater(w, 0)
                self.assertEqual(view.tab_at(width, x+w/2, y+h/2), i)
            self.assertIsNone(view.tab_at(width, -1, 0))
        self.assertEqual(tuple(t[0] for t in view.TABS), ('Items', 'Chat', 'Type-a-Word', 'Progress', 'Status'))

    def test_transport_independent_display_and_page_headers(self):
        windows, linux = fixtures.ProgressProtocolTests().pair()
        view = self.view()
        self.assertEqual(view.progress_blocks(windows), view.progress_blocks(linux))
        blocks = view.progress_blocks(windows)
        self.assertIn('Page 1', blocks)
        self.assertTrue(any('Complete I' in b and 'Unlocked in save' in b and 'Machines ready' in b for b in blocks))
        self.assertIn('Ready', view.status_blocks(windows)[1])

    def test_empty_and_stale_are_explicit_and_symbols_remain_readable(self):
        view = self.view()
        payload = dict(progress_rows=[], progress_freshness='unavailable', progress_status='', recovery=RECOVERY)
        self.assertTrue(any('unavailable' in b.lower() for b in view.progress_blocks(payload)))
        payload.update(progress_rows=[dict(ROW, target='🔑🚪')], progress_freshness='last_known')
        blocks = view.progress_blocks(payload)
        self.assertTrue(any('Last known' in b for b in blocks))
        self.assertTrue(any('[KEY][DOOR]' in b for b in blocks))

    def test_long_details_are_preserved_for_widget_wrapping(self):
        view = self.view()
        detail = 'Missing rotation; alternative route. ' * 14
        blocks = view.progress_blocks(dict(progress_rows=[dict(ROW, machine_status=detail)],
            progress_status='Summary', progress_freshness='current'))
        self.assertTrue(any(detail in b for b in blocks))

    def test_chat_progress_items_transition_never_accepts_keyboard(self):
        state = apply_action(OverlayState(), OverlayAction('open-chat'))
        for action in ('open-progress', 'open-items', 'open-status'):
            state = apply_action(state, OverlayAction(action))
            self.assertTrue(state.is_open)
            self.assertFalse(snapshot(state).accepts_keyboard)
