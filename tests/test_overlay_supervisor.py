import json
import multiprocessing
import unittest
from unittest import mock

from word_factori.overlay_model import OverlayAction, OverlayState, snapshot
from word_factori.overlay_protocol import decode_parent_message
from word_factori.overlay_supervisor import OverlaySupervisor


def renderer_entry(connection, config):
    """Top-level spawnable renderer stand-in; fake processes never execute it."""


class FakeConnection:
    def __init__(self, *, send_error=None, recv_error=None):
        self.sent = []
        self.incoming = []
        self.send_error = send_error
        self.recv_error = recv_error
        self.closed = False

    def send(self, value):
        if self.send_error is not None:
            raise self.send_error
        self.sent.append(value)

    def poll(self, timeout=0.0):
        if self.recv_error is not None:
            raise self.recv_error
        return bool(self.incoming)

    def recv(self):
        if self.recv_error is not None:
            raise self.recv_error
        return self.incoming.pop(0)

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, context, target, args, *, alive):
        self.context = context
        self.target = target
        self.args = args
        self.alive = alive
        self.started = False
        self.join_timeouts = []
        self.terminate_calls = 0

    def start(self):
        self.started = True
        self.context.starts += 1

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_timeouts.append(timeout)

    def terminate(self):
        self.terminate_calls += 1
        self.alive = False


class FakeProcessContext:
    def __init__(self, *, process_alive=True, parent_connection_factory=None):
        self.process_alive = process_alive
        self.parent_connection_factory = parent_connection_factory or FakeConnection
        self.starts = 0
        self.pipe_calls = []
        self.processes = []
        self.parent_connections = []
        self.child_connections = []

    def Pipe(self, duplex=True):
        self.pipe_calls.append(duplex)
        parent = self.parent_connection_factory()
        child = FakeConnection()
        self.parent_connections.append(parent)
        self.child_connections.append(child)
        return parent, child

    def Process(self, *, target, args):
        process = FakeProcess(self, target, args, alive=self.process_alive)
        self.processes.append(process)
        return process


class OverlaySupervisorTests(unittest.TestCase):
    def make_supervisor(self, context=None):
        return OverlaySupervisor(process_context=context or FakeProcessContext(), target=renderer_entry)

    def test_default_uses_spawn_context(self):
        expected = FakeProcessContext()
        with mock.patch.object(multiprocessing, "get_context", return_value=expected) as get_context:
            supervisor = OverlaySupervisor(target=renderer_entry)
        self.assertIs(supervisor.process_context, expected)
        get_context.assert_called_once_with("spawn")

    def test_start_freezes_before_creating_one_duplex_child(self):
        order = []

        class OrderedContext(FakeProcessContext):
            def Process(self, *, target, args):
                order.append("process")
                return super().Process(target=target, args=args)

        context = OrderedContext()
        supervisor = self.make_supervisor(context)
        with mock.patch.object(multiprocessing, "freeze_support", side_effect=lambda: order.append("freeze")):
            self.assertTrue(supervisor.start({"font_path": None, "scale": 1.0}))
            self.assertTrue(supervisor.start({"font_path": None, "scale": 1.0}))

        self.assertEqual(order, ["freeze", "process"])
        self.assertEqual(context.pipe_calls, [True])
        self.assertEqual(context.starts, 1)
        self.assertIs(context.processes[0].target, renderer_entry)
        self.assertEqual(context.processes[0].args[1], {"font_path": None, "scale": 1.0})
        self.assertTrue(context.child_connections[0].closed)

    def test_start_rejects_nonprimitive_config_without_spawning(self):
        context = FakeProcessContext()
        supervisor = self.make_supervisor(context)
        self.assertFalse(supervisor.start({"client_context": object()}))
        self.assertEqual(context.starts, 0)

    def test_constructor_rejects_nonimportable_target(self):
        with self.assertRaisesRegex(ValueError, "top-level"):
            OverlaySupervisor(process_context=FakeProcessContext(), target=lambda *_: None)

    def test_publish_sends_only_encoded_snapshot(self):
        context = FakeProcessContext()
        supervisor = self.make_supervisor(context)
        self.assertTrue(supervisor.start({"enabled": True}))
        self.assertTrue(supervisor.publish(snapshot(OverlayState.closed())))

        sent = context.parent_connections[0].sent
        self.assertEqual(len(sent), 1)
        self.assertIsInstance(sent[0], str)
        self.assertEqual(decode_parent_message(sent[0]).kind, "snapshot")

    def test_publish_failure_is_cosmetic(self):
        context = FakeProcessContext(
            parent_connection_factory=lambda: FakeConnection(send_error=BrokenPipeError("gone")),
        )
        supervisor = self.make_supervisor(context)
        self.assertTrue(supervisor.start({}))
        self.assertFalse(supervisor.publish(snapshot(OverlayState.closed())))

    def test_poll_actions_drains_valid_messages_and_ignores_malformed_message(self):
        context = FakeProcessContext()
        supervisor = self.make_supervisor(context)
        supervisor.start({})
        connection = context.parent_connections[0]
        connection.incoming.extend((
            json.dumps({"version": 1, "type": "action", "payload": {"kind": "open", "value": None}}),
            "not-json",
            json.dumps({"version": 1, "type": "action", "payload": {"kind": "filter", "value": "sent"}}),
        ))

        self.assertEqual(supervisor.poll_actions(), (OverlayAction("open"), OverlayAction("filter", "sent")))
        self.assertEqual(supervisor.poll_actions(), ())

    def test_poll_eof_is_cosmetic(self):
        context = FakeProcessContext(
            parent_connection_factory=lambda: FakeConnection(recv_error=EOFError("gone")),
        )
        supervisor = self.make_supervisor(context)
        supervisor.start({})
        self.assertEqual(supervisor.poll_actions(), ())

    def test_health_check_restarts_once_then_disables(self):
        context = FakeProcessContext(process_alive=False)
        supervisor = self.make_supervisor(context)
        self.assertTrue(supervisor.start({"enabled": True}))

        supervisor.health_check()
        self.assertEqual(context.starts, 2)
        self.assertFalse(supervisor.disabled)

        supervisor.health_check()
        self.assertEqual(context.starts, 2)
        self.assertTrue(supervisor.disabled)
        self.assertFalse(supervisor.publish(snapshot(OverlayState.closed())))

    def test_stop_requests_shutdown_then_terminates_only_if_needed_and_is_idempotent(self):
        context = FakeProcessContext(process_alive=True)
        supervisor = self.make_supervisor(context)
        supervisor.start({})
        process = context.processes[0]
        connection = context.parent_connections[0]

        supervisor.stop(timeout=0.25)
        supervisor.stop(timeout=0.25)

        self.assertEqual(decode_parent_message(connection.sent[0]).kind, "shutdown")
        self.assertTrue(connection.closed)
        self.assertEqual(process.join_timeouts, [0.25, 0.25])
        self.assertEqual(process.terminate_calls, 1)


if __name__ == "__main__":
    unittest.main()
