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
    return int(value)


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
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be boolean")
        if type(self.reduced_motion) is not bool:
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
        if self.font_path is not None:
            object.__setattr__(self, "font_path", str(self.font_path))


def _validated_config_primitives(config: object) -> dict[str, object] | None:
    """Revalidate exact config fields without invoking instance-controlled code."""
    if type(config) is not OverlayConfig:
        return None
    try:
        canonical = OverlayConfig(
            enabled=config.enabled,
            interface_scale=config.interface_scale,
            left_offset=config.left_offset,
            notification_duration=config.notification_duration,
            reduced_motion=config.reduced_motion,
            max_visible=config.max_visible,
            font_path=config.font_path,
        )
    except (TypeError, ValueError):
        return None
    return {
        "enabled": bool(canonical.enabled),
        "interface_scale": float(canonical.interface_scale),
        "left_offset": int(canonical.left_offset),
        "notification_duration": float(canonical.notification_duration),
        "reduced_motion": bool(canonical.reduced_motion),
        "max_visible": int(canonical.max_visible),
        "font_path": None if canonical.font_path is None else str(canonical.font_path),
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


@dataclass(frozen=True)
class _ActiveResources:
    connection: object
    process: object
    mailbox: _LatestMailbox
    writer: threading.Thread
    writer_failed: threading.Event


class OverlaySupervisor:
    """Own one optional renderer child without exposing failures to game logic."""

    def __init__(self, *, process_context: object | None = None, target: RendererTarget | None = None) -> None:
        self._context = process_context or multiprocessing.get_context("spawn")
        self._target = _top_level_target(target or _default_renderer_target)
        self._lifecycle_lock = threading.RLock()
        self._active_lock = threading.Lock()
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
        copied = _validated_config_primitives(config)
        if copied is None:
            return False
        with self._lifecycle_lock:
            with self._active_lock:
                if self.disabled:
                    return False
                active = self._active_resources_locked()
                current_config = self._config
            if active is not None:
                try:
                    alive = bool(active.process.is_alive())  # type: ignore[attr-defined]
                except Exception:
                    alive = False
                if alive and not active.writer_failed.is_set():
                    return copied == current_config
                with self._active_lock:
                    self._config = copied
                return self._restart_active(copied)
            with self._active_lock:
                self._config = copied
            created = self._create_resources(copied)
            if created is None:
                return False
            self._attach_active(created)
            return True

    def _create_resources(self, config: dict[str, object]) -> _ActiveResources | None:
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
                args=(child, dict(config)),
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
            return _ActiveResources(parent, process, mailbox, writer, writer_failed)
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
            return None

    def _active_resources_locked(self) -> _ActiveResources | None:
        if self._process is None:
            return None
        if (
            self._connection is None
            or self._mailbox is None
            or self._writer is None
            or self._writer_failed is None
        ):
            return None
        return _ActiveResources(
            self._connection, self._process, self._mailbox, self._writer, self._writer_failed,
        )

    def _attach_active(self, resources: _ActiveResources) -> None:
        with self._active_lock:
            self._connection = resources.connection
            self._process = resources.process
            self._mailbox = resources.mailbox
            self._writer = resources.writer
            self._writer_failed = resources.writer_failed

    def _detach_active(self) -> _ActiveResources | None:
        with self._active_lock:
            resources = self._active_resources_locked()
            self._connection = None
            self._process = None
            self._mailbox = None
            self._writer = None
            self._writer_failed = None
            return resources

    def _restart_active(self, config: dict[str, object]) -> bool:
        resources = self._detach_active()
        if resources is not None:
            self._cleanup_resources(resources, timeout=0.1, request_shutdown=False)
        with self._active_lock:
            if self._restarts >= 1:
                self.disabled = True
                return False
            self._restarts += 1
        created = self._create_resources(config)
        if created is None:
            with self._active_lock:
                self.disabled = True
            return False
        self._attach_active(created)
        return True

    def publish(self, value: OverlaySnapshot) -> bool:
        """Publish one encoded snapshot; renderer failures remain cosmetic."""
        try:
            encoded = encode_parent_message(snapshot_message(value))
        except (TypeError, ValueError):
            return False
        with self._active_lock:
            mailbox = self._mailbox
            writer_failed = self._writer_failed
            if self.disabled or mailbox is None:
                return False
        if writer_failed is not None and writer_failed.is_set():
            return False
        try:
            return mailbox.publish(encoded)
        except Exception:
            return False

    def poll_actions(self) -> tuple[OverlayAction, ...]:
        """Drain currently available child actions without ever blocking."""
        with self._active_lock:
            connection = self._connection
            if self.disabled or connection is None:
                return ()
        actions: list[OverlayAction] = []
        for _ in range(_MAX_ACTIONS_PER_POLL):
            try:
                if not connection.poll(0.0):  # type: ignore[attr-defined]
                    break
                encoded = connection.recv()  # type: ignore[attr-defined]
            except Exception:
                break
            try:
                actions.append(decode_child_action(encoded))
            except (TypeError, ValueError):
                continue
        return tuple(actions)

    def health_check(self) -> None:
        """Restart one crashed renderer, then disable it for this session."""
        with self._lifecycle_lock:
            with self._active_lock:
                if self.disabled:
                    return
                active = self._active_resources_locked()
                config = dict(self._config or {})
            if active is None:
                return
            try:
                alive = bool(active.process.is_alive())  # type: ignore[attr-defined]
            except Exception:
                alive = False
            if alive and not active.writer_failed.is_set():
                return
            self._restart_active(config)

    def _cleanup_resources(self, resources: _ActiveResources, *, timeout: float, request_shutdown: bool) -> None:
        connection, process = resources.connection, resources.process
        mailbox, writer = resources.mailbox, resources.writer
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
        if writer is not None:
            try:
                alive_writer = bool(writer.is_alive())
            except Exception:
                alive_writer = False
            if alive_writer:
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
                    pass
                else:
                    try:
                        process.join(timeout=timeout)
                    except Exception:
                        pass
        if writer is not None:
            try:
                if writer.is_alive():
                    # Closing the real pipe and terminating its peer should release send();
                    # a hostile fake can survive only as the deliberately daemonized fallback.
                    writer.join(timeout=timeout)
            except Exception:
                pass

    def stop(self, timeout: float = 2.0) -> None:
        """Request shutdown, then bound cleanup; safe to call repeatedly."""
        with self._lifecycle_lock:
            resources = self._detach_active()
            if resources is not None:
                self._cleanup_resources(resources, timeout=timeout, request_shutdown=True)
