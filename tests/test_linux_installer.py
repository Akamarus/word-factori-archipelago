import base64
import gzip
import hashlib
import json
import argparse
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import install_linux as installer


class LinuxInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / 'game' / 'data.win'
        self.game.parent.mkdir()
        self.original, self.patched = b'original game bytes', b'original PATCHED game bytes'
        self.game.write_bytes(self.original)
        self.prefix = self.root / 'pfx'
        self.factori = self.prefix / 'drive_c/users/steamuser/AppData/Local/factori'
        self.factori.mkdir(parents=True)
        self.worlds = self.root / 'custom_worlds'
        self.worlds.mkdir()
        self.config = self.root / 'config/installation.json'
        self.package = self.root / 'package'
        (self.package / 'tools').mkdir(parents=True)
        mod = self.package / 'game_mod/word factori archipelago'
        mod.mkdir(parents=True)
        for name in ('levels', 'recipes', 'tips', 'credits'):
            (mod / (name + '.json')).write_text('{}')
        (mod / 'archipelago_campaign.json').write_text(json.dumps({
            'campaign_id': 'word-factori-hybrid', 'manifest_version': '1.2.0',
            'level_count': 40, 'manifest_digest': 'a' * 64}))
        with zipfile.ZipFile(self.package / 'word_factori.apworld', 'w') as archive:
            archive.writestr('word_factori/__init__.py', '# fixture')
        original_hash = hashlib.sha256(self.original).hexdigest()
        patched_hash = hashlib.sha256(self.patched).hexdigest()
        delta = {'format': 1, 'protocol': 'enhanced_v1', 'original_sha256': original_hash,
                 'patched_sha256': patched_hash, 'size': len(self.patched),
                 'operations': [['copy', 0, 9], ['data', base64.b64encode(b'PATCHED game bytes').decode()]]}
        compressed = gzip.compress(json.dumps(delta).encode())
        (self.package / 'tools/enhanced.patch.gz').write_bytes(compressed)
        for name, value in [('ORIGINAL_SHA256', original_hash), ('PATCHED_SHA256', patched_hash),
                            ('DELTA_SHA256', hashlib.sha256(compressed).hexdigest())]:
            override = patch.object(installer, name, value)
            override.start()
            self.addCleanup(override.stop)
        self.paths = installer.paths_api.InstallationPaths(self.game, self.prefix, self.factori)
        self.setup = installer.LinuxInstaller(self.paths, self.worlds, self.config,
                                              self.package, process_reader=lambda: [])

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()
                and 'install-transactions' not in p.parts and not p.name.startswith('.wf-ap-')}

    def test_first_install_and_idempotent_update(self):
        self.setup.run('install')
        self.assertEqual(self.game.read_bytes(), self.patched)
        self.assertEqual(self.setup.backup.read_bytes(), self.original)
        self.assertEqual(json.loads(self.setup.receipt.read_text())['game_data'], str(self.game))
        before = self.snapshot()
        self.setup.run('install')
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.setup.run('verify'), 'Installation verified.')

    def test_bad_original_preserves_all_targets(self):
        self.game.write_bytes(b'unknown')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.setup.run('install')
        self.assertEqual(self.snapshot(), before)

    def test_restore_then_uninstall_preserves_saves_and_backups(self):
        self.setup.run('install')
        save = self.paths.mod_folder / 'player.save'
        save.write_bytes(b'precious save')
        self.setup.run('restore')
        self.assertEqual(self.game.read_bytes(), self.original)
        self.assertFalse(self.setup.receipt.exists())
        self.setup.run('install')
        self.setup.run('uninstall')
        self.assertEqual(self.game.read_bytes(), self.original)
        self.assertEqual(save.read_bytes(), b'precious save')
        self.assertEqual(self.setup.backup.read_bytes(), self.original)
        self.assertFalse((self.worlds / 'word_factori.apworld').exists())
        self.assertFalse(self.config.exists())

    def test_bad_backup_receipt_and_config_pairing(self):
        self.setup.run('install')
        for destination, payload in [(self.setup.backup, b'bad'),
                (self.setup.receipt, b'{"game_data":"/unrelated/data.win"}'),
                (self.config, b'{"schema":1,"game_data":"/unrelated/data.win"}')]:
            with self.subTest(destination=destination):
                previous = destination.read_bytes()
                destination.write_bytes(payload)
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    self.setup.run('install')
                self.assertEqual(before, self.snapshot())
                destination.write_bytes(previous)

    def test_bad_delta_preserves_targets(self):
        (self.package / 'tools/enhanced.patch.gz').write_bytes(b'bad delta')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.setup.run('install')
        self.assertEqual(before, self.snapshot())

    def test_running_or_unavailable_process_inspection_refuses(self):
        for reader in (lambda: [b'word factori.exe'], lambda: (_ for _ in ()).throw(PermissionError('proc'))):
            self.setup.process_reader = reader
            before = self.snapshot()
            with self.assertRaises((ValueError, PermissionError)):
                self.setup.run('install')
            self.assertEqual(before, self.snapshot())

    def test_failure_between_replacements_rolls_back(self):
        before = self.snapshot()
        original_replace = installer.transaction.os.replace
        def fail_game(source, target):
            if Path(target) == self.game:
                raise PermissionError('simulated replacement refusal')
            return original_replace(source, target)
        with patch.object(installer.transaction.os, 'replace', side_effect=fail_game):
            with self.assertRaises(PermissionError):
                self.setup.run('install')
        self.assertEqual(before, self.snapshot())

    def test_interrupted_install_requires_explicit_recovery(self):
        before = self.snapshot()
        original_replace = installer.transaction.os.replace
        def interrupt(source, target):
            if Path(target) == self.game:
                raise KeyboardInterrupt()
            return original_replace(source, target)
        with patch.object(installer.transaction.os, 'replace', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.setup.run('install')
        with self.assertRaisesRegex(ValueError, 'recover'):
            self.setup.run('install')
        self.setup.run('recover')
        self.assertEqual(before, self.snapshot())

    def test_cli_help_and_invalid_arguments(self):
        script = Path(installer.__file__)
        help_result = subprocess.run([sys.executable, str(script), '--help'], capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn('--game-data', help_result.stdout)
        invalid = subprocess.run([sys.executable, str(script), 'unknown'], capture_output=True, text=True)
        self.assertNotEqual(invalid.returncode, 0)

    def test_process_guard_ignores_installer_path_but_detects_wine_executable(self):
        self.setup.process_reader = lambda: [b'python3\0/home/word-factori-archipelago/tools/install_linux.py\0']
        self.setup.run('install')
        self.setup.process_reader = lambda: [b'wine64\0Z:\\games\\word factori.exe\0']
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.setup.run('restore')
        self.assertEqual(before, self.snapshot())

    def interrupted(self):
        original_replace = installer.transaction.os.replace
        def interrupt(source, target):
            if Path(target) == self.game:
                raise KeyboardInterrupt()
            return original_replace(source, target)
        with patch.object(installer.transaction.os, 'replace', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.setup.run('install')
        return self.setup.transaction.journal

    def test_recovery_rejects_hostile_journal_paths_before_any_mutation(self):
        journal = self.interrupted()
        real = journal.read_bytes()
        for key, value in [('token', '../escape'), ('identity', {}),
                           ('entries', [{'key': '../../outside', 'before': None, 'after': None}])]:
            with self.subTest(key=key):
                document = json.loads(real)
                document[key] = value
                journal.write_text(json.dumps(document))
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    self.setup.run('recover')
                self.assertEqual(before, self.snapshot())
        journal.write_bytes(real)
        self.setup.run('recover')

    def test_recovery_cannot_delete_game_via_forged_before_digest(self):
        journal = self.interrupted()
        document = json.loads(journal.read_text())
        index = next(i for i, e in enumerate(document['entries']) if e['key'] == 'game')
        document['entries'][index]['before'] = None
        document['entries'][index]['after'] = hashlib.sha256(self.original).hexdigest()
        (journal.parent / document['token'] / str(index)).unlink()
        self.setup.transaction._stage(self.game, document['token'], index).unlink()
        journal.write_text(json.dumps(document))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.setup.run('recover')
        self.assertEqual(before, self.snapshot())

    def test_recovery_refuses_changed_target_and_damaged_backup(self):
        journal = self.interrupted()
        self.game.write_bytes(b'external change')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.setup.run('recover')
        self.assertEqual(before, self.snapshot())
        self.game.write_bytes(self.original)
        document = json.loads(journal.read_text())
        index = next(i for i, e in enumerate(document['entries']) if e['key'] == 'game')
        (journal.parent / document['token'] / str(index)).write_bytes(b'damaged history')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.setup.run('recover')
        self.assertEqual(before, self.snapshot())

    def test_generated_room_json_does_not_break_verify_or_uninstall(self):
        self.setup.run('install')
        (self.paths.mod_folder / 'levels.json').write_text('{"generated":"room"}')
        campaign = self.paths.mod_folder / 'archipelago_campaign.json'
        document = json.loads(campaign.read_text())
        document['manifest_digest'] = 'b' * 64
        campaign.write_text(json.dumps(document))
        self.assertEqual(self.setup.run('verify'), 'Installation verified.')
        self.setup.run('uninstall')
        self.assertEqual(self.game.read_bytes(), self.original)

    def test_permission_preflight_leaves_bytes_unchanged(self):
        before = self.snapshot()
        with patch.object(installer.transaction.os, 'access', return_value=False):
            with self.assertRaises(PermissionError):
                self.setup.run('install')
        self.assertEqual(before, self.snapshot())

    def test_ambiguous_discovery_never_selects_first_with_yes(self):
        args = argparse.Namespace(game_data=None, prefix=None, factori_root=None,
                                  config=self.config, yes=True)
        with patch.object(installer.paths_api, 'discover_installations', return_value=[self.paths, self.paths]):
            with self.assertRaisesRegex(ValueError, 'Several'):
                installer.select_paths(args)

    def test_cli_verify_reports_missing_setup_without_writes(self):
        before = self.snapshot()
        command = [sys.executable, str(Path(installer.__file__)), 'verify', '--yes',
                   '--game-data', str(self.game), '--prefix', str(self.prefix),
                   '--factori-root', str(self.factori), '--ap-worlds', str(self.worlds),
                   '--config', str(self.config)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Setup stopped:', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_archive_helper_import_does_not_initialize_apworld(self):
        source = (Path(installer.__file__).resolve().parent.parent / 'word_factori/platform_paths.py').read_bytes()
        with zipfile.ZipFile(self.package / 'word_factori.apworld', 'w') as archive:
            archive.writestr('word_factori/__init__.py', 'raise RuntimeError("AP initialization forbidden")')
            archive.writestr('word_factori/platform_paths.py', source)
        api = installer.load_paths_api(self.package)
        self.assertEqual(api.MOD_NAME, 'word factori archipelago')

    def test_no_receipt_uninstall_cannot_remove_unpaired_files(self):
        self.setup.run('install')
        self.setup.receipt.unlink()
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.setup.run('uninstall')
        self.assertEqual(before, self.snapshot())

    def test_competing_journal_is_not_recovered_by_losing_installer(self):
        original_link = installer.transaction.os.link
        def compete(source, target):
            if Path(target) == self.setup.transaction.journal:
                Path(target).write_bytes(b'{"another":"transaction"}')
                raise FileExistsError('another installer won')
            original_link(source, target)
        before = self.snapshot()
        with patch.object(installer.transaction.os, 'link', side_effect=compete):
            with self.assertRaises(FileExistsError):
                self.setup.run('install')
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.setup.transaction.journal.read_bytes(), b'{"another":"transaction"}')

    def test_journal_publication_interruption_keeps_complete_recoverable_document(self):
        before = self.snapshot()
        original_link = installer.transaction.os.link
        def interrupt(source, target):
            original_link(source, target)
            raise KeyboardInterrupt()
        with patch.object(installer.transaction.os, 'link', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.setup.run('install')
        self.setup.run('recover')
        self.assertEqual(before, self.snapshot())

    def test_parent_traversal_override_is_rejected(self):
        unsafe = self.root / 'config/../game/data.win'
        (self.root / 'config').mkdir()
        with self.assertRaises(ValueError):
            installer.LinuxInstaller(self.paths, self.worlds, unsafe, self.package,
                                     process_reader=lambda: [])

    def test_ordinary_update_failure_restores_previous_integration_bytes(self):
        self.setup.run('install')
        (self.paths.mod_folder / 'levels.json').write_text('{"previous":"room"}')
        before = self.snapshot()
        original_replace = installer.transaction.os.replace
        failed = False
        def fail_once(source, target):
            nonlocal failed
            if Path(target) == self.game and not failed:
                failed = True
                raise PermissionError('simulated failure')
            return original_replace(source, target)
        with patch.object(installer.transaction.os, 'replace', side_effect=fail_once):
            with self.assertRaises(PermissionError):
                self.setup.run('install')
        self.assertEqual(before, self.snapshot())
        self.assertTrue(any(self.setup.transaction.root.glob('*/0')))

    def test_running_game_detected_again_immediately_before_replacement(self):
        before = self.snapshot()
        calls = 0
        def reader():
            nonlocal calls
            calls += 1
            return [b'word factori.exe'] if calls == 3 else []
        self.setup.process_reader = reader
        with self.assertRaises(ValueError):
            self.setup.run('install')
        self.assertEqual(before, self.snapshot())

    def test_game_change_during_preparation_is_not_overwritten(self):
        calls = 0
        def reader():
            nonlocal calls
            calls += 1
            if calls == 2:
                self.game.write_bytes(b'external change')
            return []
        self.setup.process_reader = reader
        with self.assertRaises(ValueError):
            self.setup.run('install')
        self.assertEqual(self.game.read_bytes(), b'external change')
        self.assertFalse(self.setup.receipt.exists())

    def test_malformed_operations_are_rejected_after_compressed_hash_validation(self):
        location = self.package / 'tools/enhanced.patch.gz'
        document = json.loads(gzip.decompress(location.read_bytes()))
        for operations in ([["copy", 0, 100000]], [["data", "!"]], [None]):
            with self.subTest(operations=operations):
                document['operations'] = operations
                compressed = gzip.compress(json.dumps(document).encode())
                location.write_bytes(compressed)
                before = self.snapshot()
                with patch.object(installer, 'DELTA_SHA256', hashlib.sha256(compressed).hexdigest()):
                    with self.assertRaises(ValueError):
                        self.setup.run('install')
                self.assertEqual(before, self.snapshot())

    def test_wine_c_receipt_migration_independently_checks_game_and_backup(self):
        game = self.prefix / 'drive_c/Games/Word Factori/data.win'
        game.parent.mkdir(parents=True)
        game.write_bytes(self.original)
        paths = installer.paths_api.InstallationPaths(game, self.prefix, self.factori)
        setup = installer.LinuxInstaller(paths, self.worlds, self.config, self.package,
                                         process_reader=lambda: [])
        setup.run('install')
        receipt = {'protocol': 'enhanced_v1', 'original_sha256': installer.ORIGINAL_SHA256,
                   'patched_sha256': installer.PATCHED_SHA256,
                   'game_data': 'C:\\Games\\Word Factori\\data.win'}
        setup.receipt.write_text(json.dumps(receipt))
        setup.run('install')
        self.assertEqual(json.loads(setup.receipt.read_text())['game_data'], str(game))
        self.assertEqual(setup.backup.read_bytes(), self.original)
        receipt['game_data'] = 'C:\\Games\\Other Copy\\data.win'
        setup.receipt.write_text(json.dumps(receipt))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            setup.run('install')
        self.assertEqual(before, self.snapshot())

    @unittest.skipIf(os.name == 'nt', 'Proton dosdevices names require a Linux filesystem')
    def test_wine_external_drive_maps_exact_selected_game(self):
        self.setup.run('install')
        mappings = self.prefix / 'dosdevices'
        mappings.mkdir()
        (mappings / 'z:').symlink_to('/', target_is_directory=True)
        receipt = {'protocol': 'enhanced_v1', 'original_sha256': installer.ORIGINAL_SHA256,
                   'patched_sha256': installer.PATCHED_SHA256,
                   'game_data': 'Z:' + str(self.game).replace('/', '\\')}
        self.setup.receipt.write_text(json.dumps(receipt))
        self.setup.run('install')
        self.assertEqual(json.loads(self.setup.receipt.read_text())['game_data'], str(self.game))

    def test_hardlinked_owned_target_refused(self):
        self.setup.run('install')
        alias = self.root / 'precious-copy'
        os.link(self.setup.receipt, alias)
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.setup.run('uninstall')
        self.assertEqual(before, self.snapshot())

    def test_changed_staged_game_is_never_installed(self):
        calls = 0
        def reader():
            nonlocal calls
            calls += 1
            if calls == 3:
                for stage in self.game.parent.glob('.wf-ap-*.tmp'):
                    stage.write_bytes(b'corrupted staging')
            return []
        self.setup.process_reader = reader
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.setup.run('install')
        self.assertEqual(self.game.read_bytes(), self.original)
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
