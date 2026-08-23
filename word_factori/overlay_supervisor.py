"""Failure-isolated ownership of the optional overlay renderer process."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import math
import multiprocessing
import threading
from typing import Callable, Mapping

from word_factori.overlay_model import OverlayAction, OverlaySnapshot
from word_factori.overlay_protocol import (
    decode_child_action,
    encode_parent_message,
    shutdown_message,
    snapshot_message,
)


RendererTarget = Callable[[object, Mapping[str, object]], None]
_MAX_ACTIONS_PER_POLL = 64


def _bounded_number(value: object, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    converted = float(value)
    if not minimum <= converted <= maximum:
        raise ValueError(f"{field} is outside its allowed range")
    return converted


def _bounded_integer(value: object, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{field} is outside its allowed range")
    return value


@dataclass(frozen=True)
class OverlayConfig:
    """Exact visual-only values that may cross into the renderer process."""

    enabled: bool = True
    interface_scale: float = 1.0
    left_offset: int = 0
    notification_duration: float = 6.0
    reduced_motion: bool = False
    max_visible: int = 3
    font_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be boolean")
        if not isinstance(self.reduced_motion, bool):
            raise ValueError("reduced_motion must be boolean")
        object.__setattr__(self, "interface_scale", _bounded_number(
            self.interface_scale, "interface_scale", 0.75, 2.0,
        ))
        object.__setattr__(self, "left_offset", _bounded_integer(
            self.left_offset, "left_offset", -2000, 2000,
        ))
        object.__setattr__(self, "notification_duration", _bounded_number(
            self.notification_duration, "notification_duration", 1.0, 30.0,
        ))
        object.__setattr__(self, "max_visible", _bounded_integer(
            self.max_visible, "max_visible", 1, 10,
        ))
        if self.font_path is not None and (
            not isinstance(self.font_path, str) or not self.font_path.strip() or len(self.font_path) > 32767
        ):
            raise ValueError("font_path must be bounded non-blank text or null")

    def as_primitives(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "interface_scale": self.interface_scale,
            "left_offset": self.left_offset,
            "notification_duration": self.notification_duration,
            "reduced_motion": self.reduced_motion,
            "max_visible": self.max_visible,
            "font_path": self.font_path,
        }


def _default_renderer_target(connection: object, config: Mapping[str, object]) -> None:
    """Resolve the GUI entry point only inside the spawned child."""
    try:
        from word_factori.overlay_renderer import overlay_process_main

        overlay_process_main(connection, config)
    finally:
        try:
            connection.close()  # type: ignore[attr-defined]
        except Exception:
            pass


def _top_level_target(target: object) -> RendererTarget:
    module_name = getattr(target, "__module__", None)
    qualified_name = getattr(target, "__qualname__", None)
    if (
        not callable(target)
        or not isinstance(module_name, str)
        or not isinstance(qualified_name, str)
        or "<locals>" in qualified_name
        or "<lambda>" in qualified_name
    ):
        raise ValueError("overlay target must be a top-level importable callable")
    try:
        resolved: object = importlib.import_module(module_name)
        for component in qualified_name.split("."):
            resolved = getattr(resolved, component)
    except (ImportError, AttributeError) as error:
        raise ValueError("overlay target must be a top-level importable callable") from error
    if resolved is not target:
        raise ValueError("overlay target must be a top-level importable callable")
    return target  # type: ignore[return-value]


class _LatestMailbox:
    """A thread-safe, size-one mailbox whose newest snapshot wins."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._value: str | None = None
        self._closed = False

    def publish(self, value: str) -> bool:
        with self._lock:
            if self._closed:
                return False
            self._value = value
            self._ready.set()
            return True

    def close(self, final_value: str | None = None) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._value = final_value
            self._ready.set()

    def take(self) -> str | None:
        while True:
            self._ready.wait()
            with self._lock:
                if self._value is not None:
                    value = self._value
                    self._value = None
                    if not self._closed:
                        self._ready.clear()
                    return value
                if self._closed:
                    return None
                self._ready.clear()


def _writer_main(connection: object, mailbox: _LatestMailbox, failed: threading.Event) -> None:
    while True:
        encoded = mailbox.take()
        if encoded is None:
            return
        try:
            connection.send(encoded)  # type: ignore[attr-defined]
        except Exception:
            failed.set()
            mailbox.close()
            return


class OverlaySupervisor:
    """Own one optional renderer child without exposing failures to game logic."""

    def __init__(self, *, process_context: object | None = None, target: RendererTarget | None = None) -> None:
        self._context = process_context or multiprocessing.get_context("spawn")
        self._target = _top_level_target(target or _default_renderer_target)
        self._connection: object | None = None
        self._process: object | None = None
        self._mailbox: _LatestMailbox | None = None
        self._writer: threading.Thread | None = None
        self._writer_failed: threading.Event | None = None
        self._config: dict[str, object] | None = None
        self._restarts = 0
        self.disabled = False

    @property
    def process_context(self) -> object:
        return self._context

    def start(self, config: OverlayConfig) -> bool:
        """Start the renderer, or report cosmetic unavailability without raising."""
        if self.disabled:
            return False
        if not isinstance(config, OverlayConfig):
            return False
        copied = config.as_primitives()
        if self._process is not None:
            try:
                alive = bool(self._process.is_alive())  # type: ignore[attr-defined]
            except Exception:
                alive = False
            writer_failed = self._writer_failed is not None and self._writer_failed.is_set()
            if alive and not writer_failed:
                return copied == self._config
            self._config = copied
            self.health_check()
            return self._process is not None and not self.disabled
        self._config = copied
        return self._launch()

    def _launch(self) -> bool:
        parent = None
        child = None
        process = None
        mailbox = None
        writer = None
        writer_failed = None
        started = False
        try:
            multiprocessing.freeze_support()
            parent, child = self._context.Pipe(duplex=True)  # type: ignore[attr-defined]
            process = self._context.Process(  # type: ignore[attr-defined]
                target=self._target,
                args=(child, dict(self._config or {})),
            )
            process.daemon = True
            process.start()
            started = True
            child.close()
            mailbox = _LatestMailbox()
            writer_failed = threading.Event()
            writer = threading.Thread(
                target=_writer_main,
                args=(parent, mailbox, writer_failed),
                name="Word Factori overlay writer",
                daemon=True,
            )
            writer.start()
            self._connection = parent
            self._process = process
            self._mailbox = mailbox
            self._writer = writer
            self._writer_failed = writer_failed
            return True
        except Exception:
            if mailbox is not None:
                mailbox.close()
            for resource in (parent, child):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass
            if writer is not None:
                try:
                    writer.join(timeout=0.1)
                except Exception:
                    pass
            if process is not None and started:
                try:
                    if process.is_alive():
                        process.terminate()
                except Exception:
                    try:
                        process.terminate()
                    except Exception:
                        pass
                try:
                    process.join(timeout=0.1)
                except Exception:
                    pass
            return False

    def publish(self, value: OverlaySnapshot) -> bool:
        """Publish one encoded snapshot; renderer failures remain cosmetic."""
        if self.disabled or self._mailbox is None:
            return False
        try:
            encoded = encode_parent_message(snapshot_message(value))
        except (TypeError, ValueError):
            return False
        if self._writer_failed is not None and self._writer_failed.is_set():
            return False
        return self._mailbox.publish(encoded)

    def poll_actions(self) -> tuple[OverlayAction, ...]:
        """Drain currently available child actions without ever blocking."""
        if self.disabled or self._connection is None:
            return ()
        actions: list[OverlayAction] = []
        for _ in range(_MAX_ACTIONS_PER_POLL):
            try:
                if not self._connection.poll(0.0):  # type: ignore[attr-defined]
                    break
                encoded = self._connection.recv()  # type: ignore[attr-defined]
            except Exception:
                break
            try:
                actions.append(decode_child_action(encoded))
            except (TypeError, ValueError):
                continue
        return tuple(actions)

    def health_check(self) -> None:
        """Restart one crashed renderer, then disable it for this session."""
        if self.disabled or self._process is None:
            return
        try:
            alive = bool(self._process.is_alive())  # type: ignore[attr-defined]
        except Exception:
            alive = False
        writer_failed = self._writer_failed is not None and self._writer_failed.is_set()
        if alive and not writer_failed:
            return
        self._release_current(timeout=0.1, request_shutdown=False)
        if self._restarts >= 1:
            self.disabled = True
            return
        self._restarts += 1
        if not self._launch():
            self.disabled = True

    def _release_current(self, *, timeout: float, request_shutdown: bool) -> None:
        connection, process = self._connection, self._process
        mailbox, writer = self._mailbox, self._writer
        self._connection = None
        self._process = None
        self._mailbox = None
        self._writer = None
        self._writer_failed = None
        if mailbox is not None:
            final = encode_parent_message(shutdown_message()) if request_shutdown else None
            mailbox.close(final)
        if writer is not None:
            try:
                writer.join(timeout=timeout)
            except Exception:
                pass
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        if writer is not None and writer.is_alive():
            try:
                writer.join(timeout=timeout)
            except Exception:
                pass
        if process is not None:
            try:
                process.join(timeout=timeout)
            except Exception:
                pass
            try:
                alive = bool(process.is_alive())
            except Exception:
                alive = True
            if alive:
                try:
                    process.terminate()
                except Exception:
                    return
                try:
                    process.join(timeout=timeout)
                except Exception:
                    pass

    def stop(self, timeout: float = 2.0) -> None:
        """Request shutdown, then bound cleanup; safe to call repeatedly."""
        self._release_current(timeout=timeout, request_shutdown=True)
