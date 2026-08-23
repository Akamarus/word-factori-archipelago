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

    def test_start_rejects_config_subclass_that_overrides_primitive_conversion(self):
        class CredentialConfig(OverlayConfig):
            def as_primitives(self):
                return {"enabled": True, "password": "secret", "server": "example.invalid"}

        context = FakeProcessContext()
        supervisor = self.make_supervisor(context)
        self.assertFalse(supervisor.start(CredentialConfig()))
        self.assertEqual(context.starts, 0)

    def test_config_normalizes_scalar_subclasses_and_rejects_mutated_frozen_instance(self):
        class FloatValue(float):
            pass

        class IntValue(int):
            pass

        class TextValue(str):
            pass

        context = FakeProcessContext()
        supervisor = self.make_supervisor(context)
        config = make_config(
            interface_scale=FloatValue(1.25),
            left_offset=IntValue(8),
            notification_duration=FloatValue(7.0),
            max_visible=IntValue(4),
            font_path=TextValue("C:/Game/FredokaOne.ttf"),
        )
        self.assertTrue(supervisor.start(config))
        child_config = context.processes[0].args[1]
        self.assertEqual(set(child_config), {
            "enabled", "interface_scale", "left_offset", "notification_duration",
            "reduced_motion", "max_visible", "font_path",
        })
        for key, expected_type in (
            ("enabled", bool),
            ("interface_scale", float),
            ("left_offset", int),
            ("notification_duration", float),
            ("reduced_motion", bool),
            ("max_visible", int),
            ("font_path", str),
        ):
            self.assertIs(type(child_config[key]), expected_type)

        second_context = FakeProcessContext()
        second = self.make_supervisor(second_context)
        corrupted = make_config()
        object.__setattr__(corrupted, "max_visible", True)
        self.assertFalse(second.start(corrupted))
        self.assertEqual(second_context.starts, 0)

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

    def test_publish_uses_stable_mailbox_when_stop_interleaves_with_encoding(self):
        context = FakeProcessContext()
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
        encoding_started = threading.Event()
        allow_encoding = threading.Event()
        real_encode = __import__(
            "word_factori.overlay_supervisor", fromlist=["encode_parent_message"],
        ).encode_parent_message
        result = []
        errors = []

        def controlled_encode(message):
            if message.kind == "snapshot":
                encoding_started.set()
                allow_encoding.wait()
            return real_encode(message)

        def publish_snapshot():
            try:
                result.append(supervisor.publish(snapshot(OverlayState.closed())))
            except Exception as error:
                errors.append(error)

        with mock.patch("word_factori.overlay_supervisor.encode_parent_message", side_effect=controlled_encode):
            publisher = threading.Thread(target=publish_snapshot, daemon=True)
            publisher.start()
            self.assertTrue(encoding_started.wait(1.0))
            supervisor.stop(timeout=0.01)
            allow_encoding.set()
            publisher.join(1.0)

        self.assertEqual(errors, [])
        self.assertEqual(result, [False])

    def test_publish_returns_while_stop_is_blocked_in_process_cleanup(self):
        cleanup_started = threading.Event()
        allow_cleanup = threading.Event()

        class BlockingCleanupProcess(FakeProcess):
            def join(self, timeout=None):
                if threading.current_thread().name == "blocking-stop" and not cleanup_started.is_set():
                    cleanup_started.set()
                    allow_cleanup.wait()
                super().join(timeout)

        class BlockingCleanupContext(FakeProcessContext):
            def Process(self, *, target, args):
                process = BlockingCleanupProcess(self, target, args, alive=True)
                self.processes.append(process)
                return process

        context = BlockingCleanupContext()
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
        stopper = threading.Thread(
            target=lambda: supervisor.stop(timeout=0.01), name="blocking-stop", daemon=True,
        )
        stopper.start()
        self.assertTrue(cleanup_started.wait(1.0))
        publish_result = []
        publish_done = threading.Event()

        def publish_during_cleanup():
            publish_result.append(supervisor.publish(snapshot(OverlayState.closed())))
            publish_done.set()

        publisher = threading.Thread(target=publish_during_cleanup, daemon=True)
        publisher.start()
        try:
            self.assertTrue(publish_done.wait(1.0), "publish waited for renderer stop cleanup")
            self.assertEqual(publish_result, [False])
        finally:
            allow_cleanup.set()
            publisher.join(1.0)
            stopper.join(1.0)

    def test_publish_returns_during_health_cleanup_then_later_stop_removes_restart(self):
        cleanup_started = threading.Event()
        allow_cleanup = threading.Event()

        class BlockingHealthProcess(FakeProcess):
            def join(self, timeout=None):
                if threading.current_thread().name == "blocking-health" and not cleanup_started.is_set():
                    cleanup_started.set()
                    allow_cleanup.wait()
                super().join(timeout)

        class BlockingHealthContext(FakeProcessContext):
            def Process(self, *, target, args):
                process = BlockingHealthProcess(self, target, args, alive=False)
                self.processes.append(process)
                return process

        context = BlockingHealthContext(process_alive=False)
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
        health = threading.Thread(target=supervisor.health_check, name="blocking-health", daemon=True)
        health.start()
        self.assertTrue(cleanup_started.wait(1.0))
        publish_result = []
        publish_done = threading.Event()
        publisher = threading.Thread(
            target=lambda: (publish_result.append(supervisor.publish(snapshot(OverlayState.closed()))),
                            publish_done.set()),
            daemon=True,
        )
        publisher.start()
        stop_done = threading.Event()
        stopper = threading.Thread(
            target=lambda: (supervisor.stop(timeout=0.01), stop_done.set()), daemon=True,
        )
        stopper.start()
        try:
            self.assertTrue(publish_done.wait(1.0), "publish waited for renderer health cleanup")
            self.assertEqual(publish_result, [False])
        finally:
            allow_cleanup.set()
            publisher.join(1.0)
            health.join(1.0)
            stopper.join(1.0)

        self.assertTrue(stop_done.is_set())
        self.assertEqual(context.starts, 2)
        self.assertFalse(supervisor.publish(snapshot(OverlayState.closed())))

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

    def test_explicit_restart_resets_session_disable_and_restart_budget(self):
        context = FakeProcessContext(process_alive=False)
        supervisor = self.make_supervisor(context)
        config = make_config(interface_scale=1.25)
        self.assertTrue(supervisor.start(config))
        supervisor.health_check()
        supervisor.health_check()
        self.assertTrue(supervisor.disabled)

        self.assertTrue(supervisor.restart(config))

        self.assertFalse(supervisor.disabled)
        self.assertEqual(3, context.starts)
        supervisor.health_check()
        self.assertEqual(4, context.starts)
        self.assertFalse(supervisor.disabled)

    def test_start_on_dead_child_restarts_with_new_config(self):
        context = FakeProcessContext(process_alive=False)
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config(interface_scale=1.0))
        self.assertTrue(supervisor.start(make_config(interface_scale=1.5)))
        self.assertEqual(context.starts, 2)
        self.assertEqual(context.processes[1].args[1]["interface_scale"], 1.5)

    def test_concurrent_stop_wins_over_delayed_health_restart(self):
        stop_mid_cleanup = threading.Event()
        allow_stop_cleanup = threading.Event()

        class DelayedStopProcess(FakeProcess):
            def join(self, timeout=None):
                if threading.current_thread().name == "delayed-stop" and not stop_mid_cleanup.is_set():
                    stop_mid_cleanup.set()
                    allow_stop_cleanup.wait()
                super().join(timeout)

        class DelayedStopContext(FakeProcessContext):
            def Process(self, *, target, args):
                process = DelayedStopProcess(self, target, args, alive=True)
                self.processes.append(process)
                return process

        context = DelayedStopContext(process_alive=True)
        supervisor = self.make_supervisor(context)
        supervisor.start(make_config())
        stopped = threading.Event()

        def stop_overlay():
            supervisor.stop(timeout=0.01)
            stopped.set()

        stopper = threading.Thread(target=stop_overlay, name="delayed-stop", daemon=True)
        stopper.start()
        self.assertTrue(stop_mid_cleanup.wait(1.0))
        health = threading.Thread(target=supervisor.health_check, name="concurrent-health", daemon=True)
        health.start()
        allow_stop_cleanup.set()
        health.join(1.0)
        stopper.join(1.0)
        self.assertTrue(stopped.is_set())
        self.assertEqual(context.starts, 1)
        self.assertFalse(supervisor.publish(snapshot(OverlayState.closed())))

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

    def test_stop_performs_final_bounded_writer_join_after_process_termination(self):
        order = []

        class OrderedConnection(FakeConnection):
            def close(self):
                order.append("connection-close")
                super().close()

        class OrderedProcess(FakeProcess):
            def join(self, timeout=None):
                order.append(("process-join", timeout))
                super().join(timeout)

            def terminate(self):
                order.append("process-terminate")
                super().terminate()

        class OrderedContext(FakeProcessContext):
            def Process(self, *, target, args):
                process = OrderedProcess(self, target, args, alive=True)
                self.processes.append(process)
                return process

        class OrderedWriter:
            def __init__(self, **kwargs):
                self.daemon = kwargs["daemon"]
                self.join_calls = 0

            def start(self):
                pass

            def join(self, timeout=None):
                self.join_calls += 1
                order.append(("writer-join", timeout))

            def is_alive(self):
                return True

        context = OrderedContext(parent_connection_factory=OrderedConnection)
        with mock.patch("word_factori.overlay_supervisor.threading.Thread", OrderedWriter):
            supervisor = self.make_supervisor(context)
            supervisor.start(make_config())
            supervisor.stop(timeout=0.25)

        self.assertEqual(order, [
            ("writer-join", 0.25),
            "connection-close",
            ("writer-join", 0.25),
            ("process-join", 0.25),
            "process-terminate",
            ("process-join", 0.25),
            ("writer-join", 0.25),
        ])

    def test_stop_contains_writer_liveness_probe_failure(self):
        class UnprobeableWriter:
            def __init__(self, **kwargs):
                self.daemon = kwargs["daemon"]

            def start(self):
                pass

            def join(self, timeout=None):
                pass

            def is_alive(self):
                raise OSError("cannot inspect writer")

        context = FakeProcessContext(process_alive=False)
        with mock.patch("word_factori.overlay_supervisor.threading.Thread", UnprobeableWriter):
            supervisor = self.make_supervisor(context)
            supervisor.start(make_config())
            supervisor.stop(timeout=0.01)


if __name__ == "__main__":
    unittest.main()
