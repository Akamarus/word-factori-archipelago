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
    NativeHookBootstrap,
    OverlayGeometry,
    OverlayWindowHook,
    Rect,
    RowPresentation,
    WM_HOTKEY,
    WM_NCHITTEST,
    drain_parent_messages,
    present_dispatch_row,
    row_height_for_texture,
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


class RendererBoundaryTests(unittest.TestCase):
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
        hook.set_interaction_state(game_active=False, ledger_open=False)
        api.callback(77, WM_HOTKEY, api.f8_id, 0)
        self.assertEqual([], actions)
        hook.set_interaction_state(game_active=True, ledger_open=False)
        api.escape_down = True
        hook.poll_pointer()
        api.callback(77, WM_HOTKEY, api.f8_id, 0)
        self.assertEqual(["toggle"], actions)
        api.escape_down = False
        hook.poll_pointer()
        hook.set_interaction_state(game_active=True, ledger_open=True)
        api.escape_down = True
        hook.poll_pointer()
        hook.poll_pointer()
        self.assertEqual(["toggle", "close"], actions)

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
        api.left_down = True
        hook.poll_pointer()
        hook.poll_pointer()
        self.assertEqual(["close"], actions)
        self.assertEqual(HTTRANSPARENT, geometry.hit_test(*api.point))
        api.left_down = False
        hook.poll_pointer()
        api.point = (200, 200)
        api.left_down = True
        hook.poll_pointer()
        self.assertEqual(["close"], actions)

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
        self.assertTrue(writer.enqueue("open"))
        self.assertTrue(writer.enqueue("close"))
        self.assertTrue(connection.ready.wait(1.0))
        writer.stop(0.2)
        self.assertEqual(["open", "close"], connection.values)
        self.assertFalse(writer.failed)

        class Broken:
            def send(self, value):
                raise BrokenPipeError("closed")

        broken = ChildActionWriter(Broken(), capacity=2)
        started = time.monotonic()
        self.assertTrue(broken.enqueue("open"))
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
        self.assertTrue(writer.enqueue("open"))
        self.assertTrue(entered.wait(1.0))
        self.assertTrue(writer.enqueue("close"))
        self.assertFalse(writer.enqueue("toggle"))
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
        encoded = OverlayGeometry.encode_action("filter", "received")
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


class FakeHookAPI:
    f8_id = 0x5746
    escape_id = 0x5747

    def __init__(self):
        self.style = 32
        self.callback = None
        self.original = object()
        self.restored = []
        self.hotkeys = set()
        self.hidden = []
        self.shown = []
        self.left_down = False
        self.escape_down = False
        self.point = (900, 400)

    def get_extended_style(self, hwnd):
        return self.style

    def set_extended_style(self, hwnd, style):
        self.style = style

    def install_window_procedure(self, hwnd, callback):
        self.callback = callback
        return self.original

    def restore_window_procedure(self, hwnd, original):
        self.restored.append(original)

    def register_hotkey(self, hwnd, hotkey_id, key):
        self.hotkeys.add(hotkey_id)

    def unregister_hotkey(self, hwnd, hotkey_id):
        self.hotkeys.discard(hotkey_id)

    def client_point_from_lparam(self, hwnd, lparam):
        return self.point

    def cursor_client_position(self, hwnd):
        return self.point

    def left_button_down(self):
        return self.left_down

    def escape_key_down(self):
        return self.escape_down

    def show_no_activate(self, hwnd):
        self.shown.append(hwnd)

    def hide_window(self, hwnd):
        self.hidden.append(hwnd)

    def call_original(self, original, hwnd, message, wparam, lparam):
        return 987


if __name__ == "__main__":
    unittest.main()
