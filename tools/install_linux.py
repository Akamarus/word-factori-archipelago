"""Native Linux setup for Word Factori in an existing Steam Proton prefix."""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import io
import json
import os
import re
import sys
import types
import zipfile
from pathlib import Path

if __package__:
    from . import linux_transaction as transaction
    from .enhanced_delta import apply_delta
else:
    import linux_transaction as transaction
    from enhanced_delta import apply_delta


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_SHA256 = 'd40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978'
PATCHED_SHA256 = '5a964d5155f8f7acc63fd90bc81882a0559c4586f5de4fd9a0657badd8594194'
DELTA_SHA256 = '5101e3172ecb171e36fce4e08c40b68d4cff077d8ef72452f988e010b1e03c5b'
MOD_FILES = ('levels.json', 'recipes.json', 'tips.json', 'credits.json', 'archipelago_campaign.json')
RECEIPT = 'archipelago_enhanced_install.json'


def load_paths_api(root: Path):
    """Load only the dependency-free member; never initialize the APWorld package."""
    name = '_word_factori_linux_platform_paths'
    archive = root / 'word_factori.apworld'
    if archive.is_file():
        with zipfile.ZipFile(archive) as world:
            try:
                source = world.read('word_factori/platform_paths.py')
            except KeyError:
                source = None
        if source is not None:
            module = types.ModuleType(name)
            module.__file__ = str(archive) + '/word_factori/platform_paths.py'
            sys.modules[name] = module
            exec(compile(source, module.__file__, 'exec'), module.__dict__)
            return module
    # Development checkout only; player ZIPs contain the member above.
    source_path = root / 'word_factori/platform_paths.py'
    if not source_path.is_file():
        raise ValueError('APWorld is missing the Linux path helper; obtain the complete player package')
    spec = importlib.util.spec_from_file_location(name, source_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


paths_api = load_paths_api(PACKAGE_ROOT)


def linux_processes():
    """Read same-user process identities; uncertain inspection fails closed."""
    if not sys.platform.startswith('linux'):
        raise ValueError('Installation requires native Linux; use the Windows installer on Windows')
    proc = Path('/proc')
    if not proc.is_dir():
        raise ValueError('Cannot inspect running processes: /proc is unavailable')
    records = []
    try:
        for directory in proc.iterdir():
            if not directory.name.isdecimal():
                continue
            try:
                if directory.stat().st_uid != os.getuid():
                    continue
                records.append((directory / 'cmdline').read_bytes() + b'\0' +
                               (directory / 'comm').read_bytes())
            except FileNotFoundError:
                continue  # A process exited while /proc was read.
    except OSError as error:
        raise ValueError('Cannot inspect running processes; close the game and make /proc readable') from error
    return records


def json_bytes(document):
    return (json.dumps(document, indent=2, sort_keys=True) + '\n').encode()


def check_campaign(files: dict[str, bytes]):
    for name in MOD_FILES:
        document = json.loads(files[name])
        if not isinstance(document, (dict, list)):
            raise ValueError(f'Invalid mod JSON: {name}')
    campaign = json.loads(files['archipelago_campaign.json'])
    if (not isinstance(campaign, dict)
            or (campaign.get('campaign_id'), campaign.get('level_count')) not in
                (('word-factori-hybrid', 40), ('word-factori-core', 30))
            or campaign.get('manifest_version') != '1.2.0'
            or not isinstance(campaign.get('manifest_digest'), str)
            or not re.fullmatch('[0-9a-f]{64}', campaign['manifest_digest'])):
        raise ValueError('Mod does not identify the supported Word Factori campaign')


def check_world(data: bytes):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if 'word_factori/__init__.py' not in archive.namelist() or archive.testzip() is not None:
            raise ValueError('Invalid Word Factori APWorld')


def receipt_game(value: str, paths):
    """Wine may record Z: outside pfx. Only accept the exact selected game."""
    if not isinstance(value, str) or not value:
        raise ValueError('Receipt game path is invalid')
    if value == str(paths.game_data):
        return
    match = re.fullmatch(r'([A-Za-z]):[\\/](.*)', value)
    if match is None:
        raise ValueError('Receipt is paired with another game copy')
    parts = re.split(r'[\\/]', match[2])
    if any(not part or part in ('.', '..') or ':' in part or any(ord(c) < 32 for c in part) for part in parts):
        raise ValueError('Unsafe Wine receipt path')
    drive = match[1].lower()
    mapped = paths.prefix / 'drive_c' if drive == 'c' else paths.prefix / 'dosdevices' / (drive + ':')
    if not mapped.is_dir():
        raise ValueError('Receipt drive has no mapping in selected Proton prefix')
    current = mapped.resolve()
    for part in parts:
        current = paths_api._casefold_child(current, part)
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ValueError('Receipt path crosses an alias after its drive mapping')
    if current.resolve() != paths.game_data.resolve() or not current.samefile(paths.game_data):
        raise ValueError('Receipt is paired with another game copy')


class LinuxInstaller:
    def __init__(self, paths, ap_worlds: Path, config: Path, package_root: Path = PACKAGE_ROOT,
                 process_reader=linux_processes):
        self.paths = paths_api.validate_installation(paths)
        self.worlds = paths_api.validate_ap_worlds(self.paths, Path(ap_worlds), resolve_root=True)
        self.config, self.package = Path(config), Path(package_root)
        self.process_reader = process_reader
        self.backup = paths.game_data.with_name('data.wf-ap-original.win')
        self.receipt = paths.mod_folder / RECEIPT
        self.targets = {name: paths.mod_folder / name for name in MOD_FILES}
        self.targets.update(world=self.worlds / 'word_factori.apworld', config=self.config,
                            receipt=self.receipt, backup=self.backup, game=paths.game_data)
        if len(set(self.targets.values())) != len(self.targets):
            raise ValueError('Installation targets overlap')
        # Explicit AP/config overrides must never redirect into game-owned trees.
        for external in (self.config, self.worlds / 'word_factori.apworld'):
            if external.is_relative_to(paths.prefix) or external.is_relative_to(paths.game_data.parent):
                raise ValueError('Native AP/config targets must be outside the game and Proton prefix')
        self.identity = {'schema': 1, 'game_data': str(paths.game_data), 'prefix': str(paths.prefix),
                         'factori_root': str(paths.factori_root)}
        identity = dict(self.identity, ap_worlds=str(self.worlds), config=str(self.config))
        self.transaction = transaction.Transaction(paths.factori_root / 'archipelago/install-transactions',
                                                    self.targets, identity, self.check_closed,
                                                    {'game': {ORIGINAL_SHA256, PATCHED_SHA256},
                                                     'backup': {None, ORIGINAL_SHA256}})
        for target in self.targets.values():
            transaction.safe_path(target)

    def check_closed(self):
        for record in self.process_reader():
            if not isinstance(record, bytes):
                raise ValueError('Process inspection returned an invalid identity')
            for component in re.split(b'[\x00\n]', record):
                basename = component.replace(b'\\', b'/').rsplit(b'/', 1)[-1].lower()
                basename = basename.replace(b'_', b' ').replace(b'-', b' ')
                if basename in (b'word factori', b'word factori.exe', b'word factori.ex',
                                b'wordfactori', b'wordfactori.exe'):
                    raise ValueError('Close Word Factori before installing, restoring or recovering; no process was killed')

    def _preflight(self):
        paths_api.validate_installation(self.paths)
        snapshot = {key: transaction.read(path) for key, path in self.targets.items()}
        current = transaction.digest(snapshot['game'])
        if current not in (ORIGINAL_SHA256, PATCHED_SHA256):
            raise ValueError('Unsupported or modified game data; no files changed')
        if snapshot['backup'] is not None and transaction.digest(snapshot['backup']) != ORIGINAL_SHA256:
            raise ValueError('Original backup is unknown or damaged; no files changed')
        if current == PATCHED_SHA256 and snapshot['backup'] is None:
            raise ValueError('Patched game requires its verified original backup')
        if snapshot['config'] is not None:
            if json.loads(snapshot['config']) != self.identity:
                raise ValueError('Configuration is paired with another installation or has invalid fields')
        if snapshot['receipt'] is not None:
            receipt = json.loads(snapshot['receipt'])
            if (not isinstance(receipt, dict) or receipt.get('protocol') != 'enhanced_v1'
                    or receipt.get('original_sha256') != ORIGINAL_SHA256
                    or receipt.get('patched_sha256') != PATCHED_SHA256):
                raise ValueError('Receipt hashes or protocol are invalid')
            receipt_game(receipt.get('game_data'), self.paths)
            if receipt.get('platform') == 'linux' and (receipt.get('prefix') != str(self.paths.prefix)
                    or receipt.get('factori_root') != str(self.paths.factori_root)
                    or receipt.get('ap_worlds') != str(self.worlds)):
                raise ValueError('Native receipt is paired with another installation')
        if snapshot['world'] is not None:
            check_world(snapshot['world'])
        existing_mod = {key: snapshot[key] for key in MOD_FILES}
        if any(data is not None for data in existing_mod.values()):
            if any(data is None for data in existing_mod.values()):
                raise ValueError('Existing mod is incomplete; refusing ambiguous owned files')
            check_campaign(existing_mod)
        return snapshot

    def _payload(self, source):
        world = transaction.read(self.package / 'word_factori.apworld')
        if world is None:
            raise ValueError('Package is missing word_factori.apworld')
        check_world(world)
        files = {name: transaction.read(self.package / 'game_mod/word factori archipelago' / name)
                 for name in MOD_FILES}
        if any(data is None for data in files.values()):
            raise ValueError('Package mod files are missing')
        check_campaign(files)
        compressed = transaction.read(self.package / 'tools/enhanced.patch.gz')
        if transaction.digest(compressed) != DELTA_SHA256:
            raise ValueError('Compressed delta failed pinned hash verification')
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            decoded = stream.read(128 * 1024 * 1024 + 1)
        if len(decoded) > 128 * 1024 * 1024:
            raise ValueError('Delta payload exceeds size limit')
        delta = json.loads(decoded)
        if (not isinstance(delta, dict) or delta.get('protocol') != 'enhanced_v1'
                or delta.get('original_sha256') != ORIGINAL_SHA256
                or delta.get('patched_sha256') != PATCHED_SHA256
                or not isinstance(delta.get('operations'), list)
                or any(not isinstance(op, list) for op in delta['operations'])):
            raise ValueError('Delta does not match this integration')
        patched = apply_delta(source, delta)
        receipt = {'protocol': 'enhanced_v1', 'original_sha256': ORIGINAL_SHA256,
                   'patched_sha256': PATCHED_SHA256, 'game_data': str(self.paths.game_data),
                   'platform': 'linux', 'prefix': str(self.paths.prefix),
                   'factori_root': str(self.paths.factori_root), 'ap_worlds': str(self.worlds)}
        return dict(files, world=world, config=json_bytes(self.identity), receipt=json_bytes(receipt),
                    backup=source, game=patched)

    def prepare(self, operation='install'):
        if self.transaction.pending():
            raise ValueError('Interrupted installation detected; run recover first')
        before = self._preflight()
        if operation == 'verify':
            if (transaction.digest(before['game']) != PATCHED_SHA256 or before['receipt'] is None
                    or before['world'] is None or before['config'] is None
                    or any(before[name] is None for name in MOD_FILES)):
                raise ValueError('Installation is incomplete or the original game is restored')
            return {}, before
        self.check_closed()
        if operation == 'install':
            source = before['backup'] if before['backup'] is not None else before['game']
            changes = self._payload(source)
        elif operation in ('restore', 'uninstall'):
            if before['receipt'] is None:
                raise ValueError('A verified installation receipt is required for restoration/removal')
            if before['backup'] is None:
                raise ValueError('Restoration/removal requires the verified original backup')
            source = before['backup']
            # Retain pairing evidence after restore so a later uninstall does not
            # need to patch the game again. Readiness still checks the game hash.
            changes = {'game': source}
            if operation == 'uninstall':
                changes.update({name: None for name in ('receipt', *MOD_FILES, 'world', 'config')})
        else:
            raise ValueError('Unknown operation')
        for key in changes:
            transaction.writable(self.targets[key])
        transaction.writable(self.transaction.journal)
        return changes, before

    def run(self, operation='install'):
        if operation == 'recover':
            self.transaction.recover()
            return 'Recovery complete. Previous files restored; historical backups preserved.'
        changes, before = self.prepare(operation)
        if operation == 'verify':
            return 'Installation verified.'
        self.transaction.apply(changes, {key: transaction.digest(value) for key, value in before.items()})
        return {'install': 'Installed. Restart Archipelago and Word Factori.',
                'restore': 'Original game restored. Saves and backups preserved.',
                'uninstall': 'Integration removed. Saves, unowned mod files and backups preserved.'}[operation]


def select_paths(args, input_fn=input):
    explicit = (args.game_data, args.prefix, args.factori_root)
    if any(explicit):
        if not all(explicit):
            raise ValueError('Explicit selection requires --game-data, --prefix and --factori-root together')
        return paths_api.validate_installation(paths_api.InstallationPaths(*map(Path, explicit)))
    if args.config.exists():
        return paths_api.load_installation(args.config)
    candidates = paths_api.discover_installations()
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError('No initialized Proton installation found. Launch and close the game once through Steam, '
                         'or supply --game-data, --prefix and --factori-root')
    if args.yes or not sys.stdin.isatty():
        raise ValueError('Several installations found; select one using the explicit path options')
    for index, candidate in enumerate(candidates, 1):
        print(f'{index}: {candidate.game_data}\n   {candidate.factori_root}')
    answer = input_fn('Select installation number: ')
    if not answer.isdecimal() or not 1 <= int(answer) <= len(candidates):
        raise ValueError('Invalid installation selection')
    return candidates[int(answer) - 1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', nargs='?', default='install',
                        choices=('install', 'verify', 'restore', 'uninstall', 'recover'))
    for option in ('game-data', 'prefix', 'factori-root', 'ap-worlds'):
        parser.add_argument('--' + option, type=Path)
    parser.add_argument('--config', type=Path, default=paths_api.config_path())
    parser.add_argument('--yes', action='store_true', help='Confirm chosen paths; never resolves ambiguous discovery')
    args = parser.parse_args(argv)
    try:
        if sys.version_info < (3, 12):
            raise ValueError('Python 3.12 or newer is required')
        paths = select_paths(args)
        worlds = args.ap_worlds
        if worlds is None:
            if args.yes or not sys.stdin.isatty():
                raise ValueError('Supply --ap-worlds with the existing native Archipelago worlds or custom_worlds directory')
            worlds = Path(input('Native Archipelago worlds directory (worlds or custom_worlds): ').strip())
        setup = LinuxInstaller(paths, worlds, args.config)
        if args.operation != 'recover':
            setup.prepare(args.operation)
        print(f'Game: {paths.game_data}\nProton prefix: {paths.prefix}\nMod: {paths.mod_folder}\n'
              f'APWorld: {setup.worlds / "word_factori.apworld"}\nConfiguration: {args.config}')
        if args.operation != 'verify' and not args.yes:
            if not sys.stdin.isatty() or input(f'Proceed with {args.operation}? [y/N] ').strip().lower() != 'y':
                raise ValueError('Cancelled; no files changed')
        print(setup.run(args.operation))
        return 0
    except (ValueError, OSError, EOFError, UnicodeError, zipfile.BadZipFile) as error:
        print(f'Setup stopped: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
