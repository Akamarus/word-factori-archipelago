"""Safety boundaries for the developer-only full-game Mail acceptance copy."""
import unittest


class FullMailIsolationTests(unittest.TestCase):
    def test_external_calls_and_function_references_are_neutralized(self):
        from tools import mail_hooks
        isolate = getattr(mail_hooks, 'isolate_probe_external_calls', None)
        self.assertIsNotNone(isolate, 'full-game external-call isolation is missing')
        source = 'http_get(url); var fn=steam_file_delete; url_open(url); native_move();'
        changed = isolate(source)
        self.assertEqual('wf_probe_external_blocked(url); var fn=wf_probe_external_blocked; wf_probe_external_blocked(url); native_move();', changed)

    def test_isolation_preserves_literals_comments_and_local_identifiers(self):
        from tools import mail_hooks
        isolate = getattr(mail_hooks, 'isolate_probe_external_calls', None)
        self.assertIsNotNone(isolate, 'full-game external-call isolation is missing')
        source = '// http_get(url)\nvar label="steam_file_delete"; my_http_get();'
        self.assertEqual(source, isolate(source))

    def test_isolation_refuses_interpolated_external_calls(self):
        from tools import mail_hooks
        isolate = getattr(mail_hooks, 'isolate_probe_external_calls', None)
        self.assertIsNotNone(isolate, 'full-game external-call isolation is missing')
        with self.assertRaises(ValueError):
            isolate('var message=$"remote: {http_get(url)}";')


if __name__ == '__main__':
    unittest.main()
