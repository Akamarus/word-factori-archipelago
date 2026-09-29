"""Replay APTests failures using real packaged AP generation in disposable folders.

No installed worlds, public servers, game binaries or saves are accessed.
Optionally pass the test-service tracker.apworld to compare actual UT spheres.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verify_connected_multiworld import stage_core


def player_options(case):
    return {
        'custom_level_set': 'core_campaign', 'recipe_checks': False,
        'type_a_word_checks': False, 'type_a_word_words': [], 'progressive_machines': True,
        **{key: value for key, value in case.items() if key not in {'run', 'seed'}},
    }


def worker(run, deps, tracker_enabled, fault_inaccessible=False, profile=False, kingdom_hearts=False):
    if deps:
        sys.path.insert(0, str(deps))
    sys.path.insert(0, str(run / 'ap'))
    os.chdir(run)
    import Utils
    for func, folder in ((Utils.user_path, 'user'), (Utils.home_path, 'user'), (Utils.cache_path, 'cache')):
        func.cached_path = str(run / folder)
        (run / folder).mkdir(exist_ok=True)
    import yaml
    import settings
    settings.no_gui = True
    (run / 'players').mkdir()
    # Prevent optional Tracker settings from requesting an interactive folder.
    (run / 'user/host.yaml').write_text(yaml.safe_dump({
        'universal_tracker': {'player_files_path': str(run / 'players')},
    }), encoding='utf-8')
    import Generate
    import Main
    case = json.loads((run / 'case.json').read_text())
    options = player_options(case)
    (run / 'players/player.yaml').write_text(yaml.safe_dump({'game': 'Word Factori', 'Word Factori': options}), encoding='utf-8')
    if kingdom_hearts:
        (run / 'players/zz-kingdom.yaml').write_text(yaml.safe_dump({
            'game': 'Kingdom Hearts', 'Kingdom Hearts': {}}), encoding='utf-8')
    rolled, seed = Generate.main(Generate.mystery_argparse([
        '--player_files_path', str(run / 'players'), '--seed', str(case['seed']),
        '--outputpath', str(run / 'output'), '--spoiler', '1', '--plando', 'items,connections,texts,bosses']))
    started = time.perf_counter()
    if profile:
        import cProfile
        profiler = cProfile.Profile()
        mw = profiler.runcall(Main.main, rolled, seed)
        profiler.dump_stats(str(run / 'generation.prof'))
    else:
        mw = Main.main(rolled, seed)
    generation_seconds = time.perf_counter() - started
    if fault_inaccessible:
        # Negative acceptance probe: victory remains possible, but full
        # accessibility must reject even an unreachable filler location.
        filler = next(loc for loc in mw.get_filled_locations() if loc.item.name == 'I Sticker')
        filler.access_rule = lambda state: False
    assert mw.can_beat_game(), 'victory is unreachable'
    assert mw.fulfills_accessibility(), 'configured accessibility is not satisfied'
    games = [mw.game[player] for player in mw.player_ids]
    if kingdom_hearts:
        assert games == ['Word Factori', 'Kingdom Hearts'], games
    import worlds.word_factori as wf
    assert '.apworld' in wf.__file__, 'regression must test the packaged world'
    from MultiServer import Context
    with zipfile.ZipFile(next((run / 'output').glob('*.zip'))) as archive:
        raw = Context.decompress(archive.read(next(name for name in archive.namelist() if name.endswith('.archipelago'))))['slot_data'][1]
    assert isinstance(raw['level_order'], tuple), 'expected actual saved multidata'
    assert wf.WordFactoriWorld.interpret_slot_data(raw) == mw.worlds[1].fill_slot_data()
    tracker_spheres = None
    if tracker_enabled:
        from worlds.tracker import TrackerCore, DeferredEntranceMode
        from NetUtils import NetworkItem
        tracker = TrackerCore.TrackerCore(logging.getLogger('aptests-regression'), False, False)
        tracker.enforce_deferred_connections = DeferredEntranceMode.disabled
        tracker.set_slot_params(wf.GAME, 1, mw.player_name[1], 1)
        tracker.initalize_tracker_core(wf.WordFactoriWorld, raw)
        assert tracker.multiworld is not None, tracker.gen_error
        assert tracker.multiworld.worlds[1].fill_slot_data() == mw.worlds[1].fill_slot_data()
        inventory = [NetworkItem(item.code, -2, 1, item.classification)
                     for item in mw.precollected_items[1] if item.code is not None]
        missing = {loc.address for loc in mw.get_locations() if loc.address is not None}
        tracker_spheres = 0
        for sphere in mw.get_sendable_spheres():
            expected = {loc.name: loc for loc in sphere if loc.address is not None}
            if not expected:
                break
            tracker.set_missing_locations(set(missing))
            tracker.set_items_received(list(inventory))
            actual = tracker.updateTracker()
            assert set(actual.in_logic_locations) == set(expected), (actual.in_logic_locations, list(expected))
            for loc in expected.values():
                inventory.append(NetworkItem(loc.item.code, loc.address, 1, loc.item.classification))
                missing.remove(loc.address)
            tracker_spheres += 1
    result = {'run': case['run'], 'status': 'pass', 'generation_seconds': generation_seconds,
              'tracker_spheres': tracker_spheres, 'games': games}
    (run / 'result.json').write_text(json.dumps(result), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ap-source', type=Path, required=True)
    parser.add_argument('--apworld', type=Path, default=ROOT / 'word_factori.apworld')
    parser.add_argument('--dependency-path', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tracker', type=Path)
    parser.add_argument('--kingdom-hearts', type=Path,
                        help='trusted kh1.apworld companion for mixed-world generation')
    parser.add_argument('--extra-seeds', type=int, default=0)
    parser.add_argument('--case', help='run only this fixture ID')
    parser.add_argument('--profile', action='store_true', help='save per-case generation CPU profiles')
    parser.add_argument('--fault-inaccessible', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.tracker and args.kingdom_hearts:
        parser.error('Tracker sphere replay currently supports single-player fixtures only')
    if args.worker:
        logging.basicConfig(level=logging.WARNING)
        worker(args.output.resolve(), args.dependency_path, bool(args.tracker), args.fault_inaccessible,
               args.profile, bool(args.kingdom_hearts))
        return 0
    args.output.mkdir(parents=True, exist_ok=False)
    # Freeze the input once: a concurrent development rebuild must not change
    # the package halfway through a matrix or leave a worker with a partial ZIP.
    snapshot = args.output.resolve() / 'input.apworld'
    shutil.copyfile(args.apworld, snapshot)
    with zipfile.ZipFile(snapshot) as archive:
        if archive.testzip() is not None:
            raise ValueError('APWorld snapshot failed ZIP integrity verification')
    identity = {'apworld_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest()}
    if args.kingdom_hearts:
        companion = args.output.resolve() / 'kh1.apworld'
        shutil.copyfile(args.kingdom_hearts, companion)
        with zipfile.ZipFile(companion) as archive:
            if archive.testzip() is not None:
                raise ValueError('companion APWorld failed ZIP integrity verification')
        identity['kingdom_hearts_sha256'] = hashlib.sha256(companion.read_bytes()).hexdigest()
    (args.output / 'input.json').write_text(json.dumps(identity), encoding='utf-8')
    cases = json.loads((ROOT / 'tests/fixtures/aptests_progressive_failures.json').read_text())
    if args.tracker or args.kingdom_hearts:
        cases += json.loads((ROOT / 'tests/fixtures/aptests_tracker_failures.json').read_text())
    for number in range(args.extra_seeds):
        cases.append({'run': f'extra-{number}', 'seed': 920000 + number,
                      'accessibility': 'full' if number % 2 else 'minimal',
                      'goal': 'campaign_count' if number % 3 else 'final_factory', 'campaign_count': 30,
                      'custom_level_set': 'discovery_labs' if number % 4 == 0 else 'core_campaign',
                      'recipe_checks': number % 7 == 0,
                      'type_a_word_checks': number % 5 == 0, 'type_a_word_count': 2,
                      'type_a_word_words': ['JACK', '99'],
                      'start_inventory_from_pool': {'Progressive Rotation Access': 1} if number % 6 == 0 else {}})
    if args.case is not None:
        cases = [case for case in cases if str(case['run']) == args.case]
        if not cases:
            parser.error('unknown fixture ID')
    results = []
    for case in cases:
        run = args.output.resolve() / str(case['run'])
        run.mkdir()
        stage_core(args.ap_source.resolve(), run / 'ap')
        (run / 'user/worlds').mkdir(parents=True)
        shutil.copyfile(snapshot, run / 'user/worlds/word_factori.apworld')
        if args.tracker:
            shutil.copyfile(args.tracker, run / 'user/worlds/tracker.apworld')
        if args.kingdom_hearts:
            shutil.copyfile(companion, run / 'user/worlds/kh1.apworld')
        (run / 'case.json').write_text(json.dumps(case), encoding='utf-8')
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--ap-source', str(args.ap_source), '--output', str(run)]
        if args.dependency_path:
            command += ['--dependency-path', str(args.dependency_path.resolve())]
        if args.tracker:
            command += ['--tracker', str(args.tracker.resolve())]
        if args.kingdom_hearts:
            command += ['--kingdom-hearts', str(companion)]
        if args.fault_inaccessible:
            command += ['--fault-inaccessible']
        if args.profile:
            command += ['--profile']
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', SKIP_REQUIREMENTS_UPDATE='1', AP_NO_PROMPT='1')
        with (run / 'worker.log').open('w', encoding='utf-8') as log:
            try:
                result = subprocess.run(command, env=env, cwd=run, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                status = json.loads((run / 'result.json').read_text()) if result.returncode == 0 else {'run': case['run'], 'status': 'fail'}
            except subprocess.TimeoutExpired:
                status = {'run': case['run'], 'status': 'timeout'}
        results.append(status)
        print(status, flush=True)
    (args.output / 'report.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return int(any(result['status'] != 'pass' for result in results))


if __name__ == '__main__':
    raise SystemExit(main())
