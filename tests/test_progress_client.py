import unittest
from unittest.mock import patch, AsyncMock

from tests import test_client_lifecycle as fixtures
from word_factori.bridge import bind_game_slot
from word_factori.overlay_model import OverlayState


class ProgressClientTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ClientLifecycleTests.asyncSetUp
    write_active_slot = fixtures.ClientLifecycleTests.write_active_slot

    def require_feature(self):
        self.assertTrue(callable(getattr(self.ctx, 'progress_presentation', None)))

    async def scan(self):
        # Keep the actual save parser, binding and reporting; only mod selection is external UI state.
        with patch.object(self.ctx, 'selected_mod', return_value=True):
            await self.ctx.scan_once()

    async def test_current_save_not_server_checks_controls_page(self):
        self.require_feature()
        await self.scan()  # Bind the empty room save before recording completions.
        self.ctx.checked_locations = {l.code for l in self.ctx.active_locations()}
        self.write_active_slot('game-slot-A', {0, 1, 2})
        await self.scan()
        value = self.ctx.progress_presentation()
        self.assertEqual(value.rows[6].completion, 'Completed')
        self.assertEqual(value.rows[6].page_status, 'Locked: finish 1 more on page 1')
        self.write_active_slot('game-slot-A', {0, 1, 2, 3})
        await self.scan()
        self.assertEqual(self.ctx.progress_presentation().rows[6].page_status, 'Unlocked in save')

    async def test_failed_scan_and_wrong_save_invalidate_progress(self):
        self.require_feature()
        await self.scan()
        self.write_active_slot('other-save', {0, 1, 2, 3})
        await self.scan()
        self.assertEqual(self.ctx.progress_presentation().freshness, 'unavailable')
        self.assertEqual(self.ctx.recovery_presentation().code, 'save_mismatch')
        self.save_path.write_text('invalid')
        await self.scan()
        self.assertEqual(self.ctx.progress_presentation().freshness, 'unavailable')
    async def test_unselected_mod_never_leaves_current_readiness(self):
        self.require_feature()
        await self.scan()
        with patch.object(self.ctx, 'selected_mod', return_value=False):
            await self.ctx.scan_once()
        self.assertEqual(self.ctx.progress_presentation().freshness, 'unavailable')
        self.assertEqual(self.ctx.recovery_presentation().code, 'mod_unselected')

    async def test_render_getters_never_read_save_or_rebuild_logic(self):
        self.require_feature()
        await self.scan()
        value = self.ctx.progress_presentation()
        with patch('word_factori.client.read_active_slot', side_effect=AssertionError('render IO')), \
             patch('word_factori.client.patch_readiness', side_effect=AssertionError('render hash')), \
             patch('word_factori.progress_presentation.budgets_for_location', side_effect=AssertionError('render logic')):
            for _ in range(5):
                self.assertEqual(self.ctx.progress_presentation(), value)
                self.ctx.recovery_presentation()

    async def test_disconnect_marks_last_known_then_new_room_clears(self):
        self.require_feature()
        await self.scan()
        await self.ctx.connection_closed()
        self.assertEqual(self.ctx.progress_presentation().freshness, 'last_known')
        self.assertEqual(self.ctx.recovery_presentation().code, 'disconnected')
        self.ctx.connected_identity = 'different-room'
        self.assertEqual(self.ctx.progress_presentation().rows, ())

    async def test_changed_generation_during_report_discards_observation(self):
        self.require_feature()
        async def changed(*args, **kwargs):
            self.ctx._advance_connection_generation()
        with patch.object(self.ctx, 'report_indices', new=changed):
            await self.scan()
        self.assertNotEqual(self.ctx.progress_presentation().freshness, 'current')

    async def test_connection_refusal_has_safe_recovery(self):
        self.require_feature()
        self.ctx.on_package('ConnectionRefused', {'errors': ['InvalidPassword']})
        self.assertEqual(self.ctx.recovery_presentation().code, 'auth_failed')

    async def test_connected_without_valid_campaign_is_not_ready(self):
        self.require_feature()
        self.ctx.slot_data = {'campaign_id': 'not-a-room'}
        await self.scan()
        self.assertEqual(self.ctx.recovery_presentation().code, 'room_mismatch')

    async def test_presentation_failure_cannot_interrupt_check_reporting(self):
        self.require_feature()
        await self.scan()
        self.write_active_slot('game-slot-A', {0})
        with patch('word_factori.client.build_progress', side_effect=ValueError('presentation failure')):
            await self.scan()
        self.assertIn(self.ctx.active_locations()[0].code, self.ctx.bridge_state.pending_checks)
        self.assertEqual(self.ctx.progress_presentation().freshness, 'unavailable')
