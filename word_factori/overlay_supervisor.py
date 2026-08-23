"""Failure-isolated ownership of the optional overlay renderer process."""

from __future__ import annotations

import importlib
import math
import multiprocessing
from typing import Callable, Mapping

from word_factori.overlay_model import OverlayAction, OverlaySnapshot
from word_factori.overlay_protocol import (
    decode_child_action,
    encode_parent_message,
    shutdown_message,
    snapshot_message,
)


RendererTarget = Callable[[object, Mapping[str, object]], None]


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


def _copy_primitive(value: object) -> object:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("overlay config numbers must be finite")
        return value
    if isinstance(value, (list, tuple)):
        return [_copy_primitive(item) for item in value]
    if isinstance(value, Mapping):
        if not all(type(key) is str for key in value):
            raise ValueError("overlay config keys must be strings")
        return {key: _copy_primitive(item) for key, item in value.items()}
    raise ValueError("overlay config must contain only JSON primitives")


def _config_copy(config: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(config, Mapping):
        raise ValueError("overlay config must be a mapping")
    copied = _copy_primitive(config)
    if not isinstance(copied, dict):
        raise ValueError("overlay config must be a mapping")
    return copied


class OverlaySupervisor:
    """Own one optional renderer child without exposing failures to game logic."""

    def __init__(self, *, process_context: object | None = None, target: RendererTarget | None = None) -> None:
        self._context = process_context or multiprocessing.get_context("spawn")
        self._target = _top_level_target(target or _default_renderer_target)
        self._connection: object | None = None
        self._process: object | None = None
        self._config: dict[str, object] | None = None
        self._restarts = 0
        self.disabled = False

    @property
    def process_context(self) -> object:
        return self._context

    def start(self, config: Mapping[str, object]) -> bool:
        """Start the renderer, or report cosmetic unavailability without raising."""
        if self.disabled:
            return False
        try:
            copied = _config_copy(config)
        except (TypeError, ValueError):
            return False
        if self._process is not None:
            try:
                if self._process.is_alive():  # type: ignore[attr-defined]
                    return True
            except Exception:
                pass
            self.health_check()
            return self._process is not None and not self.disabled
        self._config = copied
        return self._launch()

    def _launch(self) -> bool:
        parent = None
        child = None
        process = None
        try:
            multiprocessing.freeze_support()
            parent, child = self._context.Pipe(duplex=True)  # type: ignore[attr-defined]
            process = self._context.Process(  # type: ignore[attr-defined]
                target=self._target,
                args=(child, dict(self._config or {})),
            )
            process.daemon = True
            process.start()
            child.close()
            self._connection = parent
            self._process = process
            return True
        except Exception:
            for resource in (parent, child):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass
            if process is not None:
                try:
                    process.join(timeout=0.0)
                except Exception:
                    pass
            return False

    def publish(self, value: OverlaySnapshot) -> bool:
        """Publish one encoded snapshot; renderer failures remain cosmetic."""
        if self.disabled or self._connection is None:
            return False
        try:
            encoded = encode_parent_message(snapshot_message(value))
            self._connection.send(encoded)  # type: ignore[attr-defined]
            return True
        except Exception:
            return False

    def poll_actions(self) -> tuple[OverlayAction, ...]:
        """Drain currently available child actions without ever blocking."""
        if self.disabled or self._connection is None:
            return ()
        actions: list[OverlayAction] = []
        while True:
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
        if alive:
            return
        self._release_dead_process()
        if self._restarts >= 1:
            self.disabled = True
            return
        self._restarts += 1
        if not self._launch():
            self.disabled = True

    def _release_dead_process(self) -> None:
        connection, process = self._connection, self._process
        self._connection = None
        self._process = None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        if process is not None:
            try:
                process.join(timeout=0.0)
            except Exception:
                pass

    def stop(self, timeout: float = 2.0) -> None:
        """Request shutdown, then bound cleanup; safe to call repeatedly."""
        connection, process = self._connection, self._process
        self._connection = None
        self._process = None
        if connection is not None:
            try:
                connection.send(encode_parent_message(shutdown_message()))
            except Exception:
                pass
            try:
                connection.close()
            except Exception:
                pass
        if process is None:
            return
        try:
            process.join(timeout=timeout)
        except Exception:
            pass
        try:
            alive = bool(process.is_alive())
        except Exception:
            alive = False
        if not alive:
            return
        try:
            process.terminate()
        except Exception:
            return
        try:
            process.join(timeout=timeout)
        except Exception:
            pass
