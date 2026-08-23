"""Isolated Word Factori-styled overlay renderer.

This module deliberately has no Kivy import at module scope so the Archipelago
client and spawned-process bootstrap remain importable in headless test runs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
from typing import Callable, Mapping, Protocol

from word_factori.overlay_model import OverlayAction, validate_action
from word_factori.overlay_protocol import PROTOCOL_VERSION, ParentMessage, decode_parent_message
from word_factori.overlay_supervisor import OverlayConfig
from word_factori.window_tracker import Win32WindowTracker


HTCLIENT = 1
HTTRANSPARENT = -1
WM_NCHITTEST = 0x0084
WM_HOTKEY = 0x0312
VK_F8 = 0x77
_HOTKEY_ID = 0x5746
_GWL_EXSTYLE = -20
_GWLP_WNDPROC = -4
_WS_EX_TOPMOST = 0x00000008
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_LAYERED = 0x00080000
_WS_EX_NOACTIVATE = 0x08000000
_MAX_PIPE_MESSAGES_PER_TICK = 64


@dataclass(frozen=True)
class Rect:
    """A top-left-origin rectangle used by Win32 hit testing and layout."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if any(type(value) is not int for value in (self.x, self.y, self.width, self.height)):
            raise ValueError("rectangle values must be integers")
        if self.width < 0 or self.height < 0:
            raise ValueError("rectangle dimensions cannot be negative")

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def top(self) -> int:
        return self.y + self.height

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.right and self.y <= y < self.top


def _fit_rect(x: float, y: float, width: float, height: float, outer_width: int, outer_height: int) -> Rect:
    width_i = max(0, min(int(round(width)), max(0, outer_width)))
    height_i = max(0, min(int(round(height)), max(0, outer_height)))
    x_i = max(0, min(int(round(x)), max(0, outer_width - width_i)))
    y_i = max(0, min(int(round(y)), max(0, outer_height - height_i)))
    return Rect(x_i, y_i, width_i, height_i)


@dataclass(frozen=True)
class OverlayGeometry:
    mailbox: Rect
    toasts: tuple[Rect, ...] = ()
    ledger: Rect | None = None

    @classmethod
    def for_window(
        cls,
        *,
        width: int,
        height: int,
        scale: float,
        left_offset: int,
        toast_count: int,
        ledger_open: bool,
    ) -> "OverlayGeometry":
        if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
            raise ValueError("overlay dimensions must be positive integers")
        if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale):
            raise ValueError("overlay scale must be finite")
        if type(left_offset) is not int or type(toast_count) is not int or toast_count < 0:
            raise ValueError("overlay geometry inputs are invalid")
        ui_scale = max(0.5, min(float(scale), 4.0))
        margin = 24 * ui_scale
        mailbox_size = 72 * ui_scale
        mailbox_y = (height - mailbox_size) / 2 + left_offset
        mailbox = _fit_rect(margin, mailbox_y, mailbox_size, mailbox_size, width, height)
        toast_width = min(420 * ui_scale, max(0, width - mailbox.right - 2 * margin))
        toast_height = 96 * ui_scale
        toast_gap = 12 * ui_scale
        toasts = tuple(
            _fit_rect(
                mailbox.right + 16 * ui_scale,
                mailbox.y + index * (toast_height + toast_gap),
                toast_width,
                toast_height,
                width,
                height,
            )
            for index in range(toast_count)
        )
        ledger = None
        if ledger_open:
            ledger_width = min(760 * ui_scale, max(0, width - 2 * margin))
            ledger_height = min(620 * ui_scale, max(0, height - 2 * margin))
            ledger = _fit_rect(
                max(mailbox.right + 16 * ui_scale, (width - ledger_width) / 2),
                (height - ledger_height) / 2,
                ledger_width,
                ledger_height,
                width,
                height,
            )
        return cls(mailbox, toasts, ledger)

    def hit_test(self, x: int, y: int) -> int:
        if self.mailbox.contains(x, y):
            return HTCLIENT
        if any(region.contains(x, y) for region in self.toasts):
            return HTCLIENT
        if self.ledger is not None and self.ledger.contains(x, y):
            return HTCLIENT
        return HTTRANSPARENT

    @staticmethod
    def encode_action(kind: str, value: str | None = None) -> str:
        action = validate_action(OverlayAction(kind, value))
        return json.dumps(
            {
                "version": PROTOCOL_VERSION,
                "type": "action",
                "payload": {"kind": action.kind, "value": action.value},
            },
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )


def validated_renderer_config(config: Mapping[str, object]) -> dict[str, object]:
    """Copy and revalidate Task 5's exact visual-only child configuration."""
    if type(config) is not dict or set(config) != set(OverlayConfig.__dataclass_fields__):
        raise ValueError("renderer config must contain exactly the visual fields")
    try:
        canonical = OverlayConfig(**config)
    except (TypeError, ValueError) as error:
        raise ValueError("renderer config is invalid") from error
    return asdict(canonical)


@dataclass(frozen=True)
class ParentDrain:
    messages: tuple[ParentMessage, ...]
    disconnected: bool = False


def drain_parent_messages(connection: object) -> ParentDrain:
    """Read at most one bounded nonblocking batch, rejecting malformed frames."""
    messages: list[ParentMessage] = []
    for _index in range(_MAX_PIPE_MESSAGES_PER_TICK):
        try:
            if not connection.poll(0.0):  # type: ignore[attr-defined]
                break
            encoded = connection.recv()  # type: ignore[attr-defined]
        except Exception:
            return ParentDrain(tuple(messages), disconnected=True)
        try:
            message = decode_parent_message(encoded)
        except (TypeError, ValueError):
            continue
        messages.append(message)
        if message.kind == "shutdown":
            break
    return ParentDrain(tuple(messages))


class OverlayHookAPI(Protocol):
    def get_extended_style(self, hwnd: int) -> int: ...
    def set_extended_style(self, hwnd: int, style: int) -> None: ...
    def install_window_procedure(self, hwnd: int, callback: Callable[[int, int, int, int], int]) -> object: ...
    def restore_window_procedure(self, hwnd: int, original: object) -> None: ...
    def register_hotkey(self, hwnd: int) -> None: ...
    def unregister_hotkey(self, hwnd: int) -> None: ...
    def client_point_from_lparam(self, hwnd: int, lparam: int) -> tuple[int, int]: ...
    def call_original(self, original: object | None, hwnd: int, message: int, wparam: int, lparam: int) -> int: ...


class OverlayWindowHook:
    """Own extended styles/WndProc changes and restore them deterministically."""

    def __init__(
        self,
        *,
        hwnd: int,
        geometry: Callable[[], OverlayGeometry | None],
        hotkey: Callable[[], None],
        api: OverlayHookAPI,
    ) -> None:
        self._hwnd = hwnd
        self._geometry = geometry
        self._hotkey = hotkey
        self._api = api
        self._original_style: int | None = None
        self._original_procedure: object | None = None

    def install(self) -> None:
        if self._original_procedure is not None:
            return
        original_style = self._api.get_extended_style(self._hwnd)
        style = original_style | _WS_EX_LAYERED | _WS_EX_TOPMOST | _WS_EX_NOACTIVATE | _WS_EX_TOOLWINDOW
        original_procedure: object | None = None
        try:
            self._api.set_extended_style(self._hwnd, style)
            original_procedure = self._api.install_window_procedure(self._hwnd, self._window_procedure)
        except Exception:
            if original_procedure is not None:
                try:
                    self._api.restore_window_procedure(self._hwnd, original_procedure)
                except Exception:
                    pass
            try:
                self._api.set_extended_style(self._hwnd, original_style)
            except Exception:
                pass
            raise
        try:
            self._api.register_hotkey(self._hwnd)
        except Exception:
            # The hit-test hook is essential; a system-wide F8 collision is not.
            pass
        self._original_style = original_style
        self._original_procedure = original_procedure

    def _window_procedure(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        if message == WM_HOTKEY and int(wparam) == _HOTKEY_ID:
            self._hotkey()
            return 0
        if message == WM_NCHITTEST:
            try:
                geometry = self._geometry()
                if geometry is None:
                    return HTTRANSPARENT
                x, y = self._api.client_point_from_lparam(self._hwnd, lparam)  # type: ignore[attr-defined]
                return geometry.hit_test(x, y)
            except Exception:
                return HTTRANSPARENT
        try:
            return self._api.call_original(self._original_procedure, hwnd, message, wparam, lparam)  # type: ignore[attr-defined]
        except Exception:
            return 0

    def shutdown(self) -> None:
        original_procedure = self._original_procedure
        original_style = self._original_style
        self._original_procedure = None
        self._original_style = None
        try:
            self._api.unregister_hotkey(self._hwnd)
        except Exception:
            pass
        if original_procedure is not None:
            try:
                self._api.restore_window_procedure(self._hwnd, original_procedure)
            except Exception:
                pass
        if original_style is not None:
            try:
                self._api.set_extended_style(self._hwnd, original_style)
            except Exception:
                pass


class CtypesOverlayHookAPI:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("native overlay hooks are available only on Windows")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._long_type = ctypes.c_ssize_t
        self._wndproc_type = ctypes.WINFUNCTYPE(
            self._long_type, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        )
        self._callbacks: dict[int, object] = {}
        self._configure()

    def _configure(self) -> None:
        self._get_long = self._user32.GetWindowLongPtrW
        self._get_long.argtypes = (wintypes.HWND, ctypes.c_int)
        self._get_long.restype = self._long_type
        self._set_long = self._user32.SetWindowLongPtrW
        self._set_long.argtypes = (wintypes.HWND, ctypes.c_int, self._long_type)
        self._set_long.restype = self._long_type
        self._user32.CallWindowProcW.argtypes = (
            self._long_type, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        )
        self._user32.CallWindowProcW.restype = self._long_type
        self._user32.ScreenToClient.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
        self._user32.ScreenToClient.restype = wintypes.BOOL
        self._user32.SetWindowPos.argtypes = (
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT,
        )
        self._user32.SetWindowPos.restype = wintypes.BOOL
        self._user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        self._user32.RegisterHotKey.restype = wintypes.BOOL
        self._user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
        self._user32.UnregisterHotKey.restype = wintypes.BOOL

    def get_extended_style(self, hwnd: int) -> int:
        return int(self._get_long(hwnd, _GWL_EXSTYLE))

    def set_extended_style(self, hwnd: int, style: int) -> None:
        ctypes.set_last_error(0)
        result = self._set_long(hwnd, _GWL_EXSTYLE, style)
        if not result and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        topmost = -1 if style & _WS_EX_TOPMOST else -2
        flags = 0x0001 | 0x0002 | 0x0010 | 0x0020  # NOSIZE, NOMOVE, NOACTIVATE, FRAMECHANGED
        self._user32.SetWindowPos(hwnd, topmost, 0, 0, 0, 0, flags)

    def install_window_procedure(self, hwnd: int, callback: Callable[[int, int, int, int], int]) -> object:
        native = self._wndproc_type(callback)
        ctypes.set_last_error(0)
        original = self._set_long(hwnd, _GWLP_WNDPROC, ctypes.cast(native, ctypes.c_void_p).value)
        if not original and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        self._callbacks[hwnd] = native
        return int(original)

    def restore_window_procedure(self, hwnd: int, original: object) -> None:
        self._set_long(hwnd, _GWLP_WNDPROC, int(original))
        self._callbacks.pop(hwnd, None)

    def register_hotkey(self, hwnd: int) -> None:
        if not self._user32.RegisterHotKey(hwnd, _HOTKEY_ID, 0, VK_F8):
            raise ctypes.WinError(ctypes.get_last_error())

    def unregister_hotkey(self, hwnd: int) -> None:
        self._user32.UnregisterHotKey(hwnd, _HOTKEY_ID)

    def client_point_from_lparam(self, hwnd: int, lparam: int) -> tuple[int, int]:
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        point = wintypes.POINT(x, y)
        if not self._user32.ScreenToClient(hwnd, ctypes.byref(point)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(point.x), int(point.y)

    def call_original(self, original: object | None, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        if original is None:
            return int(self._user32.DefWindowProcW(hwnd, message, wparam, lparam))
        return int(self._user32.CallWindowProcW(int(original), hwnd, message, wparam, lparam))


def _kivy_window_handle(window: object) -> int | None:
    """Best-effort handle discovery isolated to the child runtime."""
    for name in ("window_handle", "hwnd"):
        value = getattr(window, name, None)
        if type(value) is int and value > 0:
            return value
    getter = getattr(window, "get_window_info", None)
    if callable(getter):
        try:
            info = getter()
        except Exception:
            info = None
        if isinstance(info, Mapping):
            for name in ("window", "hwnd", "window_handle"):
                value = info.get(name)
                if type(value) is int and value > 0:
                    return value
    if os.name == "nt":
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            current_pid = os.getpid()
            found: list[int] = []
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            @callback_type
            def collect(hwnd: int, _: int) -> bool:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if int(pid.value) == current_pid and user32.IsWindowVisible(hwnd):
                    found.append(int(hwnd))
                return True

            user32.EnumWindows(collect, 0)
            if found:
                return found[0]
        except Exception:
            pass
    return None


def overlay_process_main(connection: object, config: Mapping[str, object]) -> None:
    """Run the Kivy child using only a private pipe and validated visual config."""
    validated = validated_renderer_config(config)
    if not validated["enabled"]:
        return

    os.environ.setdefault("KIVY_NO_ARGS", "1")
    from kivy.config import Config

    Config.set("graphics", "borderless", "1")
    Config.set("graphics", "resizable", "0")
    Config.set("graphics", "multisamples", "0")
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.text import LabelBase
    from kivy.core.window import Window
    from kivy.graphics import Color, RoundedRectangle
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView

    font_name = "Roboto"
    font_value = validated["font_path"]
    if isinstance(font_value, str) and Path(font_value).is_file():
        try:
            LabelBase.register(name="WordFactoriFredoka", fn_regular=font_value)
            font_name = "WordFactoriFredoka"
        except Exception:
            font_name = "Roboto"

    def paint(widget: object, color: tuple[float, float, float, float], radius: float) -> None:
        with widget.canvas.before:  # type: ignore[attr-defined]
            Color(*color)
            background = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])  # type: ignore[attr-defined]
        widget.bind(pos=lambda instance, value: setattr(background, "pos", value))  # type: ignore[attr-defined]
        widget.bind(size=lambda instance, value: setattr(background, "size", value))  # type: ignore[attr-defined]

    def fitted_label(**kwargs: object) -> Label:
        label = Label(**kwargs)
        label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        return label

    class MailboxButton(Button):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(text="AP\nMAIL", font_name=font_name, font_size=dp(15),
                             color=(1, 1, 1, 1), background_normal="", background_color=(0, 0, 0, 0),
                             halign="center", valign="middle", **kwargs)
            paint(self, (0.74, 0.05, 0.13, 1), dp(18))

    class DeliveryToast(BoxLayout):
        def __init__(self, row: Mapping[str, object], **kwargs: object) -> None:
            super().__init__(orientation="vertical", padding=dp(14), spacing=dp(3), **kwargs)
            paint(self, (0.12, 0.55, 0.80, 0.98), dp(16))
            direction = row.get("direction")
            item = str(row.get("item_name", "Unknown item"))
            player = str(row.get("other_player", "Unknown player"))
            game = str(row.get("other_game", "Unknown game"))
            if direction == "sent":
                primary, secondary = f"↑ Sent {item}", f"to {player} • {game}"
            elif direction == "self":
                primary, secondary = f"★ Found {item}", "for yourself"
            else:
                primary, secondary = f"↓ Received {item}", f"from {player} • {game}"
            self.add_widget(fitted_label(text=primary, font_name=font_name, font_size=dp(18), bold=True,
                                         color=(1, 1, 1, 1), halign="left", valign="middle"))
            self.add_widget(fitted_label(text=secondary, font_name=font_name, font_size=dp(13),
                                         color=(0.94, 0.98, 1, 1), halign="left", valign="middle"))

    class DispatchRow(BoxLayout):
        def __init__(self, row: Mapping[str, object], **kwargs: object) -> None:
            super().__init__(orientation="horizontal", size_hint_y=None, height=dp(76),
                             padding=(dp(12), dp(8)), spacing=dp(10), **kwargs)
            direction = row.get("direction")
            icon = "↑" if direction == "sent" else "★" if direction == "self" else "↓"
            item = str(row.get("item_name", "Unknown item"))
            player = str(row.get("other_player", "Unknown player"))
            game = str(row.get("other_game", "Unknown game"))
            location = str(row.get("location_name", "Unknown location"))
            relation = "to" if direction == "sent" else "with" if direction == "self" else "from"
            self.add_widget(Label(text=icon, font_name=font_name, font_size=dp(22), size_hint_x=None,
                                  width=dp(34), color=(0.39, 0.74, 1, 1)))
            self.add_widget(fitted_label(text=f"{item}\n{relation} {player} • {game}\n{location}",
                                         font_name=font_name, font_size=dp(13), color=(1, 1, 1, 1),
                                         halign="left", valign="middle"))

    class DispatchLedger(BoxLayout):
        def __init__(self, app: "DispatchOverlayApp", payload: Mapping[str, object], **kwargs: object) -> None:
            super().__init__(orientation="vertical", padding=dp(14), spacing=dp(8), **kwargs)
            paint(self, (0.06, 0.08, 0.11, 0.98), dp(20))
            header = BoxLayout(size_hint_y=None, height=dp(58), padding=(dp(12), 0), spacing=dp(8))
            paint(header, (0.33, 0.34, 0.72, 1), dp(14))
            header.add_widget(Label(text="Archipelago Dispatches", font_name=font_name,
                                    font_size=dp(21), color=(1, 1, 1, 1), halign="left"))
            for label, value in (("All", "all"), ("Received", "received"), ("Sent", "sent")):
                button = Button(text=label, font_name=font_name, size_hint_x=None, width=dp(94),
                                background_normal="", background_color=(0.12, 0.55, 0.80, 1))
                button.bind(on_release=lambda instance, selected=value: app.send_action("filter", selected))
                header.add_widget(button)
            self.add_widget(header)
            scroll = ScrollView(do_scroll_x=False)
            rows = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
            rows.bind(minimum_height=rows.setter("height"))
            for row in payload.get("ledger_rows", []):
                if isinstance(row, Mapping):
                    rows.add_widget(DispatchRow(row))
            scroll.add_widget(rows)
            self.add_widget(scroll)
            status = str(payload.get("connection_status", "disconnected")).replace("-", " ").title()
            if payload.get("reload_required"):
                status += " • Reload your Word Factori slot to use new machinery"
            self.add_widget(Label(text=status, font_name=font_name, font_size=dp(12),
                                  size_hint_y=None, height=dp(28), color=(0.65, 0.76, 0.88, 1)))

    class DispatchOverlayApp(App):
        def __init__(self) -> None:
            super().__init__()
            self.root_layout: FloatLayout | None = None
            self.snapshot: dict[str, object] = {}
            self.geometry: OverlayGeometry | None = None
            self.tracker = Win32WindowTracker()
            self.native_hook: OverlayWindowHook | None = None
            self.last_focus: bool | None = None
            self.expiry_events: dict[str, object] = {}
            self.stopping = False
            self.display_scale = 1.0
            self.game_shown = False

        def build(self) -> FloatLayout:
            Window.clearcolor = (0, 0, 0, 0)
            root = FloatLayout()
            self.root_layout = root
            Clock.schedule_interval(self.poll_parent, 0.05)
            Clock.schedule_interval(self.follow_game, 0.10)
            Clock.schedule_once(lambda _: self.install_native_hook(), 0)
            Window.bind(on_key_down=self.on_key_down)
            return root

        def on_key_down(self, _window: object, key: int, *_args: object) -> bool:
            if key == 27 and bool(self.snapshot.get("is_open", False)):
                self.send_action("close")
                return True
            if key == VK_F8:
                self.send_action("toggle")
                return True
            return False

        def install_native_hook(self) -> None:
            if self.native_hook is not None:
                return
            hwnd = _kivy_window_handle(Window)
            if hwnd is None:
                return
            try:
                hook = OverlayWindowHook(
                    hwnd=hwnd,
                    geometry=lambda: self.geometry,
                    hotkey=lambda: self.send_action("toggle"),
                    api=CtypesOverlayHookAPI(),
                )
                hook.install()
                self.native_hook = hook
            except Exception:
                self.native_hook = None

        def send_action(self, kind: str, value: str | None = None) -> None:
            try:
                connection.send(OverlayGeometry.encode_action(kind, value))  # type: ignore[attr-defined]
            except Exception:
                self.stopping = True
                self.stop()

        def poll_parent(self, _: float) -> None:
            drained = drain_parent_messages(connection)
            if drained.disconnected:
                self.stopping = True
                self.stop()
                return
            for message in drained.messages:
                if message.kind == "shutdown":
                    self.stopping = True
                    self.stop()
                    return
                if message.kind == "settings":
                    for key, value in message.payload.items():
                        if key in validated:
                            validated[key] = value
                    continue
                self.snapshot = dict(message.payload)
                self.rebuild()

        def rebuild(self) -> None:
            if self.root_layout is None:
                return
            self.root_layout.clear_widgets()
            width, height = (max(1, int(Window.width)), max(1, int(Window.height)))
            ui_scale = float(self.snapshot.get("interface_scale", validated["interface_scale"])) * self.display_scale
            left_offset = int(self.snapshot.get("left_offset", validated["left_offset"]))
            visible = self.snapshot.get("visible_notifications", [])
            visible_rows = tuple(row for row in visible if isinstance(row, Mapping))
            ledger_open = bool(self.snapshot.get("is_open", False))
            self.geometry = OverlayGeometry.for_window(
                width=width,
                height=height,
                scale=ui_scale,
                left_offset=left_offset,
                toast_count=len(visible_rows),
                ledger_open=ledger_open,
            )
            mailbox = MailboxButton()
            self.place(mailbox, self.geometry.mailbox)
            unread = int(self.snapshot.get("unread_count", 0))
            mailbox.text = f"AP MAIL\n{unread}" if unread else "AP\nMAIL"
            mailbox.bind(on_release=lambda _: self.send_action("close" if ledger_open else "open"))
            self.root_layout.add_widget(mailbox)
            if ledger_open and self.geometry.ledger is not None:
                ledger = DispatchLedger(self, self.snapshot)
                self.place(ledger, self.geometry.ledger)
                self.root_layout.add_widget(ledger)
            else:
                for row, rectangle in zip(visible_rows, self.geometry.toasts):
                    toast = DeliveryToast(row)
                    self.place(toast, rectangle)
                    self.root_layout.add_widget(toast)
                    key = row.get("key")
                    if self.game_shown and isinstance(key, str) and key not in self.expiry_events:
                        delay = float(self.snapshot.get("notification_duration", validated["notification_duration"]))
                        self.expiry_events[key] = Clock.schedule_once(
                            lambda _, event_key=key: self.expire(event_key), delay,
                        )

        def expire(self, key: str) -> None:
            self.expiry_events.pop(key, None)
            self.send_action("expire", key)

        def cancel_expiry_events(self) -> None:
            for event in tuple(self.expiry_events.values()):
                try:
                    event.cancel()
                except Exception:
                    pass
            self.expiry_events.clear()

        def place(self, widget: object, rectangle: Rect) -> None:
            widget.size_hint = (None, None)  # type: ignore[attr-defined]
            widget.size = (rectangle.width, rectangle.height)  # type: ignore[attr-defined]
            widget.pos = (rectangle.x, max(0, int(Window.height) - rectangle.top))  # type: ignore[attr-defined]

        def follow_game(self, _: float) -> None:
            state = self.tracker.sample()
            shown = state is not None and state.visible and state.focused
            was_shown = self.game_shown
            self.game_shown = shown
            if was_shown and not shown:
                self.cancel_expiry_events()
            if self.root_layout is not None:
                self.root_layout.opacity = 1 if shown else 0
                self.root_layout.disabled = not shown
            if not shown:
                self.geometry = None
            if state is None:
                if self.last_focus is not False:
                    self.send_action("focus-lost")
                    self.last_focus = False
                return
            if self.last_focus is None or state.focused != self.last_focus:
                self.send_action("focus-returned" if state.focused else "focus-lost")
                self.last_focus = state.focused
            left, top, width, height = state.bounds
            if not math.isclose(self.display_scale, state.scale):
                self.display_scale = state.scale
                self.rebuild()
            if (Window.left, Window.top) != (left, top):
                Window.left, Window.top = left, top
            if (int(Window.width), int(Window.height)) != (width, height):
                Window.size = (width, height)
                self.rebuild()
            elif shown and not was_shown:
                self.rebuild()

        def on_stop(self) -> None:
            self.cancel_expiry_events()
            if self.native_hook is not None:
                self.native_hook.shutdown()
                self.native_hook = None

    application = DispatchOverlayApp()
    try:
        application.run()
    finally:
        if application.native_hook is not None:
            application.native_hook.shutdown()
            application.native_hook = None
