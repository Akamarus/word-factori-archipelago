import json
import multiprocessing
import threading
import unittest
from unittest import mock

from word_factori.overlay_model import OverlayAction, OverlayState, apply_action, snapshot
from word_factori.overlay_protocol import decode_parent_message
from word_factori.overlay_supervisor import OverlayConfig, OverlaySupervisor


def renderer_entry(connection, config):
    """Top-level spawnable renderer stand-in; fake processes never execute it."""


def make_config(**changes):
    values = {
        "enabled": True,
        "interface_scale": 1.0,
        "left_offset": 0,
        "notification_duration": 6.0,
        "reduced_motion": False,
        "max_visible": 3,
        "font_path": None,
    }
    values.update(changes)
    return OverlayConfig(**values)


class FakeConnection:
    def __init__(self, *, send_error=None, recv_error=None, close_error=None, send_gate=None, on_send=None):
        self.sent = []
        self.incoming = []
        self.send_error = send_error
        self.recv_error = recv_error
        self.close_error = close_error
        self.send_gate = send_gate
        self.on_send = on_send
        self.send_started = threading.Event()
        self.closed = False

    def send(self, value):
        self.send_started.set()
        if self.send_gate is not None:
            self.send_gate.wait()
        if self.send_error is not None:
            raise self.send_error
        self.sent.append(value)
        if self.on_send is not None:
            self.on_send(value)

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
        if self.close_error is not None:
            raise self.close_error


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
    def __init__(self, *, process_alive=True, parent_connection_factory=None, child_connection_factory=None):
        self.process_alive = process_alive
        self.parent_connection_factory = parent_connection_factory or FakeConnection
        self.child_connection_factory = child_connection_factory or FakeConnection
        self.starts = 0
        self.pipe_calls = []
        self.processes = []
        self.parent_connections = []
        self.child_connections = []

    def Pipe(self, duplex=True):
        self.pipe_calls.append(duplex)
        parent = self.parent_connection_factory()
        child = self.child_connection_factory()
        self.parent_connections.append(parent)
        self.child_connections.append(child)
        return parent, child

    def Process(self, *, target, args):
        process = FakeProcess(self, target, args, alive=self.process_alive)
        self.processes.append(process)
        return process


class OverlaySupervisorTests(unittest.TestCase):
    def make_supervisor(self, context=None):
        supervisor = OverlaySupervisor(process_context=context or FakeProcessContext(), target=renderer_entry)
        self.addCleanup(supervisor.stop, 0.01)
        return supervisor

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
            self.assertTrue(supervisor.start(make_config(interface_scale=1.25)))
            self.assertTrue(supervisor.start(make_config(interface_scale=1.25)))

        self.assertEqual(order, ["freeze", "process"])
        self.assertEqual(context.pipe_calls, [True])
        self.assertEqual(context.starts, 1)
        self.assertIs(context.processes[0].target, renderer_entry)
        self.assertEqual(context.processes[0].args[1], {
            "enabled": True,
            "interface_scale": 1.25,
            "left_offset": 0,
            "notification_duration": 6.0,
            "reduced_motion": False,
            "max_visible": 3,
            "font_path": None,
        })
        self.assertIsInstance(context.processes[0].args[1], dict)
        self.assertTrue(context.child_connections[0].closed)

    def test_start_requires_exact_visual_config_without_spawning(self):
        context = FakeProcessContext()
        supervisor = self.make_supervisor(context)
        self.assertFalse(supervisor.start({"enabled": True}))
        self.assertEqual(context.starts, 0)
        for values in (
            {"interface_scale": float("nan")},
            {"left_offset": 2001},
            {"notification_duration": "6"},
            {"max_visible": True},
            {"font_path": object()},
        ):
            with self.assertRaises((TypeError, ValueError)):
                make_config(**values)

        with self.assertRaises(TypeError):
            OverlayConfig(password="secret")

    def test_constructor_rejects_nonimportable_target(self):
        with self.assertRaisesRegex(ValueError, "top-level"):
            OverlaySupervisor(process_context=FakeProcessContext(), target=lambda *_: None)

    def test_publish_sends_only_encoded_snapshot(self):
        context = FakeProcessContext()
        supervisor = self.make_supervisor(context)
        self.assertTrue(supervisor.start(make_config()))
        self.assertTrue(supervisor.publish(snapshot(OverlayState.closed())))
        connection = context.parent_connections[0]
        self.assertTrue(connection.send_started.wait(1.0))
        sent = connection.sent
        self.assertEqual(len(sent), 1)
        self.assertIsInstance(sent[0], str)
        self.assertEqual(decode_parent_message(sent[0]).kind, "snapshot")

    def test_writer_failure_is_cosmetic_and_restarts_once(self):
        context = FakeProcessContext(
            parent_connection_factory=lambda: FakeConnection(send_error=BrokenPipeError("gone")),
        )
        supervisor = self.make_supervisor(context)
        self.assertTrue(supervisor.start(make_config()))
        self.assertTrue(supervisor.publish(snapshot(OverlayState.closed())))
        self.assertTrue(context.parent_connections[0].send_started.wait(1.0))
        supervisor.health_check()
        self.assertEqual(context.starts, 2)

        self.assertTrue(supervisor.publish(snapshot(OverlayState.closed())))
        self.assertTrue(context.parent_connections[1].send_started.wait(1.0))
        supervisor.health_check()
        self.assertTrue(supervisor.disabled)

    def test_publish_coalesces_latest_snapshot_without_waiting_for_hung_writer(self):
        release_writer = threading.Event()
        latest_sent = threading.Event()

        def connection_factory():
            def on_send(encoded):
                message = decode_parent_message(encoded)
                if message.payload.get("connection_status") == "error":
                    latest_sent.set()

            return FakeConnection(send_gate=release_writer, on_send=on_send)

        context = FakeProcessContext(
            parent_connection_factory=connection_factory,
        )
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
        connection = context.parent_connections[0]
        first = snapshot(OverlayState.closed())
        second = snapshot(apply_action(OverlayState.closed(), OverlayAction("connection-status", "connected")))
        latest = snapshot(apply_action(OverlayState.closed(), OverlayAction("connection-status", "error")))

        self.assertTrue(supervisor.publish(first))
        self.assertTrue(connection.send_started.wait(1.0))
        completed = threading.Event()

        def publish_while_writer_is_hung():
            supervisor.publish(second)
            supervisor.publish(latest)
            completed.set()

        caller = threading.Thread(target=publish_while_writer_is_hung, daemon=True)
        caller.start()
        self.assertTrue(completed.wait(1.0), "publish blocked behind the renderer pipe")
        release_writer.set()
        caller.join(1.0)
        self.assertTrue(latest_sent.wait(1.0))
        statuses = [decode_parent_message(value).payload["connection_status"] for value in connection.sent]
        self.assertEqual(statuses, ["disconnected", "error"])

    def test_poll_actions_drains_valid_messages_and_ignores_malformed_message(self):
        context = FakeProcessContext()
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
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
        supervisor.start(make_config())
        self.assertEqual(supervisor.poll_actions(), ())

    def test_poll_actions_reads_at_most_sixty_four_messages(self):
        encoded = json.dumps({
            "version": 1, "type": "action", "payload": {"kind": "open", "value": None},
        })

        class AlwaysReadyConnection(FakeConnection):
            def poll(self, timeout=0.0):
                return True

            def recv(self):
                return encoded

        context = FakeProcessContext(parent_connection_factory=AlwaysReadyConnection)
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
        self.assertEqual(len(supervisor.poll_actions()), 64)
        self.assertEqual(len(supervisor.poll_actions()), 64)

    def test_health_check_restarts_once_then_disables(self):
        context = FakeProcessContext(process_alive=False)
        supervisor = self.make_supervisor(context)
        self.assertTrue(supervisor.start(make_config()))

        supervisor.health_check()
        self.assertEqual(context.starts, 2)
        self.assertFalse(supervisor.disabled)

        supervisor.health_check()
        self.assertEqual(context.starts, 2)
        self.assertTrue(supervisor.disabled)
        self.assertFalse(supervisor.publish(snapshot(OverlayState.closed())))

    def test_start_on_dead_child_restarts_with_new_config(self):
        context = FakeProcessContext(process_alive=False)
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config(interface_scale=1.0))
        self.assertTrue(supervisor.start(make_config(interface_scale=1.5)))
        self.assertEqual(context.starts, 2)
        self.assertEqual(context.processes[1].args[1]["interface_scale"], 1.5)

    def test_launch_failure_after_process_start_terminates_owned_child(self):
        context = FakeProcessContext(
            process_alive=True,
            child_connection_factory=lambda: FakeConnection(close_error=OSError("close failed")),
        )
        supervisor = self.make_supervisor(context)
        self.assertFalse(supervisor.start(make_config()))
        self.assertEqual(context.starts, 1)
        self.assertEqual(context.processes[0].terminate_calls, 1)
        self.assertFalse(context.processes[0].is_alive())
        self.assertTrue(context.parent_connections[0].closed)

    def test_stop_requests_shutdown_then_terminates_only_if_needed_and_is_idempotent(self):
        context = FakeProcessContext(process_alive=True)
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
        process = context.processes[0]
        connection = context.parent_connections[0]

        supervisor.stop(timeout=0.25)
        supervisor.stop(timeout=0.25)

        self.assertEqual(decode_parent_message(connection.sent[0]).kind, "shutdown")
        self.assertTrue(connection.closed)
        self.assertEqual(process.join_timeouts, [0.25, 0.25])
        self.assertEqual(process.terminate_calls, 1)

    def test_graceful_stop_does_not_terminate_child_that_exits_on_shutdown(self):
        context = FakeProcessContext(process_alive=True)

        def connection_factory():
            def on_send(encoded):
                if decode_parent_message(encoded).kind == "shutdown":
                    context.processes[0].alive = False

            return FakeConnection(on_send=on_send)

        context.parent_connection_factory = connection_factory
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
        process = context.processes[0]
        supervisor.stop(timeout=0.25)
        self.assertEqual(process.terminate_calls, 0)

    def test_stop_terminates_owned_child_when_liveness_probe_fails(self):
        class UnprobeableProcess(FakeProcess):
            def is_alive(self):
                raise OSError("cannot inspect child")

        class UnprobeableContext(FakeProcessContext):
            def Process(self, *, target, args):
                process = UnprobeableProcess(self, target, args, alive=True)
                self.processes.append(process)
                return process

        context = UnprobeableContext()
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
        supervisor.stop(timeout=0.25)
        self.assertEqual(context.processes[0].terminate_calls, 1)


if __name__ == "__main__":
    unittest.main()
