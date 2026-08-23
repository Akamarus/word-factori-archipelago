import json
import tempfile
import unittest
from pathlib import Path

from word_factori.overlay_protocol import decode_child_action, encode_parent_message, settings_message
from word_factori.overlay_renderer import (
    HTCLIENT,
    HTTRANSPARENT,
    OverlayGeometry,
    OverlayWindowHook,
    Rect,
    WM_NCHITTEST,
    drain_parent_messages,
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
        class HookAPI:
            def __init__(self):
                self.style = 32
                self.callback = None
                self.original = object()
                self.restored = []
                self.hotkey_registered = False

            def get_extended_style(self, hwnd):
                return self.style

            def set_extended_style(self, hwnd, style):
                self.style = style

            def install_window_procedure(self, hwnd, callback):
                self.callback = callback
                return self.original

            def restore_window_procedure(self, hwnd, original):
                self.restored.append(original)

            def register_hotkey(self, hwnd):
                self.hotkey_registered = True

            def unregister_hotkey(self, hwnd):
                self.hotkey_registered = False

            def client_point_from_lparam(self, hwnd, lparam):
                return (900, 400)

            def call_original(self, original, hwnd, message, wparam, lparam):
                return 987

        api = HookAPI()
        geometry = OverlayGeometry(mailbox=Rect(24, 400, 72, 72))
        hook = OverlayWindowHook(hwnd=77, geometry=lambda: geometry, hotkey=lambda: None, api=api)
        hook.install()
        self.assertTrue(api.hotkey_registered)
        self.assertEqual(HTTRANSPARENT, api.callback(77, WM_NCHITTEST, 0, 0))
        hook.shutdown()
        self.assertEqual(32, api.style)
        self.assertEqual([api.original], api.restored)
        self.assertFalse(api.hotkey_registered)


if __name__ == "__main__":
    unittest.main()
