"""Single-owner, bounded local Mail channel. Never reads or writes game saves."""
from __future__ import annotations

from collections import deque
import copy
import os
from pathlib import Path
import stat
import tempfile
import threading
import time

from . import native_mail_protocol as protocol


def _safe(path):
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Mail path must be absolute without traversal')
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise ValueError('Mail path is redirected')
    if path.exists():
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
            raise ValueError('Mail target is not an ordinary owned file')


class NativeMailTransport:
    def __init__(self, root: Path, session: str, *, clock=time.monotonic):
        protocol.encode_envelope(dict(version=1, session=session, renderer='0'*32,
                                      revision=0, heartbeat=0), kind='manifest')
        self.root, self.session, self.clock = Path(root), session, clock
        self.renderer = None
        self._lock_file = None
        self._mutex = threading.RLock()
        self._next_poll = float('-inf')
        self._last_beat = float('-inf')
        self._heartbeat = 0
        self._revision = 0
        self._hello = None
        self._hello_advance = None
        self._candidate = None
        self._conflict = False
        self._invalid = False
        self._latest = None
        self._published = None
        self._pending = None
        self._highwater = -1
        self._acks = deque(maxlen=protocol.MAX_ACKS)
        self._issued_keys = deque(maxlen=512)
        self._issued_cursors = deque(maxlen=128)
        self.error = None

    @property
    def ready(self):
        return bool(self._lock_file and self.renderer and not self._conflict
                    and not self._invalid and protocol.heartbeat_fresh(self._hello_advance, self.clock()))

    def start(self):
        with self._mutex:
            if self._lock_file:
                return
            _safe(self.root)
            if self.root.name != 'archipelago_mail':
                raise ValueError('Mail requires its dedicated directory')
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.root / 'client.lock'; _safe(path)
            stream = path.open('a+b')
            try:
                if os.name == 'nt':
                    import msvcrt
                    if stream.seek(0, os.SEEK_END) == 0:
                        stream.write(b'0'); stream.flush()
                    stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except Exception:
                stream.close()
                raise
            self._lock_file = stream

    def _read(self, name, kind):
        path = self.root / name; _safe(path)
        try:
            with path.open('rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('Unsafe Mail input')
                raw = stream.read(protocol.LIMITS[kind]+1)
        except FileNotFoundError:
            return None
        return protocol.decode_envelope(raw, kind=kind)

    def _write(self, name, raw):
        destination = self.root / name; _safe(destination)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix='.mail-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            _safe(destination)
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _manifest(self):
        if self.renderer and self._published is not None:
            self._write('manifest.json', protocol.encode_envelope(dict(
                version=1, session=self.session, renderer=self.renderer,
                revision=self._revision, heartbeat=self._heartbeat), kind='manifest'))

    def publish(self, snapshot):
        protocol.encode_envelope(snapshot, kind='snapshot')
        with self._mutex:
            if not self._lock_file:
                return
            self._latest = copy.deepcopy(snapshot)
            self._flush()

    def _flush(self):
        if not self.renderer or self._latest is None or not self.ready:
            return
        value = copy.deepcopy(self._latest)
        value.update(session=self.session, renderer=self.renderer,
                     revision=self._revision, acks=list(self._acks))
        if value == self._published:
            return
        value['revision'] = self._revision + 1
        raw = protocol.encode_envelope(value, kind='snapshot')
        self._write('snapshot.json', raw)
        # The old manifest remains authoritative until its replacement succeeds.
        previous = self._revision
        self._revision = value['revision']
        try:
            self._write('manifest.json', protocol.encode_envelope(dict(
                version=1, session=self.session, renderer=self.renderer,
                revision=self._revision, heartbeat=self._heartbeat), kind='manifest'))
        except Exception:
            self._revision = previous
            raise
        if self._published and value['room'] != self._published['room']:
            self._issued_keys.clear(); self._issued_cursors.clear()
        self._published = value
        for row in value['items']:
            if row['key'] not in self._issued_keys:
                self._issued_keys.append(row['key'])
        for view, cursor in value['history'].items():
            if cursor and (view, cursor) not in self._issued_cursors:
                self._issued_cursors.append((view, cursor))

    def _observe_hello(self, hello, now):
        if hello is None:
            return
        renderer, beat = hello['renderer'], hello['heartbeat']
        if renderer == self.renderer:
            if beat < self._hello:
                raise ValueError('Mail renderer heartbeat moved backwards')
            if beat > self._hello:
                self._hello, self._hello_advance = beat, now
            return
        if self._candidate is None or self._candidate[0] != renderer:
            self._candidate = (renderer, beat)
            return
        if beat <= self._candidate[1]:
            return
        if self.renderer and protocol.heartbeat_fresh(self._hello_advance, now):
            self._conflict = True
            raise ValueError('Two active Mail renderers; restart the paired client')
        self.renderer, self._hello, self._hello_advance = renderer, beat, now
        self._candidate = None
        self._pending = None; self._highwater = -1; self._acks.clear()
        self._published = None
        self._issued_keys.clear(); self._issued_cursors.clear()

    def poll(self):
        with self._mutex:
            now = self.clock()
            if not self._lock_file or now < self._next_poll or self._conflict:
                return ()
            self._next_poll = now + protocol.POLL_SECONDS
            try:
                self._observe_hello(self._read('hello.json', 'hello'), now)
                request = self._read('request.json', 'request')
                self._invalid = False
                self.error = None
                if not self.ready:
                    return ()
                self._flush()
                if now - self._last_beat >= protocol.HEARTBEAT_SECONDS:
                    self._heartbeat += 1
                    self._manifest()
                    self._last_beat = now
                if request is None or self._published is None:
                    return ()
                if (request['session'] != self.session or request['renderer'] != self.renderer
                        or request['room'] != self._published['room']
                        or request['sequence'] <= self._highwater or self._pending is not None):
                    return ()
                self._highwater = request['sequence']
                self._pending = copy.deepcopy(request)
                payload, action = request['payload'], request['action']
                allowed = (action != 'mark-read' or payload['through_key'] in self._issued_keys)
                allowed = allowed and (action != 'history' or payload['cursor'] == 'latest'
                                       or (payload['view'], payload['cursor']) in self._issued_cursors)
                if not allowed:
                    self.acknowledge(request, 'rejected', 'This view is no longer available. Reopen Mail.')
                    return ()
                self._acks.append(dict(sequence=request['sequence'], status='queued', message=''))
                self._flush()
                return (copy.deepcopy(request),)
            except (ValueError, OSError) as error:
                self._invalid = True
                self.error = str(error)
                return ()

    def acknowledge(self, request, status, message):
        with self._mutex:
            if not self._lock_file:
                return
            if request != self._pending:
                raise ValueError('Mail acknowledgment does not match the reserved request')
            row = dict(sequence=request['sequence'], status=status, message=message)
            protocol._ack(row)
            self._acks = deque((x for x in self._acks if x['sequence'] != request['sequence']), maxlen=protocol.MAX_ACKS)
            self._acks.append(row)
            self._pending = None
            self._flush()

    def close(self):
        with self._mutex:
            if self._lock_file:
                stream, self._lock_file = self._lock_file, None
                try:
                    if os.name == 'nt':
                        import msvcrt
                        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream, fcntl.LOCK_UN)
                finally:
                    stream.close()
