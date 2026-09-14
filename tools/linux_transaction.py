"""Recoverable file replacements; journals and historical copies stay outside mods.

Each destination is staged on its own filesystem. This is deliberately not a
claim of atomicity across the game, Proton prefix and native AP installation.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from pathlib import Path


def safe_path(path: Path, *, journal_link=False) -> None:
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Transaction paths must be absolute and contain no parent traversal')
    for entry in (path, *path.parents):
        if entry.is_symlink() or getattr(entry, 'is_junction', lambda: False)():
            raise ValueError(f'Refusing aliased target: {entry}')
    if path.exists() and not path.is_file():
        raise ValueError(f'Expected a regular file: {path}')
    if path.exists() and path.stat().st_nlink != 1 and not journal_link:
        raise ValueError(f'Refusing hard-linked target: {path}')


def digest(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def read(path: Path, *, journal_link=False) -> bytes | None:
    safe_path(path, journal_link=journal_link)
    return path.read_bytes() if path.exists() else None


def sync_directory(path: Path) -> None:
    if os.name == 'posix':
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def durable_write(path: Path, data: bytes) -> None:
    safe_path(path)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def writable(path: Path) -> None:
    safe_path(path)
    ancestor = path.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not ancestor.is_dir() or not ancestor.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        raise PermissionError(f'Directory is not writable: {ancestor}')
    if not os.access(ancestor, os.W_OK | os.X_OK):
        raise PermissionError(f'Directory is not writable: {ancestor}')


class Transaction:
    def __init__(self, root: Path, targets: dict[str, Path], identity: dict, check_closed,
                 allowed_hashes: dict[str, set]):
        self.root, self.targets, self.identity = root, targets, identity
        self.check_closed = check_closed
        self.allowed_hashes = allowed_hashes
        self.journal = root / 'active.json'
        safe_path(self.journal, journal_link=True)

    def pending(self) -> bool:
        safe_path(self.journal, journal_link=True)
        return self.journal.exists()

    def _stage(self, target, token, index):
        return target.parent / f'.wf-ap-{token}-{index}.tmp'

    def apply(self, changes: dict[str, bytes | None], expected: dict[str, str | None]):
        if self.pending():
            raise ValueError('Interrupted installation detected; run recover first')
        self.check_closed()
        for key in changes:
            writable(self.targets[key])
        writable(self.journal)
        token = uuid.uuid4().hex
        history = self.root / token
        history.mkdir(parents=True, exist_ok=False)
        entries = []
        owns_journal = False
        # Finish every backup and stage before publishing the journal.
        try:
            for index, (key, after) in enumerate(changes.items()):
                target = self.targets[key]
                before = read(target)
                if digest(before) != expected[key]:
                    raise ValueError(f'Target changed during preparation: {target}')
                target.parent.mkdir(parents=True, exist_ok=True)
                if before is not None:
                    durable_write(history / str(index), before)
                if after is not None:
                    durable_write(self._stage(target, token, index), after)
                entries.append({'key': key, 'before': digest(before), 'after': digest(after)})
            document = {'schema': 1, 'identity': self.identity, 'token': token, 'entries': entries}
            # Link a completely written journal into place with exclusive creation.
            # Unlike replace(), link() cannot overwrite a competing transaction;
            # unlike writing active.json directly, interruption cannot truncate it.
            complete_journal = history / 'journal.json'
            durable_write(complete_journal, json.dumps(document, sort_keys=True).encode())
            os.link(complete_journal, self.journal)
            owns_journal = True
            sync_directory(self.root)
            for index, entry in enumerate(entries):
                self.check_closed()
                # Every still-unmodified target must retain its preflight identity.
                for pending_index, pending in enumerate(entries[index:], index):
                    if digest(read(self.targets[pending['key']])) != pending['before']:
                        raise ValueError('Target changed during transaction')
                    stage = self._stage(self.targets[pending['key']], token, pending_index)
                    if pending['after'] is not None and digest(read(stage)) != pending['after']:
                        raise ValueError('Staged replacement changed during transaction')
                target = self.targets[entry['key']]
                if entry['after'] is None:
                    target.unlink(missing_ok=True)
                else:
                    os.replace(self._stage(target, token, index), target)
                sync_directory(target.parent)
            self.journal.unlink()
            sync_directory(self.root)
        except Exception:
            if owns_journal and self.pending():
                self.recover()
            raise
        finally:
            # An interruption retains both journal and remaining stages.
            if not self.pending():
                for index, key in enumerate(changes):
                    stage = self._stage(self.targets[key], token, index)
                    safe_path(stage)
                    stage.unlink(missing_ok=True)

    def recover(self):
        self.check_closed()
        raw = read(self.journal, journal_link=True)
        if raw is None:
            return
        if len(raw) > 65536:
            raise ValueError('Transaction journal is too large')
        document = json.loads(raw)
        if (not isinstance(document, dict) or set(document) != {'schema', 'identity', 'token', 'entries'}
                or document['schema'] != 1 or document['identity'] != self.identity
                or not isinstance(document['token'], str)
                or not re.fullmatch('[0-9a-f]{32}', document['token'])):
            raise ValueError('Transaction journal does not match selected installation')
        entries = document['entries']
        if not isinstance(entries, list) or not 1 <= len(entries) <= len(self.targets):
            raise ValueError('Invalid transaction entries')
        checked, keys = [], set()
        for index, entry in enumerate(entries):
            if (not isinstance(entry, dict) or set(entry) != {'key', 'before', 'after'}
                    or not isinstance(entry['key'], str) or entry['key'] not in self.targets
                    or entry['key'] in keys):
                raise ValueError('Unsafe transaction target')
            keys.add(entry['key'])
            for value in (entry['before'], entry['after']):
                if value is not None and (not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)):
                    raise ValueError('Invalid transaction digest')
                if entry['key'] in self.allowed_hashes and value not in self.allowed_hashes[entry['key']]:
                    raise ValueError('Transaction game/backup digest is not a pinned build')
            target = self.targets[entry['key']]
            current = digest(read(target))
            if current not in (entry['before'], entry['after']):
                raise ValueError('Recovery target changed; refusing to overwrite it')
            backup = self.root / document['token'] / str(index)
            before = read(backup)
            if digest(before) != entry['before']:
                raise ValueError('Transaction backup failed verification')
            stage = self._stage(target, document['token'], index)
            staged = read(stage)
            if staged is not None and digest(staged) not in (entry['before'], entry['after']):
                raise ValueError('Transaction staging file changed')
            checked.append((entry, target, before, stage))
        # Validate the entire journal before a single recovery mutation.
        for entry, target, before, stage in reversed(checked):
            self.check_closed()
            current = digest(read(target))
            if current not in (entry['before'], entry['after']):
                raise ValueError('Recovery target changed during recovery')
            if current != entry['before']:
                if before is None:
                    target.unlink(missing_ok=True)
                else:
                    stage.unlink(missing_ok=True)
                    durable_write(stage, before)
                    os.replace(stage, target)
                sync_directory(target.parent)
            safe_path(stage)
            stage.unlink(missing_ok=True)
        self.journal.unlink()
        sync_directory(self.root)
