"""Developer-only real Python/native file-channel acceptance peer, no AP server."""
from __future__ import annotations
import asyncio
from pathlib import Path
import threading
from types import SimpleNamespace
import uuid

from word_factori.native_mail_adapter import NativeMailAdapter, room_token
from word_factori.native_mail_transport import NativeMailTransport
from word_factori.overlay_model import OverlayState, snapshot
from word_factori.dispatch_store import DispatchLedger

IDENTITY = 'isolated-native-mail-acceptance'
ROOM = room_token(IDENTITY)


class LiveMailPeer:
    def __init__(self, root: Path):
        self.transport = NativeMailTransport(root, uuid.uuid4().hex)
        self.adapter = NativeMailAdapter(self.transport)
        self.messages = []
        self.error = None
        self.stop = threading.Event()
        self.thread = None

    def __enter__(self):
        self.transport.start()
        self.transport._write('enabled.json', b'{"version":1,"enabled":true}')
        self.adapter.publish(snapshot(OverlayState(connection_status='connected'), DispatchLedger(IDENTITY),
            word_order_rows=[dict(name='Live order', word='TEST', status='Not completed')]),
            room=ROOM, contract='test-contract')
        context = SimpleNamespace(connected_identity=IDENTITY, _connection_generation=1,
            server=object(), command_processor=lambda ctx: self.messages.append)

        async def process():
            try:
                while not self.stop.is_set():
                    await self.adapter.process_once(context)
                    await asyncio.sleep(.02)
            except Exception as error:
                self.error = error
        self.thread = threading.Thread(target=lambda: asyncio.run(process()), daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=5)
        self.adapter.close()
        if self.thread.is_alive():
            raise RuntimeError('Native Mail acceptance peer did not stop')

    def verify(self):
        if self.error is not None:
            raise RuntimeError('Native Mail acceptance peer failed') from self.error
        if self.messages != ['native-roundtrip']:
            raise ValueError('Native chat was missing, duplicated, or changed')
