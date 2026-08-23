import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from word_factori.overlay_protocol import decode_child_action, encode_parent_message, settings_message
from word_factori.overlay_renderer import (
    HTCLIENT,
    HTTRANSPARENT,
    ChildActionWriter,
    CtypesOverlayHookAPI,
    KeyPressState,
    MOD_NOREPEAT,
    NativeHookBootstrap,
    OverlayGeometry,
    OverlayWindowHook,
    Rect,
    RowPresentation,
    RuntimeFontResolver,
    WM_HOTKEY,
    WM_NCHITTEST,
    drain_parent_messages,
    present_dispatch_row,
    runtime_font_path,
    row_height_for_texture,
    window_relative_regions,
    validated_renderer_config,
)
from word_factori.window_tracker import Win32WindowTracker


class FakeWin32:
    def __init__(
        self,
        *,
        windows=(100,),
        pid=44,
        executable=r"C:\Games\Word Factori\word factori.exe",
        rect=(100, 80, 2020, 1160),
        dpi=144,
        visible=True,
        minimized=False,
        foreground=True,
    ):
        self.windows = tuple(windows)
        self.pid = pid
        self.executable = executable
        self.rect = rect
        self.dpi = dpi
        self.visible = visible
        self.minimized = minimized
        self.foreground = foreground
        self.closed = []

    def enum_windows(self):
        return self.windows

    def is_window(self, hwnd):
        return True

    def window_process_id(self, hwnd):
        return self.pid

    def open_process(self, pid):
        return f"handle-{pid}"

    def process_path(self, handle):
        return self.executable

    def close_handle(self, handle):
        self.closed.append(handle)

    def window_rect(self, hwnd):
        return self.rect

    def is_window_visible(self, hwnd):
        return self.visible

    def is_minimized(self, hwnd):
        return self.minimized

    def foreground_window(self):
        return 100 if self.foreground else 999

    def dpi_for_window(self, hwnd):
        return self.dpi


class WindowTrackerTests(unittest.TestCase):
    def test_tracker_returns_scaled_visible_game_bounds(self):
        api = FakeWin32()
        state = Win32WindowTracker(api=api).sample()
        self.assertIsNotNone(state)
        self.assertEqual((100, 80, 1920, 1080), state.bounds)
        self.assertEqual(1.5, state.scale)
        self.assertTrue(state.visible)
        self.assertTrue(state.focused)
        self.assertEqual(["handle-44"], api.closed)

    def test_tracker_ignores_wrong_executable_and_closes_process_handle(self):
        api = FakeWin32(executable=r"C:\Game\other.exe")
        self.assertIsNone(Win32WindowTracker(api=api).sample())
        self.assertEqual(["handle-44"], api.closed)

    def test_minimized_or_hidden_game_is_retained_but_not_visible(self):
        minimized = Win32WindowTracker(api=FakeWin32(minimized=True)).sample()
        hidden = Win32WindowTracker(api=FakeWin32(visible=False)).sample()
        self.assertFalse(minimized.visible)
        self.assertFalse(hidden.visible)

    def test_invalid_candidates_are_skipped_without_leaking_handles(self):
        api = FakeWin32(pid=0, rect=(100, 100, 100, 200), dpi=0)
        self.assertIsNone(Win32WindowTracker(api=api).sample())
        self.assertEqual([], api.closed)

    def test_api_failures_do_not_escape_sampling(self):
        api = FakeWin32()
        api.process_path = lambda handle: (_ for _ in ()).throw(OSError("gone"))
        self.assertIsNone(Win32WindowTracker(api=api).sample())
        self.assertEqual(["handle-44"], api.closed)

    def test_renderer_discovers_font_only_beside_tracked_word_factori_process(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "word factori.exe"
            executable.touch()
            font = executable.with_name("FredokaOne.ttf")
            font.touch()
            tracker = Win32WindowTracker(api=FakeWin32(executable=str(executable)))

            self.assertEqual(str(font), runtime_font_path(None, tracker))

    def test_renderer_font_discovery_safely_falls_back_when_game_is_absent(self):
        tracker = Win32WindowTracker(api=FakeWin32(windows=()))

        self.assertIsNone(runtime_font_path(None, tracker))

    def test_renderer_font_discovery_retries_when_game_starts_after_child(self):
        resolver = RuntimeFontResolver(None)
        self.assertIsNone(resolver.resolve(Win32WindowTracker(api=FakeWin32(windows=()))))
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "word factori.exe"
            executable.touch()
            font = executable.with_name("FredokaOne.ttf")
            font.touch()

            resolved = resolver.resolve(Win32WindowTracker(
                api=FakeWin32(executable=str(executable)),
            ))

        self.assertEqual(str(font), resolved)


class RendererBoundaryTests(unittest.TestCase):
    def test_renderer_action_encoding_requires_current_snapshot_generation(self):
        with self.assertRaises(ValueError):
            OverlayGeometry.encode_action("open", generation=None)
        decoded = decode_child_action(OverlayGeometry.encode_action("open", generation=9))
        self.assertEqual(("open", 9), (decoded.kind, decoded.generation))

    def test_production_visibility_adapter_uses_verified_no_activate_show_and_hide(self):
        user32 = FakeVisibilityUser32()
        adapter = CtypesOverlayHookAPI.__new__(CtypesOverlayHookAPI)
        adapter._user32 = user32

        adapter.show_no_activate(77)
        adapter.hide_window(77)

        self.assertEqual([
            (77, 0, 0, 0, 0, 0, 0x0057),
            (77, 0, 0, 0, 0, 0, 0x0097),
        ], user32.position_calls)
        self.assertEqual([77, 77], user32.visibility_checks)

    def test_production_visibility_adapter_raises_when_set_window_pos_fails(self):
        user32 = FakeVisibilityUser32(set_position_result=False)
        adapter = CtypesOverlayHookAPI.__new__(CtypesOverlayHookAPI)
        adapter._user32 = user32

        with self.assertRaises(OSError):
            adapter.show_no_activate(77)

    def test_production_visibility_adapter_raises_on_visibility_mismatch(self):
        user32 = FakeVisibilityUser32(apply_visibility=False)
        adapter = CtypesOverlayHookAPI.__new__(CtypesOverlayHookAPI)
        adapter._user32 = user32

        with self.assertRaisesRegex(OSError, "visible state"):
            adapter.show_no_activate(77)
        user32.visible = True
        with self.assertRaisesRegex(OSError, "hidden state"):
            adapter.hide_window(77)

    def test_hotkeys_are_gated_by_game_focus_and_ledger_state(self):
        api = FakeHookAPI()
        actions = []
        hook = OverlayWindowHook(
            hwnd=77,
            geometry=lambda: OverlayGeometry(mailbox=Rect(10, 10, 40, 40)),
            action=lambda kind: actions.append(kind),
            api=api,
        )
        hook.install()
        self.assertIn((api.f8_id, MOD_NOREPEAT, 0x77), api.hotkey_calls)
        hook.set_interaction_state(game_active=False, ledger_open=False)
        api.callback(77, WM_HOTKEY, api.f8_id, 0)
        self.assertEqual([], actions)
        hook.set_interaction_state(game_active=True, ledger_open=False)
        hook.poll_pointer()
        api.callback(77, WM_HOTKEY, api.f8_id, 0)
        self.assertEqual(["toggle"], actions)
        hook.poll_pointer()
        hook.set_interaction_state(game_active=True, ledger_open=True)
        self.assertIn((api.escape_id, MOD_NOREPEAT, 0x1B), api.hotkey_calls)
        api.callback(77, WM_HOTKEY, api.escape_id, 0)
        self.assertEqual(["toggle", "close"], actions)
        hook.set_interaction_state(game_active=False, ledger_open=True)
        self.assertNotIn(api.escape_id, api.hotkeys)

    def test_escape_registration_failure_uses_pressed_since_poll_fallback(self):
        api = FakeHookAPI()
        api.fail_escape_registration = True
        actions = []
        hook = OverlayWindowHook(
            hwnd=77, geometry=lambda: OverlayGeometry(mailbox=Rect(1, 2, 3, 4)),
            action=lambda kind: actions.append(kind), api=api,
        )
        hook.install()
        hook.set_interaction_state(game_active=True, ledger_open=True)
        api.key_states[0x1B] = [KeyPressState(True, False)]
        hook.poll_pointer()
        hook.poll_pointer()
        self.assertEqual(["close"], actions)

    def test_outside_click_closes_once_without_changing_clickthrough_geometry(self):
        api = FakeHookAPI()
        actions = []
        geometry = OverlayGeometry(
            mailbox=Rect(10, 10, 40, 40),
            ledger=Rect(100, 100, 300, 300),
        )
        hook = OverlayWindowHook(hwnd=77, geometry=lambda: geometry,
                                 action=lambda kind: actions.append(kind), api=api)
        hook.install()
        hook.set_interaction_state(game_active=True, ledger_open=True)
        api.point = (700, 500)
        api.key_states[0x01] = [KeyPressState(True, False)]
        hook.poll_pointer()
        hook.poll_pointer()
        self.assertEqual(["close"], actions)
        self.assertEqual(HTTRANSPARENT, geometry.hit_test(*api.point))
        api.point = (200, 200)
        api.key_states[0x01] = [KeyPressState(True, False)]
        hook.poll_pointer()
        self.assertEqual(["close"], actions)

    def test_native_region_tracks_exact_geometry_updates_and_clears(self):
        api = FakeHookAPI()
        current = [OverlayGeometry(
            mailbox=Rect(10, 20, 30, 40),
            toasts=(Rect(50, 60, 70, 80),),
            ledger=None,
        )]
        hook = OverlayWindowHook(hwnd=77, geometry=lambda: current[0], action=lambda kind: None, api=api)
        hook.install()
        self.assertEqual(((Rect(10, 20, 30, 40), Rect(50, 60, 70, 80)),), tuple(api.regions))
        current[0] = OverlayGeometry(
            mailbox=Rect(12, 22, 30, 40),
            toasts=(),
            ledger=Rect(100, 110, 200, 210),
        )
        hook.refresh_region(force=True)
        self.assertEqual((Rect(12, 22, 30, 40), Rect(100, 110, 200, 210)), api.regions[-1])
        self.assertTrue(hook.shutdown())
        self.assertEqual([77], api.cleared_regions)

    def test_client_regions_are_offset_to_window_origin_at_adapter_seam(self):
        regions = (Rect(10, 20, 30, 40), Rect(50, 60, 70, 80))
        self.assertEqual(
            (Rect(18, 51, 30, 40), Rect(58, 91, 70, 80)),
            window_relative_regions(regions, (8, 31)),
        )

    def test_region_or_native_visibility_failure_marks_bootstrap_failed(self):
        region_api = FakeHookAPI()
        region_api.fail_region = True
        region_bootstrap = NativeHookBootstrap(
            handle_provider=lambda: 77, api_factory=lambda: region_api,
            geometry=lambda: OverlayGeometry(mailbox=Rect(1, 2, 3, 4)),
            action=lambda kind: None, max_attempts=1,
        )
        self.assertEqual("failed", region_bootstrap.tick())

        show_api = FakeHookAPI()
        show_bootstrap = NativeHookBootstrap(
            handle_provider=lambda: 77, api_factory=lambda: show_api,
            geometry=lambda: OverlayGeometry(mailbox=Rect(1, 2, 3, 4)),
            action=lambda kind: None, max_attempts=1,
        )
        self.assertEqual("ready", show_bootstrap.tick())
        show_api.fail_show = True
        self.assertFalse(show_bootstrap.set_visible(True))
        self.assertEqual("failed", show_bootstrap.status)

        hide_api = FakeHookAPI()
        hide_bootstrap = NativeHookBootstrap(
            handle_provider=lambda: 77, api_factory=lambda: hide_api,
            geometry=lambda: OverlayGeometry(mailbox=Rect(1, 2, 3, 4)),
            action=lambda kind: None, max_attempts=1,
        )
        self.assertEqual("ready", hide_bootstrap.tick())
        self.assertTrue(hide_bootstrap.set_visible(True))
        hide_api.fail_hide = True
        self.assertFalse(hide_bootstrap.set_visible(False))
        self.assertEqual("failed", hide_bootstrap.status)

    def test_failed_wndproc_restore_retains_references_for_shutdown_retry(self):
        api = FakeHookAPI()
        api.restore_failures = 1
        hook = OverlayWindowHook(
            hwnd=77, geometry=lambda: OverlayGeometry(mailbox=Rect(1, 2, 3, 4)),
            action=lambda kind: None, api=api,
        )
        hook.install()
        self.assertFalse(hook.shutdown())
        self.assertTrue(hook.shutdown_pending)
        self.assertIsNotNone(api.callback)
        self.assertTrue(hook.shutdown())
        self.assertFalse(hook.shutdown_pending)
        self.assertIsNone(api.callback)

    def test_native_bootstrap_hides_before_install_retries_and_then_succeeds(self):
        api = FakeHookAPI()
        handles = iter((None, 77))
        bootstrap = NativeHookBootstrap(
            handle_provider=lambda: next(handles),
            api_factory=lambda: api,
            geometry=lambda: None,
            action=lambda kind: None,
            max_attempts=3,
        )
        self.assertEqual("pending", bootstrap.tick())
        self.assertEqual("ready", bootstrap.tick())
        self.assertEqual([77], api.hidden)
        bootstrap.set_visible(True)
        bootstrap.set_visible(False)
        self.assertEqual([77], api.shown)
        self.assertEqual([77, 77], api.hidden)
        bootstrap.shutdown()

    def test_native_bootstrap_exhausts_bounded_missing_handle_attempts(self):
        bootstrap = NativeHookBootstrap(
            handle_provider=lambda: None,
            api_factory=lambda: FakeHookAPI(),
            geometry=lambda: None,
            action=lambda kind: None,
            max_attempts=2,
        )
        self.assertEqual("pending", bootstrap.tick())
        self.assertEqual("failed", bootstrap.tick())
        self.assertEqual("failed", bootstrap.tick())

    def test_native_bootstrap_restores_partial_install_before_retry(self):
        api = FakeHookAPI()
        original_install = api.install_window_procedure
        calls = 0

        def fail_once(hwnd, callback):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("hook rejected")
            return original_install(hwnd, callback)

        api.install_window_procedure = fail_once
        bootstrap = NativeHookBootstrap(
            handle_provider=lambda: 77,
            api_factory=lambda: api,
            geometry=lambda: None,
            action=lambda kind: None,
            max_attempts=2,
        )
        self.assertEqual("pending", bootstrap.tick())
        self.assertEqual(32, api.style)
        self.assertEqual("ready", bootstrap.tick())
        bootstrap.shutdown()
        self.assertEqual(32, api.style)

    def test_toast_stack_extremes_are_positive_ordered_and_non_overlapping(self):
        cases = (
            (1280, 720, 3.0, 2000, 3),
            (1280, 720, 4.0, -2000, 10),
            (640, 480, 4.0, 2000, 10),
            (1920, 1080, 1.0, 0, 1),
        )
        for width, height, scale, offset, count in cases:
            with self.subTest(width=width, height=height, scale=scale, offset=offset, count=count):
                geometry = OverlayGeometry.for_window(
                    width=width, height=height, scale=scale, left_offset=offset,
                    toast_count=count, ledger_open=False,
                )
                self.assertEqual(count, len(geometry.toasts))
                for toast in geometry.toasts:
                    self.assertGreater(toast.width, 0)
                    self.assertGreater(toast.height, 0)
                    self.assertGreaterEqual(toast.y, 0)
                    self.assertLessEqual(toast.top, height)
                for first, second in zip(geometry.toasts, geometry.toasts[1:]):
                    self.assertLessEqual(first.top, second.y)

    def test_row_presentation_preserves_direction_time_location_and_unicode(self):
        base = {
            "item_name": "超長い Contraption ✨",
            "other_player": "Игрок-非常に長い",
            "other_game": "Celeste Ω",
            "location_name": "Forsaken City / 工場",
            "observed_at": "2026-08-23T12:34:56Z",
            "historical": False,
        }
        received = present_dispatch_row({**base, "direction": "received"})
        sent = present_dispatch_row({**base, "direction": "sent"})
        own = present_dispatch_row({**base, "direction": "self", "historical": True})
        self.assertIsInstance(received, RowPresentation)
        self.assertIn("Received", received.primary)
        self.assertIn("Sent", sent.primary)
        self.assertIn("for yourself", own.secondary)
        self.assertIn(base["location_name"], received.metadata)
        self.assertIn(base["observed_at"], received.metadata)
        self.assertIn("earlier", own.metadata)
        self.assertNotIn(base["observed_at"], own.metadata)
        self.assertIn(base["item_name"], received.primary)
        self.assertEqual(76, row_height_for_texture(10))
        self.assertEqual(180, row_height_for_texture(1000))

    def test_child_action_writer_preserves_order_and_reports_broken_pipe(self):
        class Connection:
            def __init__(self):
                self.values = []
                self.ready = threading.Event()

            def send(self, value):
                self.values.append(decode_child_action(value).kind)
                if len(self.values) == 2:
                    self.ready.set()

        connection = Connection()
        writer = ChildActionWriter(connection, capacity=4)
        self.assertTrue(writer.enqueue("open", generation=3))
        self.assertTrue(writer.enqueue("close", generation=3))
        self.assertTrue(connection.ready.wait(1.0))
        writer.stop(0.2)
        self.assertEqual(["open", "close"], connection.values)
        self.assertFalse(writer.failed)

        class Broken:
            def send(self, value):
                raise BrokenPipeError("closed")

        broken = ChildActionWriter(Broken(), capacity=2)
        started = time.monotonic()
        self.assertTrue(broken.enqueue("open", generation=3))
        self.assertLess(time.monotonic() - started, 0.1)
        deadline = time.monotonic() + 1.0
        while not broken.failed and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertTrue(broken.failed)
        broken.stop(0.2)

    def test_child_action_writer_fails_closed_when_bounded_queue_is_full(self):
        release = threading.Event()
        entered = threading.Event()

        class Blocking:
            def send(self, value):
                entered.set()
                release.wait(1.0)

        writer = ChildActionWriter(Blocking(), capacity=1)
        self.assertTrue(writer.enqueue("open", generation=3))
        self.assertTrue(entered.wait(1.0))
        self.assertTrue(writer.enqueue("close", generation=3))
        self.assertFalse(writer.enqueue("toggle", generation=3))
        self.assertTrue(writer.failed)
        release.set()
        writer.stop(0.2)

    def test_parent_pipe_drain_is_nonblocking_bounded_and_strict(self):
        settings = encode_parent_message(settings_message({
            "enabled": True,
            "interface_scale": 1.0,
            "left_offset": 0,
            "notification_duration": 6.0,
            "reduced_motion": False,
            "max_visible": 3,
        }))

        class Connection:
            def __init__(self):
                self.values = ["not-json", *([settings] * 70)]
                self.received = 0

            def poll(self, timeout):
                self.asserted_timeout = timeout
                return bool(self.values)

            def recv(self):
                self.received += 1
                return self.values.pop(0)

        connection = Connection()
        result = drain_parent_messages(connection)
        self.assertEqual(64, connection.received)
        self.assertEqual(63, len(result.messages))
        self.assertFalse(result.disconnected)
        self.assertEqual(0.0, connection.asserted_timeout)

    def test_renderer_module_does_not_import_kivy_before_child_entrypoint(self):
        source = Path("word_factori/overlay_renderer.py").read_text(encoding="utf-8")
        self.assertNotIn("from kivy", source.split("def overlay_process_main", 1)[0])
        self.assertNotIn("import kivy", source.split("def overlay_process_main", 1)[0])

    def test_child_revalidates_exact_visual_only_config(self):
        valid = {
            "enabled": True,
            "interface_scale": 1.25,
            "left_offset": -20,
            "notification_duration": 6.0,
            "reduced_motion": False,
            "max_visible": 3,
            "font_path": None,
        }
        self.assertEqual(valid, validated_renderer_config(valid))
        with self.assertRaises(ValueError):
            validated_renderer_config({**valid, "password": "secret"})
        with self.assertRaises(ValueError):
            validated_renderer_config({**valid, "interface_scale": float("nan")})

    def test_hit_testing_is_transparent_outside_interactive_regions(self):
        geometry = OverlayGeometry(
            mailbox=Rect(24, 400, 72, 72),
            toasts=(Rect(112, 360, 420, 96),),
            ledger=None,
        )
        self.assertEqual(HTCLIENT, geometry.hit_test(40, 420))
        self.assertEqual(HTCLIENT, geometry.hit_test(300, 400))
        self.assertEqual(HTTRANSPARENT, geometry.hit_test(900, 400))

    def test_open_ledger_is_interactive_and_toast_geometry_is_bounded(self):
        geometry = OverlayGeometry.for_window(
            width=1280,
            height=720,
            scale=2.0,
            left_offset=2000,
            toast_count=10,
            ledger_open=True,
        )
        self.assertIsNotNone(geometry.ledger)
        self.assertLessEqual(len(geometry.toasts), 10)
        for region in (geometry.mailbox, *geometry.toasts, geometry.ledger):
            self.assertGreaterEqual(region.x, 0)
            self.assertGreaterEqual(region.y, 0)
            self.assertLessEqual(region.right, 1280)
            self.assertLessEqual(region.top, 720)

    def test_child_action_encoding_matches_strict_parent_decoder(self):
        encoded = OverlayGeometry.encode_action("filter", "received", generation=3)
        self.assertEqual(("filter", "received"), (
            decode_child_action(encoded).kind,
            decode_child_action(encoded).value,
        ))
        payload = json.loads(encoded)
        self.assertEqual({"version", "type", "payload"}, set(payload))

    def test_native_hook_restores_original_procedure_and_styles(self):
        api = FakeHookAPI()
        geometry = OverlayGeometry(mailbox=Rect(24, 400, 72, 72))
        hook = OverlayWindowHook(hwnd=77, geometry=lambda: geometry, action=lambda kind: None, api=api)
        hook.install()
        self.assertIn(api.f8_id, api.hotkeys)
        self.assertEqual(HTTRANSPARENT, api.callback(77, WM_NCHITTEST, 0, 0))
        hook.shutdown()
        self.assertEqual(32, api.style)
        self.assertEqual([api.original], api.restored)
        self.assertEqual(set(), api.hotkeys)


class FakeVisibilityUser32:
    def __init__(self, *, set_position_result=True, apply_visibility=True):
        self.set_position_result = set_position_result
        self.apply_visibility = apply_visibility
        self.visible = False
        self.position_calls = []
        self.visibility_checks = []
        self.show_window_calls = []

    def SetWindowPos(self, *arguments):
        self.position_calls.append(arguments)
        if self.set_position_result and self.apply_visibility:
            flags = arguments[-1]
            if flags & 0x0040:
                self.visible = True
            elif flags & 0x0080:
                self.visible = False
        return self.set_position_result

    def IsWindowVisible(self, hwnd):
        self.visibility_checks.append(hwnd)
        return self.visible

    def ShowWindow(self, hwnd, command):
        self.show_window_calls.append((hwnd, command))
        return False


class FakeHookAPI:
    f8_id = 0x5746
    escape_id = 0x5747

    def __init__(self):
        self.style = 32
        self.callback = None
        self.original = object()
        self.restored = []
        self.hotkeys = set()
        self.hotkey_calls = []
        self.hidden = []
        self.shown = []
        self.point = (900, 400)
        self.key_states = {}
        self.regions = []
        self.cleared_regions = []
        self.fail_region = False
        self.fail_show = False
        self.fail_hide = False
        self.restore_failures = 0
        self.fail_escape_registration = False

    def get_extended_style(self, hwnd):
        return self.style

    def set_extended_style(self, hwnd, style):
        self.style = style

    def install_window_procedure(self, hwnd, callback):
        self.callback = callback
        return self.original

    def restore_window_procedure(self, hwnd, original):
        if self.restore_failures:
            self.restore_failures -= 1
            raise OSError("restore failed")
        self.restored.append(original)
        self.callback = None

    def register_hotkey(self, hwnd, hotkey_id, modifiers, key):
        self.hotkey_calls.append((hotkey_id, modifiers, key))
        if hotkey_id == self.escape_id and self.fail_escape_registration:
            raise OSError("escape occupied")
        self.hotkeys.add(hotkey_id)

    def unregister_hotkey(self, hwnd, hotkey_id):
        self.hotkeys.discard(hotkey_id)

    def client_point_from_lparam(self, hwnd, lparam):
        return self.point

    def cursor_client_position(self, hwnd):
        return self.point

    def key_press_state(self, key):
        states = self.key_states.get(key, [])
        return states.pop(0) if states else KeyPressState(False, False)

    def set_window_region(self, hwnd, regions):
        if self.fail_region:
            raise OSError("region failed")
        self.regions.append(tuple(regions))

    def clear_window_region(self, hwnd):
        self.cleared_regions.append(hwnd)

    def show_no_activate(self, hwnd):
        if self.fail_show:
            raise OSError("show failed")
        self.shown.append(hwnd)

    def hide_window(self, hwnd):
        if self.fail_hide:
            raise OSError("hide failed")
        self.hidden.append(hwnd)

    def call_original(self, original, hwnd, message, wparam, lparam):
        return 987


if __name__ == "__main__":
    unittest.main()
