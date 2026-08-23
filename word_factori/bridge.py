from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True, order=True)
class ReceivedItem:
    index: int
    name: str


@dataclass(frozen=True)
class BridgeState:
    applied: Mapping[int, str] = field(default_factory=dict)
    item_counts: Mapping[str, int] = field(default_factory=dict)
    pending_checks: frozenset[int] = frozenset()
    game_slot_id: str | None = None

    @classmethod
    def empty(cls): return cls()


@dataclass(frozen=True)
class ReconcileResult:
    state: BridgeState
    applied_indices: tuple[int, ...]
    new_checks: frozenset[int]


def reconcile(
    state: BridgeState,
    received: Iterable[ReceivedItem],
    local_checks: set[int],
    server_checks: set[int],
    *,
    authoritative: bool = False,
) -> ReconcileResult:
    applied = {} if authoritative else dict(state.applied)
    new = []
    for item in sorted(received):
        if item.index in applied:
            if applied[item.index] != item.name: raise ValueError(f"conflict at receive index {item.index}")
            continue
        applied[item.index] = item.name; new.append(item.index)
    return ReconcileResult(BridgeState(applied, dict(Counter(applied.values())), state.pending_checks, state.game_slot_id), tuple(new), frozenset(local_checks - server_checks))


def queue_checks(state: BridgeState, location_ids: Iterable[int]) -> BridgeState:
    return BridgeState(state.applied, state.item_counts, state.pending_checks | frozenset(location_ids), state.game_slot_id)


def acknowledge_checks(state: BridgeState, server_checks: Iterable[int]) -> BridgeState:
    return BridgeState(state.applied, state.item_counts, state.pending_checks - frozenset(server_checks), state.game_slot_id)


def bind_game_slot(state: BridgeState, game_slot_id: str) -> BridgeState:
    if not game_slot_id:
        raise ValueError("game slot id must be non-empty")
    return BridgeState(state.applied, state.item_counts, state.pending_checks, game_slot_id)


def load_state(path: Path) -> BridgeState:
    if not path.is_file():
        return BridgeState.empty()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("applied", {}), dict):
        raise ValueError("bridge sidecar must be an object containing an applied object")
    applied = {int(index): str(name) for index, name in payload.get("applied", {}).items()}
    pending = payload.get("pending_checks", [])
    if not isinstance(pending, list):
        raise ValueError("bridge sidecar pending_checks must be an array")
    game_slot_id = payload.get("game_slot_id")
    if game_slot_id is not None and (not isinstance(game_slot_id, str) or not game_slot_id):
        raise ValueError("bridge sidecar game_slot_id must be a non-empty string")
    return BridgeState(applied, dict(Counter(applied.values())), frozenset(int(value) for value in pending), game_slot_id)


def save_state(path: Path, state: BridgeState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({
                "version": 3,
                "applied": {str(index): name for index, name in sorted(state.applied.items())},
                "pending_checks": sorted(state.pending_checks),
                "game_slot_id": state.game_slot_id,
            }, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
