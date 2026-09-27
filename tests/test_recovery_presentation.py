import importlib
import unittest


class RecoveryPresentationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('word_factori.recovery_presentation'))
        self.api = importlib.import_module('word_factori.recovery_presentation')

    def test_missing_patch_directs_matching_installer_without_save_deletion(self):
        for platform, installer in (('linux', 'Linux installer'), ('win32', 'Install Word Factori Archipelago.cmd')):
            result = self.api.recovery_presentation('patch_missing', platform=platform)
            self.assertIn('Close the game', result.action)
            self.assertIn(installer, result.action)
            self.assertNotIn('delete', result.action.lower())
    def test_unknown_errors_cannot_echo_private_input(self):
        result = self.api.recovery_presentation('C:/Users/private/password123', platform='linux')
        self.assertEqual(result.code, 'unknown_error')
        self.assertNotIn('private', result.action)
        self.assertIn('regular client', result.action)

    def test_build_failure_does_not_promise_reinstall(self):
        result = self.api.recovery_presentation('unsupported_build', platform='linux')
        self.assertIn('supported', result.action)
        self.assertNotIn('rerun', result.action.lower())

    def test_connection_and_save_guidance_does_not_require_per_item_reload(self):
        for code in ('disconnected', 'save_unbound', 'save_mismatch', 'mod_unselected', 'native_waiting', 'journal_invalid'):
            result = self.api.recovery_presentation(code, platform='win32')
            self.assertEqual(result.code, code)
            self.assertTrue(result.title and result.action)
            self.assertNotIn('reload', result.action.lower())
            self.assertNotIn('delete', result.action.lower())
