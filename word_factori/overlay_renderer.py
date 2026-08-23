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
import queue
import threading
from typing import Callable, Mapping, Protocol

from word_factori.client_core import game_font_path
from word_factori.overlay_model import OverlayAction, validate_action
from word_factori.overlay_protocol import PROTOCOL_VERSION, ParentMessage, decode_parent_message
from word_factori.overlay_supervisor import OverlayConfig
from word_factori.window_tracker import Win32WindowTracker


HTCLIENT = 1
HTTRANSPARENT = -1
WM_NCHITTEST = 0x0084
WM_HOTKEY = 0x0312
VK_F8 = 0x77
VK_ESCAPE = 0x1B
VK_LBUTTON = 0x01
MOD_NOREPEAT = 0x4000
_HOTKEY_ID = 0x5746
_ESCAPE_HOTKEY_ID = 0x5747
_GWL_EXSTYLE = -20
_GWLP_WNDPROC = -4
_WS_EX_TOPMOST = 0x00000008
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_LAYERED = 0x00080000
_WS_EX_NOACTIVATE = 0x08000000
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010


def runtime_font_path(configured: str | None, tracker: object | None) -> str | None:
    """Resolve Fredoka only from a validated explicit path or tracked game process."""
    if configured is not None:
        return configured if Path(configured).is_file() else None
    if tracker is None:
        return None
    try:
        state = tracker.sample()  # type: ignore[attr-defined]
        candidate = game_font_path(state.process_path) if state is not None else None
    except Exception:
        return None
    return str(candidate) if candidate is not None else None


class RuntimeFontResolver:
    """Remember a discovered font while allowing retries until Word Factori appears."""

    def __init__(self, configured: str | None) -> None:
        self.configured = configured
        self.resolved: str | None = None

    def resolve_state(self, state: object | None) -> str | None:
        if self.resolved is not None:
            return self.resolved
        if self.configured is not None:
            self.resolved = self.configured if Path(self.configured).is_file() else None
            return self.resolved
        try:
            process_path = state.process_path  # type: ignore[attr-defined]
            candidate = game_font_path(process_path)
        except Exception:
            return None
        self.resolved = str(candidate) if candidate is not None else None
        return self.resolved

    def resolve(self, tracker: object | None) -> str | None:
        if self.resolved is not None:
            return self.resolved
        try:
            state = tracker.sample() if tracker is not None else None  # type: ignore[attr-defined]
        except Exception:
            state = None
        return self.resolve_state(state)
_SWP_SHOWWINDOW = 0x0040
_SWP_HIDEWINDOW = 0x0080
_MAX_PIPE_MESSAGES_PER_TICK = 64
_DEFAULT_HOOK_ATTEMPTS = 30  # Three seconds at the 100 ms tracking cadence.
_DEFAULT_ACTION_CAPACITY = 64
_MIN_ROW_HEIGHT = 76
_MAX_ROW_HEIGHT = 180  # Long rows wrap and grow, but one row cannot consume the ledger.


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


def window_relative_regions(regions: tuple[Rect, ...], client_offset: tuple[int, int]) -> tuple[Rect, ...]:
    if (
        not isinstance(regions, tuple)
        or not all(isinstance(region, Rect) for region in regions)
        or not isinstance(client_offset, tuple)
        or len(client_offset) != 2
        or any(type(value) is not int for value in client_offset)
    ):
        raise ValueError("window region offset inputs are invalid")
    offset_x, offset_y = client_offset
    return tuple(Rect(region.x + offset_x, region.y + offset_y, region.width, region.height) for region in regions)


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
        margin = min(24 * ui_scale, width / 8, height / 8)
        mailbox_size = min(72 * ui_scale, width / 3, height / 3)
        mailbox_y = (height - mailbox_size) / 2 + left_offset
        mailbox = _fit_rect(margin, mailbox_y, mailbox_size, mailbox_size, width, height)
        toast_x = mailbox.right + min(16 * ui_scale, width / 16)
        toast_width = min(420 * ui_scale, width - toast_x - margin)
        if toast_width < 1:
            toast_x = margin
            toast_width = max(1, width - 2 * margin)
        available_height = max(1.0, height - 2 * margin)
        if toast_count:
            desired_height = 96 * ui_scale
            desired_gap = 12 * ui_scale
            toast_gap = min(desired_gap, available_height / max(1, toast_count * 8)) if toast_count > 1 else 0.0
            toast_height = min(desired_height, (available_height - toast_gap * (toast_count - 1)) / toast_count)
            if toast_height <= 0:
                toast_gap = 0.0
                toast_height = available_height / toast_count
            group_height = toast_height * toast_count + toast_gap * (toast_count - 1)
            group_y = max(margin, min((height - group_height) / 2 + left_offset, height - margin - group_height))
        else:
            toast_gap = 0.0
            toast_height = 0.0
            group_y = margin
        toasts = tuple(
            _fit_rect(
                toast_x,
                group_y + index * (toast_height + toast_gap),
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

    def interactive_regions(self) -> tuple[Rect, ...]:
        return (self.mailbox, *self.toasts) + (() if self.ledger is None else (self.ledger,))

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


@dataclass(frozen=True)
class RowPresentation:
    icon: str
    primary: str
    secondary: str
    metadata: str


def _display_text(row: Mapping[str, object], field: str, fallback: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) and value else fallback


def present_dispatch_row(row: Mapping[str, object]) -> RowPresentation:
    """Build truthful item-only wording without inventing historical times."""
    if not isinstance(row, Mapping):
        raise ValueError("dispatch row must be a mapping")
    direction = row.get("direction")
    if direction not in ("received", "sent", "self"):
        raise ValueError("dispatch row direction is invalid")
    item = _display_text(row, "item_name", "Unknown item")
    player = _display_text(row, "other_player", "Unknown player")
    game = _display_text(row, "other_game", "Unknown game")
    location = _display_text(row, "location_name", "Unknown location")
    if direction == "sent":
        icon, primary, secondary = "↑", f"Sent {item}", f"to {player} • {game}"
    elif direction == "self":
        icon, primary, secondary = "★", f"Found {item}", "for yourself"
    else:
        icon, primary, secondary = "↓", f"Received {item}", f"from {player} • {game}"
    if row.get("historical") is True:
        time_text = "earlier"
    else:
        time_text = _display_text(row, "observed_at", "time unavailable")
    return RowPresentation(icon, primary, secondary, f"{location} • {time_text}")


def row_height_for_texture(texture_height: object) -> int:
    if isinstance(texture_height, bool) or not isinstance(texture_height, (int, float)) or not math.isfinite(texture_height):
        raise ValueError("row texture height must be finite")
    return max(_MIN_ROW_HEIGHT, min(_MAX_ROW_HEIGHT, int(math.ceil(float(texture_height))) + 20))


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


class ChildActionWriter:
    """Bounded ordered child-to-parent writer that never blocks the Kivy thread."""

    def __init__(self, connection: object, *, capacity: int = _DEFAULT_ACTION_CAPACITY) -> None:
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("action capacity must be a positive integer")
        self._connection = connection
        self._queue: queue.Queue[str] = queue.Queue(maxsize=capacity)
        self._stopping = threading.Event()
        self._failed = threading.Event()
        self._thread = threading.Thread(target=self._run, name="Word Factori overlay actions", daemon=True)
        self._thread.start()

    @property
    def failed(self) -> bool:
        return self._failed.is_set()

    def enqueue(self, kind: str, value: str | None = None) -> bool:
        if self._stopping.is_set() or self._failed.is_set():
            return False
        encoded = OverlayGeometry.encode_action(kind, value)
        try:
            self._queue.put_nowait(encoded)
        except queue.Full:
            self._failed.set()
            self._stopping.set()
            return False
        return True

    def _run(self) -> None:
        while not self._stopping.is_set() or not self._queue.empty():
            try:
                encoded = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                self._connection.send(encoded)  # type: ignore[attr-defined]
            except Exception:
                self._failed.set()
                self._stopping.set()
                return
            finally:
                self._queue.task_done()

    def stop(self, timeout: float = 0.2) -> None:
        self._stopping.set()
        try:
            self._thread.join(timeout=max(0.0, float(timeout)))
        except Exception:
            pass


@dataclass(frozen=True)
class KeyPressState:
    pressed_since_last_poll: bool
    down: bool

    def __post_init__(self) -> None:
        if type(self.pressed_since_last_poll) is not bool or type(self.down) is not bool:
            raise ValueError("key press state must contain booleans")


class OverlayHookAPI(Protocol):
    def get_extended_style(self, hwnd: int) -> int: ...
    def set_extended_style(self, hwnd: int, style: int) -> None: ...
    def install_window_procedure(self, hwnd: int, callback: Callable[[int, int, int, int], int]) -> object: ...
    def restore_window_procedure(self, hwnd: int, original: object) -> None: ...
    def register_hotkey(self, hwnd: int, hotkey_id: int, modifiers: int, key: int) -> None: ...
    def unregister_hotkey(self, hwnd: int, hotkey_id: int) -> None: ...
    def client_point_from_lparam(self, hwnd: int, lparam: int) -> tuple[int, int]: ...
    def cursor_client_position(self, hwnd: int) -> tuple[int, int]: ...
    def key_press_state(self, key: int) -> KeyPressState: ...
    def set_window_region(self, hwnd: int, regions: tuple[Rect, ...]) -> None: ...
    def clear_window_region(self, hwnd: int) -> None: ...
    def show_no_activate(self, hwnd: int) -> None: ...
    def hide_window(self, hwnd: int) -> None: ...
    def call_original(self, original: object | None, hwnd: int, message: int, wparam: int, lparam: int) -> int: ...


class OverlayWindowHook:
    """Own extended styles/WndProc changes and restore them deterministically."""

    def __init__(
        self,
        *,
        hwnd: int,
        geometry: Callable[[], OverlayGeometry | None],
        action: Callable[[str], None],
        api: OverlayHookAPI,
    ) -> None:
        self._hwnd = hwnd
        self._geometry = geometry
        self._action = action
        self._api = api
        self._original_style: int | None = None
        self._original_procedure: object | None = None
        self._game_active = False
        self._ledger_open = False
        self._left_was_down = False
        self._escape_was_down = False
        self._f8_registered = False
        self._escape_registered = False
        self._escape_poll_fallback = False
        self._visible = False
        self._installed = False
        self._region_signature: tuple[Rect, ...] | None = None
        self._shutdown_pending = False

    @property
    def shutdown_pending(self) -> bool:
        return self._shutdown_pending

    def install(self) -> None:
        if self._installed:
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
        self._original_style = original_style
        self._original_procedure = original_procedure
        self._installed = True
        try:
            self.refresh_region(force=True)
        except Exception:
            self.shutdown()
            raise
        try:
            self._api.register_hotkey(self._hwnd, _HOTKEY_ID, MOD_NOREPEAT, VK_F8)
            self._f8_registered = True
        except Exception:
            # Region-based containment remains essential; an occupied F8 is cosmetic.
            self._f8_registered = False

    def refresh_region(self, *, force: bool = False) -> None:
        if not self._installed:
            raise RuntimeError("overlay hook is not installed")
        geometry = self._geometry()
        regions = () if geometry is None else geometry.interactive_regions()
        if not force and regions == self._region_signature:
            return
        self._api.set_window_region(self._hwnd, regions)
        self._region_signature = regions

    def set_interaction_state(self, *, game_active: bool, ledger_open: bool) -> None:
        self._game_active = bool(game_active)
        self._ledger_open = bool(ledger_open)
        wants_escape = self._game_active and self._ledger_open
        if wants_escape and not self._escape_registered and not self._escape_poll_fallback:
            try:
                self._api.register_hotkey(
                    self._hwnd, _ESCAPE_HOTKEY_ID, MOD_NOREPEAT, VK_ESCAPE,
                )
            except Exception:
                self._escape_poll_fallback = True
                try:
                    self._escape_was_down = self._api.key_press_state(VK_ESCAPE).down
                except Exception:
                    self._escape_was_down = False
            else:
                self._escape_registered = True
        elif not wants_escape:
            if self._escape_registered:
                try:
                    self._api.unregister_hotkey(self._hwnd, _ESCAPE_HOTKEY_ID)
                except Exception:
                    pass
                else:
                    self._escape_registered = False
            self._escape_poll_fallback = False
            self._escape_was_down = False

    @staticmethod
    def _new_press(state: KeyPressState, was_down: bool) -> bool:
        return state.pressed_since_last_poll or (state.down and not was_down)

    def poll_pointer(self) -> None:
        try:
            left = self._api.key_press_state(VK_LBUTTON)
            if self._new_press(left, self._left_was_down) and self._game_active and self._ledger_open:
                geometry = self._geometry()
                point = self._api.cursor_client_position(self._hwnd)
                if geometry is not None and geometry.hit_test(*point) == HTTRANSPARENT:
                    self._action("close")
            self._left_was_down = left.down
            if self._escape_poll_fallback:
                escape = self._api.key_press_state(VK_ESCAPE)
                if self._new_press(escape, self._escape_was_down) and self._game_active and self._ledger_open:
                    self._action("close")
                self._escape_was_down = escape.down
        except Exception:
            self._left_was_down = False
            self._escape_was_down = False

    def set_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if not self._installed:
            self._api.hide_window(self._hwnd)
            self._visible = False
            return
        if visible:
            self.refresh_region(force=True)
        if visible == self._visible:
            return
        if visible:
            self._api.show_no_activate(self._hwnd)
        else:
            self._api.hide_window(self._hwnd)
        self._visible = visible

    def _window_procedure(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        if message == WM_HOTKEY and int(wparam) == _HOTKEY_ID:
            if self._game_active:
                self._action("toggle")
            return 0
        if message == WM_HOTKEY and int(wparam) == _ESCAPE_HOTKEY_ID:
            if self._game_active and self._ledger_open:
                self._action("close")
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

    def shutdown(self) -> bool:
        success = True
        hidden = True
        try:
            self._api.hide_window(self._hwnd)
        except Exception:
            success = False
            hidden = False
        self._visible = False
        if self._f8_registered:
            try:
                self._api.unregister_hotkey(self._hwnd, _HOTKEY_ID)
            except Exception:
                success = False
            else:
                self._f8_registered = False
        if self._escape_registered:
            try:
                self._api.unregister_hotkey(self._hwnd, _ESCAPE_HOTKEY_ID)
            except Exception:
                success = False
            else:
                self._escape_registered = False
        region_safe = True
        if not hidden:
            try:
                self._api.set_window_region(self._hwnd, ())
            except Exception:
                success = False
                region_safe = False
            else:
                self._region_signature = ()
        elif self._region_signature is not None:
            try:
                self._api.clear_window_region(self._hwnd)
            except Exception:
                success = False
            else:
                self._region_signature = None
        if region_safe:
            if self._original_procedure is not None:
                try:
                    self._api.restore_window_procedure(self._hwnd, self._original_procedure)
                except Exception:
                    success = False
                else:
                    self._original_procedure = None
                    self._installed = False
            if self._original_style is not None:
                try:
                    self._api.set_extended_style(self._hwnd, self._original_style)
                except Exception:
                    success = False
                else:
                    self._original_style = None
        self._shutdown_pending = not success
        return success


class NativeHookBootstrap:
    """Fail-closed bounded acquisition of the overlay HWND and essential hook."""

    def __init__(
        self,
        *,
        handle_provider: Callable[[], int | None],
        api_factory: Callable[[], OverlayHookAPI],
        geometry: Callable[[], OverlayGeometry | None],
        action: Callable[[str], None],
        max_attempts: int = _DEFAULT_HOOK_ATTEMPTS,
    ) -> None:
        if type(max_attempts) is not int or max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")
        self._handle_provider = handle_provider
        self._api_factory = api_factory
        self._geometry = geometry
        self._action = action
        self._max_attempts = max_attempts
        self._attempts = 0
        self._status = "pending"
        self.hook: OverlayWindowHook | None = None

    @property
    def status(self) -> str:
        return self._status

    def tick(self) -> str:
        if self._status != "pending":
            return self._status
        self._attempts += 1
        hook: OverlayWindowHook | None = None
        try:
            hwnd = self._handle_provider()
            if type(hwnd) is not int or hwnd <= 0:
                raise LookupError("overlay window handle is not ready")
            api = self._api_factory()
            api.hide_window(hwnd)
            hook = OverlayWindowHook(hwnd=hwnd, geometry=self._geometry, action=self._action, api=api)
            hook.install()
        except Exception:
            if hook is not None and not hook.shutdown():
                self.hook = hook
                self._status = "failed"
                return self._status
            if self._attempts >= self._max_attempts:
                self._status = "failed"
            return self._status
        self.hook = hook
        self._status = "ready"
        return self._status

    def _fail_closed(self) -> bool:
        self._status = "failed"
        if self.hook is not None:
            try:
                self.hook.set_visible(False)
            except Exception:
                pass
            if self.hook.shutdown():
                self.hook = None
        return False

    def refresh_region(self, *, force: bool = False) -> bool:
        if self._status != "ready" or self.hook is None:
            return False
        try:
            self.hook.refresh_region(force=force)
        except Exception:
            return self._fail_closed()
        return True

    def set_visible(self, visible: bool) -> bool:
        if self._status != "ready" or self.hook is None:
            return not visible
        try:
            self.hook.set_visible(visible)
        except Exception:
            return self._fail_closed()
        return True

    def shutdown(self) -> bool:
        success = True
        if self.hook is not None:
            success = self.hook.shutdown()
            if success:
                self.hook = None
        self._status = "failed"
        return success


class CtypesOverlayHookAPI:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("native overlay hooks are available only on Windows")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
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
        self._user32.IsWindowVisible.argtypes = (wintypes.HWND,)
        self._user32.IsWindowVisible.restype = wintypes.BOOL
        self._user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
        self._user32.GetCursorPos.restype = wintypes.BOOL
        self._user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
        self._user32.GetAsyncKeyState.restype = ctypes.c_short
        self._user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        self._user32.GetWindowRect.restype = wintypes.BOOL
        self._user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
        self._user32.ClientToScreen.restype = wintypes.BOOL
        self._user32.SetWindowRgn.argtypes = (wintypes.HWND, wintypes.HANDLE, wintypes.BOOL)
        self._user32.SetWindowRgn.restype = ctypes.c_int
        self._gdi32.CreateRectRgn.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
        self._gdi32.CreateRectRgn.restype = wintypes.HANDLE
        self._gdi32.CombineRgn.argtypes = (wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE, ctypes.c_int)
        self._gdi32.CombineRgn.restype = ctypes.c_int
        self._gdi32.DeleteObject.argtypes = (wintypes.HANDLE,)
        self._gdi32.DeleteObject.restype = wintypes.BOOL

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
        ctypes.set_last_error(0)
        result = self._set_long(hwnd, _GWLP_WNDPROC, int(original))
        if not result and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        self._callbacks.pop(hwnd, None)

    def register_hotkey(self, hwnd: int, hotkey_id: int, modifiers: int, key: int) -> None:
        if not self._user32.RegisterHotKey(hwnd, hotkey_id, modifiers, key):
            raise ctypes.WinError(ctypes.get_last_error())

    def unregister_hotkey(self, hwnd: int, hotkey_id: int) -> None:
        self._user32.UnregisterHotKey(hwnd, hotkey_id)

    def client_point_from_lparam(self, hwnd: int, lparam: int) -> tuple[int, int]:
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        point = wintypes.POINT(x, y)
        if not self._user32.ScreenToClient(hwnd, ctypes.byref(point)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(point.x), int(point.y)

    def cursor_client_position(self, hwnd: int) -> tuple[int, int]:
        point = wintypes.POINT()
        if not self._user32.GetCursorPos(ctypes.byref(point)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self._user32.ScreenToClient(hwnd, ctypes.byref(point)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(point.x), int(point.y)

    def key_press_state(self, key: int) -> KeyPressState:
        raw = int(self._user32.GetAsyncKeyState(key)) & 0xFFFF
        return KeyPressState(bool(raw & 0x0001), bool(raw & 0x8000))

    def _client_window_offset(self, hwnd: int) -> tuple[int, int]:
        window = wintypes.RECT()
        client_origin = wintypes.POINT(0, 0)
        if not self._user32.GetWindowRect(hwnd, ctypes.byref(window)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self._user32.ClientToScreen(hwnd, ctypes.byref(client_origin)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(client_origin.x - window.left), int(client_origin.y - window.top)

    def set_window_region(self, hwnd: int, regions: tuple[Rect, ...]) -> None:
        regions = window_relative_regions(regions, self._client_window_offset(hwnd))
        combined = self._gdi32.CreateRectRgn(0, 0, 0, 0)
        if not combined:
            raise ctypes.WinError(ctypes.get_last_error())
        transferred = False
        try:
            for rectangle in regions:
                part = self._gdi32.CreateRectRgn(
                    rectangle.x, rectangle.y, rectangle.right, rectangle.top,
                )
                if not part:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if self._gdi32.CombineRgn(combined, combined, part, 2) == 0:
                        raise ctypes.WinError(ctypes.get_last_error())
                finally:
                    self._gdi32.DeleteObject(part)
            if not self._user32.SetWindowRgn(hwnd, combined, True):
                raise ctypes.WinError(ctypes.get_last_error())
            transferred = True  # Windows owns the combined HRGN after successful SetWindowRgn.
        finally:
            if not transferred:
                self._gdi32.DeleteObject(combined)

    def clear_window_region(self, hwnd: int) -> None:
        if not self._user32.SetWindowRgn(hwnd, None, True):
            raise ctypes.WinError(ctypes.get_last_error())

    def _set_native_visibility(self, hwnd: int, visible: bool) -> None:
        flags = _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOZORDER | _SWP_NOACTIVATE
        flags |= _SWP_SHOWWINDOW if visible else _SWP_HIDEWINDOW
        ctypes.set_last_error(0)
        if not self._user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags):
            raise ctypes.WinError(ctypes.get_last_error())
        if bool(self._user32.IsWindowVisible(hwnd)) is not visible:
            requested = "visible" if visible else "hidden"
            raise OSError(f"overlay window did not reach requested {requested} state")

    def show_no_activate(self, hwnd: int) -> None:
        self._set_native_visibility(hwnd, True)

    def hide_window(self, hwnd: int) -> None:
        self._set_native_visibility(hwnd, False)

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
                if int(pid.value) == current_pid and user32.IsWindow(hwnd):
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
    try:
        tracker = Win32WindowTracker()
    except Exception:
        tracker = None
    font_resolver = RuntimeFontResolver(validated["font_path"])
    validated["font_path"] = font_resolver.resolve(tracker)

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
            presentation = present_dispatch_row(row)
            self.add_widget(Label(text=presentation.icon, font_name=font_name, font_size=dp(22), size_hint_x=None,
                                  width=dp(34), color=(0.39, 0.74, 1, 1)))
            details = Label(
                text=f"{presentation.primary}\n{presentation.secondary}\n{presentation.metadata}",
                font_name=font_name, font_size=dp(13), color=(1, 1, 1, 1),
                halign="left", valign="middle",
            )
            details.bind(width=lambda instance, value: setattr(instance, "text_size", (value, None)))
            details.bind(texture_size=lambda _instance, value: self.resize_for_texture(value[1]))
            self.add_widget(details)

        def resize_for_texture(self, texture_height: float) -> None:
            self.height = dp(row_height_for_texture(texture_height))

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
            self.action_writer = ChildActionWriter(connection)
            self.native = NativeHookBootstrap(
                handle_provider=lambda: _kivy_window_handle(Window),
                api_factory=CtypesOverlayHookAPI,
                geometry=lambda: self.geometry,
                action=lambda kind: self.send_action(kind),
            )
            self.last_focus: bool | None = None
            self.expiry_events: dict[str, object] = {}
            self.stopping = False
            self.display_scale = 1.0
            self.game_shown = False

        def build(self) -> FloatLayout:
            Window.clearcolor = (0, 0, 0, 0)
            try:
                Window.hide()
            except Exception:
                pass
            root = FloatLayout()
            self.root_layout = root
            Clock.schedule_interval(self.poll_parent, 0.05)
            Clock.schedule_interval(self.follow_game, 0.10)
            return root

        def send_action(self, kind: str, value: str | None = None) -> None:
            try:
                accepted = self.action_writer.enqueue(kind, value)
            except Exception:
                accepted = False
            if not accepted:
                self.stopping = True
                self.stop()

        def poll_parent(self, _: float) -> None:
            if self.action_writer.failed:
                self.stopping = True
                self.stop()
                return
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
            if self.native.status == "ready" and not self.native.refresh_region(force=True):
                self.stopping = True
                self.stop()
                return
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
            nonlocal font_name
            native_status = self.native.tick()
            if native_status == "failed":
                self.stopping = True
                self.stop()
                return
            state = self.tracker.sample()
            if font_name == "Roboto":
                font_value = font_resolver.resolve_state(state)
                if font_value is not None:
                    try:
                        LabelBase.register(name="WordFactoriFredoka", fn_regular=font_value)
                    except Exception:
                        pass
                    else:
                        font_name = "WordFactoriFredoka"
                        self.rebuild()
            game_active = state is not None and state.visible and state.focused
            shown = game_active and native_status == "ready"
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
                if self.native.hook is not None:
                    self.native.hook.set_interaction_state(game_active=False, ledger_open=False)
                    self.native.hook.poll_pointer()
                if not self.native.set_visible(False):
                    self.stopping = True
                    self.stop()
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
            if self.native.hook is not None:
                ledger_open = bool(self.snapshot.get("is_open", False))
                self.native.hook.set_interaction_state(game_active=game_active, ledger_open=ledger_open)
                self.native.hook.poll_pointer()
            if not self.native.set_visible(shown):
                self.stopping = True
                self.stop()

        def on_stop(self) -> None:
            self.cancel_expiry_events()
            self.native.shutdown()
            self.action_writer.stop(0.2)

    application = DispatchOverlayApp()
    try:
        application.run()
    finally:
        application.native.shutdown()
        application.action_writer.stop(0.2)
