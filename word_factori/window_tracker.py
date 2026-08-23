"""Narrow, side-effect-free Win32 discovery for the Word Factori window."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import ntpath
import os
from pathlib import Path
from typing import Protocol


GAME_EXECUTABLE = "word factori.exe"
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True)
class WindowState:
    hwnd: int
    process_path: Path
    bounds: tuple[int, int, int, int]
    scale: float
    visible: bool
    focused: bool

    def __post_init__(self) -> None:
        if type(self.hwnd) is not int or self.hwnd <= 0:
            raise ValueError("window handle must be a positive integer")
        if not isinstance(self.process_path, Path):
            raise ValueError("process_path must be a Path")
        if (
            not isinstance(self.bounds, tuple)
            or len(self.bounds) != 4
            or any(type(value) is not int for value in self.bounds)
            or self.bounds[2] <= 0
            or self.bounds[3] <= 0
        ):
            raise ValueError("window bounds are invalid")
        if not isinstance(self.scale, float) or not 0.5 <= self.scale <= 8.0:
            raise ValueError("window scale is invalid")
        if type(self.visible) is not bool or type(self.focused) is not bool:
            raise ValueError("window visibility state is invalid")


class Win32API(Protocol):
    def enum_windows(self) -> tuple[int, ...]: ...
    def is_window(self, hwnd: int) -> bool: ...
    def window_process_id(self, hwnd: int) -> int: ...
    def open_process(self, pid: int) -> object | None: ...
    def process_path(self, handle: object) -> str: ...
    def close_handle(self, handle: object) -> None: ...
    def window_rect(self, hwnd: int) -> tuple[int, int, int, int]: ...
    def is_window_visible(self, hwnd: int) -> bool: ...
    def is_minimized(self, hwnd: int) -> bool: ...
    def foreground_window(self) -> int: ...
    def dpi_for_window(self, hwnd: int) -> int: ...


class CtypesWin32API:
    """Minimal ctypes adapter. Construction is explicit and never runs at import."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Win32 window tracking is available only on Windows")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_functions()

    def _configure_functions(self) -> None:
        self._enum_callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self._user32.EnumWindows.argtypes = (self._enum_callback_type, wintypes.LPARAM)
        self._user32.EnumWindows.restype = wintypes.BOOL
        self._user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._user32.IsWindow.argtypes = (wintypes.HWND,)
        self._user32.IsWindow.restype = wintypes.BOOL
        self._user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        self._user32.GetWindowRect.restype = wintypes.BOOL
        self._user32.IsWindowVisible.argtypes = (wintypes.HWND,)
        self._user32.IsWindowVisible.restype = wintypes.BOOL
        self._user32.IsIconic.argtypes = (wintypes.HWND,)
        self._user32.IsIconic.restype = wintypes.BOOL
        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        )
        self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        if hasattr(self._user32, "GetDpiForWindow"):
            self._user32.GetDpiForWindow.argtypes = (wintypes.HWND,)
            self._user32.GetDpiForWindow.restype = wintypes.UINT

    def enum_windows(self) -> tuple[int, ...]:
        windows: list[int] = []

        @self._enum_callback_type
        def collect(hwnd: int, _: int) -> bool:
            windows.append(int(hwnd))
            return True

        if not self._user32.EnumWindows(collect, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        return tuple(windows)

    def window_process_id(self, hwnd: int) -> int:
        pid = wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)

    def is_window(self, hwnd: int) -> bool:
        return bool(self._user32.IsWindow(hwnd))

    def open_process(self, pid: int) -> object | None:
        return self._kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid) or None

    def process_path(self, handle: object) -> str:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not self._kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.value

    def close_handle(self, handle: object) -> None:
        self._kernel32.CloseHandle(handle)

    def window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        rect = wintypes.RECT()
        if not self._user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)

    def is_window_visible(self, hwnd: int) -> bool:
        return bool(self._user32.IsWindowVisible(hwnd))

    def is_minimized(self, hwnd: int) -> bool:
        return bool(self._user32.IsIconic(hwnd))

    def foreground_window(self) -> int:
        return int(self._user32.GetForegroundWindow() or 0)

    def dpi_for_window(self, hwnd: int) -> int:
        function = getattr(self._user32, "GetDpiForWindow", None)
        return int(function(hwnd)) if function is not None else 96


class Win32WindowTracker:
    """Find the first top-level window owned by the exact Word Factori executable."""

    def __init__(self, api: Win32API | None = None) -> None:
        self.api = api if api is not None else CtypesWin32API()

    def sample(self) -> WindowState | None:
        try:
            windows = tuple(self.api.enum_windows())
        except Exception:
            return None
        candidates: list[WindowState] = []
        for hwnd in windows:
            state = self._sample_candidate(hwnd)
            if state is not None:
                candidates.append(state)
        return max(candidates, key=lambda state: (state.focused, state.visible), default=None)

    def _sample_candidate(self, hwnd: object) -> WindowState | None:
        if type(hwnd) is not int or hwnd <= 0:
            return None
        handle: object | None = None
        try:
            if not self.api.is_window(hwnd):
                return None
            pid = self.api.window_process_id(hwnd)
            if type(pid) is not int or pid <= 0:
                return None
            handle = self.api.open_process(pid)
            if handle is None:
                return None
            process_name = self.api.process_path(handle)
            if not isinstance(process_name, str) or ntpath.basename(process_name).casefold() != GAME_EXECUTABLE:
                return None
            left, top, right, bottom = self.api.window_rect(hwnd)
            if any(type(value) is not int for value in (left, top, right, bottom)):
                return None
            width, height = right - left, bottom - top
            if width <= 0 or height <= 0:
                return None
            dpi = self.api.dpi_for_window(hwnd)
            if type(dpi) is not int or dpi <= 0:
                dpi = 96
            visible = bool(self.api.is_window_visible(hwnd)) and not bool(self.api.is_minimized(hwnd))
            focused = self.api.foreground_window() == hwnd
            return WindowState(
                hwnd=hwnd,
                process_path=Path(process_name),
                bounds=(left, top, width, height),
                scale=float(dpi / 96.0),
                visible=visible,
                focused=focused,
            )
        except Exception:
            return None
        finally:
            if handle is not None:
                try:
                    self.api.close_handle(handle)
                except Exception:
                    pass
