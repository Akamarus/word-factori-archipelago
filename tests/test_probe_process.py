"""Probe children must not interrupt the desktop with Windows fault dialogs."""
import ctypes
import os
import subprocess
import sys
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows process error mode')
class ProbeProcessTests(unittest.TestCase):
    def test_child_inherits_quiet_errors_and_parent_mode_is_restored(self):
        from tools import run_mail_native_probe as probe
        launch = getattr(probe, 'launch_probe_process', None)
        self.assertIsNotNone(launch, 'probe needs a quiet child launcher')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        before = kernel.GetErrorMode()
        process = launch([sys.executable, '-c',
                          'import ctypes; print(ctypes.windll.kernel32.GetErrorMode())'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, error = process.communicate(timeout=10)
        self.assertEqual(0, process.returncode, error)
        self.assertEqual(0x8003, int(output) & 0x8003)
        self.assertEqual(before, kernel.GetErrorMode())

    def test_failed_spawn_restores_parent_error_mode(self):
        from tools import run_mail_native_probe as probe
        launch = getattr(probe, 'launch_probe_process', None)
        self.assertIsNotNone(launch, 'probe needs a quiet child launcher')
        before = ctypes.windll.kernel32.GetErrorMode()
        with self.assertRaises(OSError):
            launch(['Z:/nonexistent-wf-probe-executable.exe'])
        self.assertEqual(before, ctypes.windll.kernel32.GetErrorMode())
