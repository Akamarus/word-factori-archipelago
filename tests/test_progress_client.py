import unittest
import json
from unittest.mock import patch, AsyncMock

from tests import test_client_lifecycle as fixtures
from word_factori.bridge import bind_game_slot
from word_factori.overlay_model import OverlayState
from word_factori.native_mail_adapter import NativeMailAdapter
from tests.test_native_mail_adapter import RecordingTransport
from tests import test_linux_client as linux_fixtures
from word_factori.dispatch_store import DispatchLedger


class ProgressClientTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ClientLifecycleTests.asyncSetUp
    write_active_slot = fixtures.ClientLifecycleTests.write_active_slot
    install_word_room = fixtures.ClientLifecycleTests.install_word_room

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

    async def test_unexpected_scan_failure_publishes_unavailable_before_retry(self):
        await self.scan()
        with patch('word_factori.client.read_active_slot', side_effect=RuntimeError('scan failed')):
            with self.assertRaisesRegex(RuntimeError, 'scan failed'):
                await self.scan()
        sent = self.overlay.published[-1]
        self.assertEqual(sent.progress_freshness, 'unavailable')
        self.assertEqual(sent.recovery['code'], 'unknown_error')

    async def test_late_scan_cannot_publish_over_a_new_connection(self):
        await self.scan()
        published = len(self.overlay.published)
        async def changed(*args, **kwargs):
            self.ctx._advance_connection_generation()
            raise RuntimeError('old scan failed')
        with patch.object(self.ctx, 'report_indices', new=changed):
            with self.assertRaisesRegex(RuntimeError, 'old scan failed'):
                await self.scan()
        self.assertEqual(len(self.overlay.published), published)
        self.assertNotEqual(self.ctx.recovery_presentation().code, 'unknown_error')

    async def test_word_readiness_does_not_survive_invalidation(self):
        self.install_word_room(('CC',))
        self.ctx._refresh_progress()
        self.assertEqual(self.ctx.word_order_presentation()[0][0]['machine_status'], 'Machines ready')
        self.ctx._invalidate_progress('mod_unselected')
        self.ctx.publish_overlay()
        self.assertEqual(self.overlay.published[-1].word_order_rows[0].machine_status, 'Requirements unavailable')

    async def test_word_readiness_is_bound_to_room_and_generation(self):
        self.install_word_room(('CC',))
        for change in ('room', 'generation'):
            with self.subTest(change=change):
                self.ctx._refresh_progress()
                self.assertEqual(self.ctx.word_order_presentation()[0][0]['machine_status'], 'Machines ready')
                if change == 'room':
                    self.ctx.connected_identity = 'new-room'
                else:
                    self.ctx._advance_connection_generation()
                self.assertEqual(self.ctx.word_order_presentation()[0][0]['machine_status'], 'Requirements unavailable')

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


class LinuxProgressPublicationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = linux_fixtures.LinuxClientTests.asyncSetUp
    install = linux_fixtures.LinuxClientTests.install
    context = linux_fixtures.LinuxClientTests.context
    write_active_slot = fixtures.ClientLifecycleTests.write_active_slot

    async def test_failed_scans_publish_unavailable_without_other_events(self):
        with self.install():
            self.ctx = self.context()
            self.ctx.dispatch_ledger = DispatchLedger.empty(self.ctx.connected_identity)
            self.ctx.overlay_state = OverlayState(connection_status='connected')
            self.assertTrue(self.ctx.prepare_selected_campaign())
            account = self.factori / 'test-account'
            (self.factori / 'user_ref.json').write_text(json.dumps({'most_recent_steam': 'test-account'}))
            self.save_path = account / 'mods' / 'word factori archipelago' / 'save.json'
            self.save_path.parent.mkdir(parents=True)
            transport = RecordingTransport()
            self.ctx.native_mail = NativeMailAdapter(transport)
            for failure in ('mod_unselected', 'journal_invalid', 'save_mismatch'):
                with self.subTest(failure=failure):
                    self.write_active_slot('game-slot-A', set())
                    await self.ctx.scan_once(ignore_selection_guard=True)
                    self.assertEqual(transport.values[-1]['progress_freshness'], 'current')
                    if failure == 'journal_invalid':
                        self.save_path.write_text('invalid')
                    elif failure == 'save_mismatch':
                        self.write_active_slot('other-save', set())
                    with patch.object(self.ctx, 'selected_mod', return_value=failure != 'mod_unselected'):
                        await self.ctx.scan_once()
                    sent = transport.values[-1]
                    self.assertEqual(sent['progress_freshness'], 'unavailable')
                    self.assertEqual(sent['recovery']['code'], failure)
