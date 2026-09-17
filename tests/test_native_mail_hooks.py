"""Authored fixtures exercise hook safety without distributing game code."""
import tempfile
import unittest
from pathlib import Path


class MailHookTests(unittest.TestCase):
    def test_missing_hooks_are_refused(self):
        from tools.mail_hooks import transform_mail_sources
        with self.assertRaises(ValueError):
            transform_mail_sources({}, '// authored helpers')

    def test_reader_rewrite_preserves_literals_comments_and_identifiers(self):
        from tools.mail_hooks import redirect_readers
        source = ('// keyboard_check(1)\nvar label="mouse_wheel_up()";\n'
                  'if (keyboard_check(65)) native_tick();\n'
                  'var my_keyboard_check = 1; mouse_wheel_down();')
        self.assertEqual(('// keyboard_check(1)\nvar label="mouse_wheel_up()";\n'
                          'if (wf_mail_keyboard_check(65)) native_tick();\n'
                          'var my_keyboard_check = 1; wf_mail_mouse_wheel_down();'),
                         redirect_readers(source))

    def test_function_guard_refuses_duplicate_changed_and_already_patched(self):
        from tools.mail_hooks import guard_function
        for source in ('function renamed() {}',
                       'function checkPressed(a) {} function checkPressed(b) {}',
                       'function checkPressed(a) { if(wf_mail_blocks_input()) return false; }'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                guard_function(source, 'checkPressed', 'return false;')

    def test_function_guard_preserves_body_and_other_functions(self):
        from tools.mail_hooks import guard_function
        self.assertEqual(
            'function checkPressed(a) {\nif (wf_mail_blocks_input()) { return false; }\n native_action(); }\nfunction other() {}',
            guard_function('function checkPressed(a) { native_action(); }\nfunction other() {}',
                           'checkPressed', 'return false;'))

    def test_changed_or_extra_source_refused_without_mutation(self):
        from tools.mail_hooks import transform_mail_sources
        sources = {'entry': 'function changed() {}'}
        before = dict(sources)
        with self.assertRaises(ValueError):
            transform_mail_sources(sources, '// helpers')
        self.assertEqual(before, sources)

    def test_probe_unsupported_cases_and_unknown_original_never_write(self):
        from tools.run_mail_native_probe import build_probe
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / 'runtime'
            runtime.mkdir()
            cli = root / 'cli.exe'
            cli.write_bytes(b'not executable')
            original = runtime / 'original.win'
            original.write_bytes(b'unknown original')
            for case in ('bridge', 'ui', 'all', 'invalid', 'input'):
                with self.subTest(case=case), self.assertRaises(ValueError):
                    build_probe(cli, original, runtime, root / 'output', case=case)
                self.assertFalse((root / 'output').exists())

    def test_failed_or_incomplete_native_results_cannot_pass_gate(self):
        from tools.run_mail_native_probe import validate_result
        for result in ({}, {'supported': True, 'tests': []},
                       {'supported': True, 'tests': [{'name': 'click', 'passed': False}]},
                       {'supported': True, 'tests': [{'name': 'click', 'passed': True}]}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                validate_result(result)

    def test_native_result_requires_every_named_assertion_once(self):
        from tools.run_mail_native_probe import REQUIRED_ASSERTIONS, validate_result
        tests = [{'name': name, 'passed': True} for name in REQUIRED_ASSERTIONS]
        validate_result({'supported': True, 'tests': tests})
        for changed in (tests[:-1], tests + [tests[0]], tests[:-1] + [{'name': tests[-1]['name'], 'passed': 1}]):
            with self.assertRaises(ValueError):
                validate_result({'supported': True, 'tests': changed})

    def test_all_hook_inputs_are_checked_before_transformation(self):
        from tools.mail_hooks import SOURCE_HASHES, transform_mail_sources
        sources = {name: 'authored placeholder' for name in SOURCE_HASHES}
        with self.assertRaisesRegex(ValueError, 'Changed'):
            transform_mail_sources(sources, '// helpers')

    def test_interactive_result_cannot_omit_real_keyboard_evidence(self):
        from tools.run_mail_native_probe import REQUIRED_ASSERTIONS, validate_result
        automatic = [{'name': name, 'passed': True} for name in REQUIRED_ASSERTIONS]
        physical = [{'name': name, 'passed': True} for name in (
            'real raw key press exercised while Mail open',
            'real raw key release exercised while Mail open',
            'real raw key held while Mail open',
            'real raw keyboard did not reach native consumer',
        )]
        validate_result({'supported': True, 'interactive': True, 'tests': automatic + physical})
        for index in range(len(physical)):
            with self.subTest(missing=physical[index]['name']), self.assertRaises(ValueError):
                validate_result({'supported': True, 'interactive': True,
                                 'tests': automatic + physical[:index] + physical[index + 1:]})

    def test_factory_result_cannot_pass_without_production_comparison(self):
        from tools.run_mail_native_probe import REQUIRED_ASSERTIONS, validate_result
        automatic = [{'name': name, 'passed': True} for name in REQUIRED_ASSERTIONS]
        factory = [{'name': name, 'passed': True} for name in (
            'closed Mail factory completes ten words',
            'open Mail factory completes ten words',
            'Mail does not change production tick count',
            'Mail does not change completion journal',
            'Mail stays open throughout native production',
            'native production completion is idempotent with Mail open',
        )]
        validate_result({'supported': True, 'factory': True, 'tests': automatic + factory})
        for index in range(len(factory)):
            with self.subTest(missing=factory[index]['name']), self.assertRaises(ValueError):
                validate_result({'supported': True, 'factory': True,
                                 'tests': automatic + factory[:index] + factory[index + 1:]})

    def test_factory_comparison_rejects_changed_timing_or_journal(self):
        from tools import run_mail_native_probe as probe
        compare = getattr(probe, 'compare_factory_results', None)
        self.assertIsNotNone(compare, 'independent-process factory comparison is missing')
        import copy
        base = {'supported': True, 'exit_code': 0, 'tests': [
            {'name': name, 'passed': True} for name in probe.REQUIRED_ASSERTIONS]}
        closed = dict(base, factory_mode='closed', factory_closed={
            'won': True, 'words': 10, 'ticks': 21, 'frames': 21,
            'journal': '{"words":{"II":{"buildings":2}}}', 'idempotent': True,
            'kept_open': True})
        opened = dict(base, factory_mode='open', factory_open=copy.deepcopy(closed['factory_closed']))
        probe.validate_result(compare(closed, opened))
        for key, bad in (('ticks', 22), ('frames', 22), ('words', 9), ('won', False),
                         ('journal', '{"words":{}}'), ('idempotent', False), ('kept_open', False)):
            changed = copy.deepcopy(opened)
            changed['factory_open'][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                probe.validate_result(compare(closed, changed))

    def test_native_crash_cannot_be_accepted_after_passing_assertions(self):
        from tools.run_mail_native_probe import REQUIRED_ASSERTIONS, validate_result
        result = {'supported': True, 'exit_code': 3221225477,
                  'tests': [{'name': name, 'passed': True} for name in REQUIRED_ASSERTIONS]}
        with self.assertRaises(ValueError):
            validate_result(result)

    def test_native_result_cannot_pass_without_confirmed_object_teardown(self):
        from tools.run_mail_native_probe import REQUIRED_ASSERTIONS, validate_result
        tests = [{'name': name, 'passed': True} for name in REQUIRED_ASSERTIONS
                 if name != 'scratch objects released before native shutdown']
        with self.assertRaises(ValueError):
            validate_result({'supported': True, 'exit_code': 0, 'tests': tests})

    def test_compilation_checks_cannot_accept_missing_runtime_calls(self):
        from tools.run_mail_native_probe import validate_reopened
        with self.assertRaises(ValueError):
            validate_reopened({'entry': 'native_body();'}, {'entry': 'wf_mail_mouse_wheel_up();'})
        validate_reopened({'entry': 'wf_mail_mouse_wheel_up();'}, {'entry': 'wf_mail_mouse_wheel_up();'})

    def test_editor_result_requires_dispatch_and_recovery_evidence(self):
        from tools.run_mail_native_probe import REQUIRED_ASSERTIONS, validate_result
        names = (
            'native drag moves before Mail capture',
            'Mail freezes an existing native drag',
            'dismiss click does not resume native drag',
            'dismiss release does not resume native drag',
            'fresh press resumes suspended native drag',
            'fresh release commits resumed native drag exactly once',
            'native eraser can delete the fixture line',
            'Mail prevents retained eraser deletion',
            'Mail clears retained eraser state',
            'native Step advances production with Mail open',
            'native paused Step remains paused with Mail open',
            'focus loss keeps suspended native drag frozen',
            'focus return alone cannot resume native drag',
            'fresh press after focus return resumes native drag',
            'disabled Mail restores native editor behavior',
        )
        automatic = [{'name': name, 'passed': True} for name in REQUIRED_ASSERTIONS]
        editor = [{'name': name, 'passed': True} for name in names]
        validate_result({'supported': True, 'editor': True, 'tests': automatic + editor})
        for index in range(len(editor)):
            with self.subTest(missing=editor[index]['name']), self.assertRaises(ValueError):
                validate_result({'supported': True, 'editor': True,
                                 'tests': automatic + editor[:index] + editor[index + 1:]})

    def test_editor_case_rejects_incompatible_modes_before_writing(self):
        from tools.run_mail_native_probe import build_probe
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for flags in ({'factory': True}, {'interactive': True}, {'_factory_mode': 'open'}):
                with self.subTest(flags=flags), self.assertRaisesRegex(ValueError, 'Editor case'):
                    build_probe(root / 'cli', root / 'original', root / 'runtime',
                                root / 'output', editor=True, **flags)
                self.assertFalse((root / 'output').exists())

    def test_editor_staging_refuses_changed_boundaries(self):
        from tools.mail_editor_probe import editor_imports
        for step in ('native_step();',
                     'native_step();\nenum UnknownEnum\n{Value_0}'):
            with self.subTest(step=step), self.assertRaises(ValueError):
                editor_imports('', step, '// authored fixture')


if __name__ == '__main__':
    unittest.main()
