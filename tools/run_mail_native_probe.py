"""Scratch-only native Mail feasibility runner. Never installs or edits a save."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import ctypes
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.enhanced_hooks import ORIGINAL_SHA256, verify_original
from tools.mail_hooks import CODE_ENTRIES, transform_mail_sources, reader_helpers, production_mail_helpers
from tools.run_type_word_native_probe import validate_probe_paths, discover_executable, _reject_links
from tools.mail_factory_probe import FACTORY_ENTRIES, factory_imports
from tools.mail_editor_probe import EDITOR_ENTRIES, EDITOR_ASSERTIONS, editor_imports

REQUIRED_ASSERTIONS = (
    'unblocked native mapped key', 'unblocked native mouse consumer',
    'button opens in same frame', 'native key press suppressed',
    'native held key suppressed', 'native key release suppressed',
    'native mouse press suppressed', 'native mouse hold suppressed',
    'native mouse release suppressed', 'native text buffer suppressed',
    'real clickable dispatcher clears all edge flags',
    'Chat tab does not close panel', 'typing belongs to Chat',
    'wheel belongs to panel', 'Items tab does not close panel',
    'outside dismiss consumes click', 'dismiss hold cannot reach factory',
    'dismiss release cannot reach factory', 'native input resumes after release',
    'F8 opens immediately', 'Escape closes without key leak',
    'focus loss releases capture and draft', 'native room event resets state',
    'installed native font measures text', 'disabled UI leaves native controls unchanged',
    'scratch objects released before native shutdown',
)
INTERACTIVE_ASSERTIONS = (
    'real raw key press exercised while Mail open',
    'real raw key release exercised while Mail open',
    'real raw key held while Mail open',
    'real raw keyboard did not reach native consumer',
)
FACTORY_ASSERTIONS = (
    'closed Mail factory completes ten words',
    'open Mail factory completes ten words',
    'Mail does not change production tick count',
    'Mail does not change completion journal',
    'Mail stays open throughout native production',
    'native production completion is idempotent with Mail open',
)
BRIDGE_ASSERTIONS = (
    'bridge JSON snapshot round trip', 'bridge wire null uses native null pointer',
    'bridge decoded JSON booleans accepted', 'bridge arbitrary truthy flags refused',
    'bridge valid bounded snapshot', 'bridge invalid word status refused',
    'bridge unknown fields refused', 'bridge excess rows refused',
    'bridge boolean counters refused', 'bridge native first replacement succeeds',
    'bridge native existing replacement succeeds', 'bridge native bounded read round trip',
    'bridge oversize file refused before parse', 'bridge accepts matching manifest snapshot',
    'bridge persisted heartbeat cannot authorize actions', 'bridge observed advance authorizes actions',
    'bridge unsupported action refused', 'bridge submitted chat queued once',
    'bridge full queue blocks another send', 'bridge matching acknowledgment frees queue',
    'bridge backward revision disables sending', 'bridge five second stale heartbeat refused',
    'bridge restart clears pending without resend', 'bridge wrong room clears cached history',
    'bridge shutdown disables transport',
)
UI_ASSERTIONS = (
    'UI first click opens and captures native controls',
    'UI Chat switch keeps panel open', 'UI unfocused chat does not collect text',
    'UI focused chat receives text only', 'UI Shift Enter inserts newline without sending',
    'UI Enter sends one bounded request', 'UI held Enter does not repeat send',
    'UI Items from Chat stays open', 'UI filters update locally',
    'UI Latest requests current history',
    'UI words tab lists authoritative selected target', 'UI key and door have readable labels',
    'UI status tab is present', 'UI outside dismissal retains click capture',
    'UI rejected action has visible status',
    'UI controls resume after dismissal release', 'UI focus loss clears draft and capture',
    'UI minimum viewport layout stays bounded', 'UI room epoch clears old draft and popup state',
    'UI thousand toggles and hundred transitions stay bounded',
    'UI disabled capability leaves gameplay input alone',
)


def launch_probe_process(*args, **kwargs):
    """Launch a scratch child without OS fault dialogs; never hide exit failures.

    Used only by synchronous developer probes. Children inherit this process's
    error mode. Restore it immediately, including when spawning fails; no global
    Windows settings, player client settings, or exception handling are changed.
    """
    if os.name != 'nt':
        return subprocess.Popen(*args, **kwargs)
    if kwargs.get('creationflags', 0) & 0x04000000:
        raise ValueError('CREATE_DEFAULT_ERROR_MODE would allow crash dialogs')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetErrorMode.restype = ctypes.c_uint
    kernel.SetErrorMode.argtypes = [ctypes.c_uint]
    kernel.SetErrorMode.restype = ctypes.c_uint
    previous = kernel.GetErrorMode()
    kernel.SetErrorMode(previous | 0x8003)
    try:
        return subprocess.Popen(*args, **kwargs)
    finally:
        kernel.SetErrorMode(previous)


def validate_result(result: dict) -> None:
    if result.get('exit_code', 0) != 0:
        raise ValueError('Native Mail process did not exit cleanly')
    tests = result.get('tests')
    if (result.get('supported') is not True or not isinstance(tests, list) or not tests
            or any(not isinstance(t, dict) or not t.get('name') or t.get('passed') is not True for t in tests)):
        raise ValueError('Native Mail input assertions failed or absent')
    names = [test['name'] for test in tests]
    required = (*UI_ASSERTIONS, 'scratch objects released before native shutdown') if result.get('case') in ('ui', 'all') else REQUIRED_ASSERTIONS
    if len(names) != len(set(names)) or not set(required).issubset(names):
        raise ValueError('Native Mail result is incomplete or contains duplicate assertions')
    if result.get('interactive') is True and not set(INTERACTIVE_ASSERTIONS).issubset(names):
        raise ValueError('Interactive Mail result is missing real keyboard evidence')
    if result.get('factory') is True and not set(FACTORY_ASSERTIONS).issubset(names):
        raise ValueError('Factory Mail result is missing native production evidence')
    if result.get('editor') is True and not set(EDITOR_ASSERTIONS).issubset(names):
        raise ValueError('Editor Mail result is missing native dispatch evidence')
    if result.get('case') in ('bridge', 'all') and not set(BRIDGE_ASSERTIONS).issubset(names):
        raise ValueError('Native bridge result is missing acceptance evidence')


def validate_reopened(reopened: dict[str, str], transformed: dict[str, str]) -> None:
    for entry, expected in transformed.items():
        if entry not in reopened:
            raise ValueError('Compiled Mail hook missing: ' + entry)
        calls = set(re.findall(r'\bwf_mail_\w+(?=\s*\()', expected))
        for call in calls:
            if not re.search(r'\b' + call + r'\s*\(', reopened[entry]):
                raise ValueError('Compiled Mail call missing: ' + entry + '.' + call)


def compare_factory_results(closed: dict, opened: dict) -> dict:
    for result in (closed, opened):
        validate_result(result)
    if closed.get('factory_mode') != 'closed' or opened.get('factory_mode') != 'open':
        raise ValueError('Factory comparison requires separate closed/open runs')
    a, b = closed['factory_closed'], opened['factory_open']
    comparisons = (
        a['won'] is True and a['words'] == 10,
        b['won'] is True and b['words'] == 10,
        0 < a['ticks'] == b['ticks'] and 0 < a['frames'] == b['frames'],
        json.loads(a['journal']) == json.loads(b['journal']),
        b['kept_open'] is True,
        b['idempotent'] is True,
    )
    tests = [test for test in closed['tests'] if test['name'] in REQUIRED_ASSERTIONS]
    tests += [{'name': name, 'passed': passed} for name, passed in zip(FACTORY_ASSERTIONS, comparisons)]
    return {'supported': all(test['passed'] for test in tests), 'tests': tests,
            'factory': True, 'factory_closed': a, 'factory_open': b,
            'gate_passed': False, 'manual_input_validated': False, 'installed': False}


def build_probe(cli: Path, original: Path, runtime: Path, output: Path, *, case: str = 'input', interactive: bool = False, factory: bool = False, editor: bool = False, live_bridge: bool = False, _factory_mode: str | None = None) -> dict:
    if case not in ('input', 'bridge', 'ui', 'all'):
        raise ValueError('Unsupported native Mail probe case')
    if case != 'input' and (factory or editor or interactive or _factory_mode):
        raise ValueError('Bridge acceptance runs separately from input fixtures')
    if live_bridge and (case != 'all' or os.name != 'nt'):
        raise ValueError('Live bridge acceptance requires the all case on the Windows scratch host')
    if factory and interactive:
        raise ValueError('Factory comparison uses deterministic input; run interactive separately')
    if editor and (factory or interactive or _factory_mode):
        raise ValueError('Editor case runs separately from factory and interactive cases')
    if _factory_mode not in (None, 'closed', 'open') or (_factory_mode and (factory or interactive)):
        raise ValueError('Invalid internal factory mode')
    validate_probe_paths(cli, original, runtime, output)
    verify_original(original.read_bytes())
    executable = discover_executable(runtime)
    output.mkdir(exist_ok=False)
    cli, original, runtime, output = (p.resolve() for p in (cli, original, runtime, output))
    if factory:
        closed = build_probe(cli, original, runtime, output / 'closed', _factory_mode='closed')
        opened = build_probe(cli, original, runtime, output / 'open', _factory_mode='open')
        result = compare_factory_results(closed, opened)
        result['original_sha256'] = ORIGINAL_SHA256
        result['runs'] = {'closed': closed['nonce'], 'open': opened['nonce']}
        (output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        validate_result(result)
        return result
    run_factory = _factory_mode is not None
    def run(*args):
        completed = subprocess.run([str(cli), *map(str, args)], cwd=output, capture_output=True, text=True, timeout=180)
        with (output / 'build.log').open('a', encoding='utf-8') as stream:
            stream.write(completed.stdout + completed.stderr)
        if completed.returncode:
            raise RuntimeError('Native CLI failed; inspect scratch build.log')
    extra = ('gml_GlobalScript___GoogSystem',)
    entries = CODE_ENTRIES + extra + (FACTORY_ENTRIES if run_factory else EDITOR_ENTRIES if editor else ())
    code_args = [v for entry in entries for v in ('-c', entry)]
    run('dump', original, '-o', output / 'original', *code_args)
    sources = {entry: (output / 'original/CodeEntries' / (entry + '.gml')).read_text(encoding='utf-8') for entry in CODE_ENTRIES}
    fixture = (ROOT / 'tools/native_mail_acceptance.gml').read_text(encoding='utf-8')
    helpers, harness = fixture.split('// PROBE HARNESS BOUNDARY\n', 1)
    if case in ('bridge', 'ui', 'all'):
        helpers += '\n' + (ROOT / 'tools/native_mail_bridge.gml').read_text(encoding='utf-8')
        bridge_stubs, bridge_tests = (ROOT / 'tools/native_mail_bridge_acceptance.gml').read_text(encoding='utf-8').split('function wf_bridge_snapshot()', 1)
        harness += '\nfunction wf_bridge_snapshot()' + bridge_tests
        if case == 'bridge':
            harness = harness.replace('wf_run_tests();', 'wf_run_tests(); wf_bridge_tests();')
        else:
            helpers = production_mail_helpers(ROOT)
            harness += '\n' + (ROOT / 'tools/native_mail_ui_acceptance.gml').read_text(encoding='utf-8')
            harness = harness.replace('wf_run_tests();', 'wf_bridge_tests(); wf_ui_tests();' if case == 'all' else 'wf_ui_tests();')
        # Production access helpers are global scripts, not methods bound to the
        # scratch host. oInput polls before the host Step and needs the same scope.
        helpers += '\n' + bridge_stubs
    if live_bridge:
        from tools.mail_live_peer import ROOM
        harness += '\n' + (ROOT / 'tools/native_mail_live_acceptance.gml').read_text(encoding='utf-8').replace('LIVE_ROOM_TOKEN', ROOM)
        harness = harness.replace('wf_frames=0;', 'wf_frames=0; wf_live_phase=0; wf_live_done=false;')
        harness = harness.replace('wf_frames++;', 'wf_frames++; if(wf_frames>2) wf_mail_live_step();')
        harness = harness.replace('wf_frames>8 &&', 'wf_frames>8 && wf_live_done &&')
    factory_sources = {}
    if run_factory:
        factory_sources = {entry: (output / 'original/CodeEntries' / (entry + '.gml')).read_text(encoding='utf-8') for entry in FACTORY_ENTRIES}
        harness += '\n' + (ROOT / 'tools/native_mail_factory_acceptance.gml').read_text(encoding='utf-8')
    if editor:
        harness += '\n' + (ROOT / 'tools/native_mail_editor_acceptance.gml').read_text(encoding='utf-8')
        harness = harness.replace('wf_run_tests();', 'wf_run_tests(); wf_editor_tests();')
    transformed = transform_mail_sources(sources, helpers + ('\n' + reader_helpers() if case in ('input','bridge') else ''))
    imports = output / 'imports'
    imports.mkdir()
    def stage(entry, text):
        (imports / (entry + '.gml')).write_text(text, encoding='utf-8')
    for entry, source in transformed.items():
        stage(entry, source)
    # Compile/reopen EVERY actual hook before any fixture stubs replace objects.
    # This binary is never executed or installed; the smaller runtime below is
    # deliberately separate and cannot masquerade as a populated-factory test.
    hook_script = output / 'compile-hooks.csx'
    hook_script.write_text('using System.IO;\n'
        'UndertaleModLib.Compiler.CodeImportGroup group = new(Data) { MainThreadAction = MainThreadAction };\n'
        f'foreach(var file in Directory.GetFiles({json.dumps(str(imports))}, "*.gml")) group.QueueReplace(Path.GetFileNameWithoutExtension(file),File.ReadAllText(file));\n'
        'group.Import();\n', encoding='utf-8')
    run('load', original, '-s', hook_script, '-o', output / 'hooks-only.win')
    run('dump', output / 'hooks-only.win', '-o', output / 'hooks-reopened', *code_args)
    reopened = {entry: (output / 'hooks-reopened/CodeEntries' / (entry + '.gml')).read_text(encoding='utf-8') for entry in CODE_ENTRIES}
    validate_reopened(reopened, transformed)
    nonce = uuid.uuid4().hex
    # All full original objects are disabled below. Restore only the consumers
    # under test and an authored host. No original room/save/network lifecycle.
    stage('gml_GlobalScript___GoogSystem', 'exit;\n' + (output / 'original/CodeEntries/gml_GlobalScript___GoogSystem.gml').read_text(encoding='utf-8'))
    stage('gml_Object_oPersistent_Create_0', harness.replace('NATIVE_NONCE', nonce).replace('PROBE_INTERACTIVE', 'true' if interactive else 'false').replace('PROBE_FACTORY_OPEN', 'true' if _factory_mode == 'open' else 'false').replace('PROBE_FACTORY', 'true' if run_factory else 'false'))
    stage('gml_Object_oPersistent_Step_0', 'wf_probe_frame();')
    stage('gml_Object_oPersistent_Alarm_0', 'wf_finish_report();')
    stage('gml_Object_oCursor_Create_0', '')
    stage('gml_Object_oCursor_Draw_75', 'wf_mail_probe_draw();')
    stage('gml_Object_oInput_Create_0', 'pressed={}; held={}; released={}; all_input_names=[65]; locks=ds_priority_create(); depth_pri=ds_priority_create(); full_keyboard_string=""; keyboard_string_index=1; function registerEvent() {}')
    stage('gml_Object_oInput_Step_1', 'wf_mail_frame(oPersistent.wf_ev());' if run_factory or editor else 'wf_mail_probe_step();')
    stage('gml_Object_oInput_Other_4', 'wf_mail_reset();')
    stage('gml_Object_oInput_CleanUp_0', 'wf_mail_reset(); ds_priority_destroy(locks); ds_priority_destroy(depth_pri);')
    # Do not restore unrelated events among the raw-reader transform set.
    allowed_objects = {'gml_Object_oPersistent_Create_0', 'gml_Object_oPersistent_Step_0', 'gml_Object_oPersistent_Alarm_0', 'gml_Object_oCursor_Create_0', 'gml_Object_oCursor_Draw_75', 'gml_Object_oInput_Create_0', 'gml_Object_oInput_Step_1', 'gml_Object_oInput_Other_4', 'gml_Object_oInput_CleanUp_0'}
    if run_factory:
        for entry, source in factory_imports(factory_sources).items():
            stage(entry, source)
            if entry.startswith('gml_Object_'):
                allowed_objects.add(entry)
    if editor:
        create = (output / 'original/CodeEntries/gml_Object_oControl_Create_0.gml').read_text(encoding='utf-8')
        factory_sources['gml_Object_oControl_Create_0'] = create
        editor_fixture = (ROOT / 'tools/native_mail_editor_control.gml').read_text(encoding='utf-8')
        for entry, source in editor_imports(create, transformed['gml_Object_oControl_Step_0'], editor_fixture).items():
            stage(entry, source)
            allowed_objects.add(entry)
    script = output / 'compile.csx'
    script.write_text('using System.IO;\nusing System.Collections.Generic;\n'
        'UndertaleModLib.Compiler.CodeImportGroup group = new(Data) { MainThreadAction = MainThreadAction };\n'
        'foreach(var code in Data.Code) if(code.ParentEntry==null && code.Name.Content.StartsWith("gml_Object_")) group.QueueReplace(code.Name.Content, "");\n'
        f'var allowed=new HashSet<string>(new string[]{{{",".join(json.dumps(n) for n in sorted(allowed_objects))}}});\n'
        f'foreach(var file in Directory.GetFiles({json.dumps(str(imports))}, "*.gml")) {{ var name=Path.GetFileNameWithoutExtension(file); if(!name.StartsWith("gml_Object_") || allowed.Contains(name)) group.QueueReplace(name,File.ReadAllText(file)); }}\n'
        'group.Import();\nforeach(var extension in Data.Extensions) foreach(var file in extension.Files) { file.InitScript=Data.Strings.MakeString(""); file.CleanupScript=Data.Strings.MakeString(""); }\n'
        f'Data.GeneralInfo.Name.Content="wf_mail_probe_{nonce}";\n', encoding='utf-8')
    game = output / 'game'
    game.mkdir()
    for asset in runtime.iterdir():
        if asset.is_file() and asset.suffix.lower() in {'.exe', '.dll', '.ogg', '.ttf', '.ini', '.json', '.data'}:
            _reject_links(asset)
            shutil.copy2(asset, game / asset.name)
    (game / 'steam_appid.txt').write_text('2072840\n', encoding='ascii')
    run('load', original, '-s', script, '-o', game / 'data.win')
    run('info', game / 'data.win')
    run('dump', game / 'data.win', '-o', output / 'reopened', '-c', 'gml_GlobalScript_checkInputFuncs', '-c', 'gml_GlobalScript_inputClickableUpdateState')
    startup = None
    if os.name == 'nt' and not interactive:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    metadata = {'original_sha256': ORIGINAL_SHA256, 'hooks': list(CODE_ENTRIES), 'input_hashes': {k: hashlib.sha256(v.encode()).hexdigest() for k,v in (sources | factory_sources).items()}, 'installed': False, 'case': case, 'interactive': interactive, 'editor': editor, 'factory_mode': _factory_mode, 'nonce': nonce}
    (output / 'run.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    peer_context = nullcontext()
    if live_bridge:
        from tools.mail_live_peer import LiveMailPeer
        peer_context = LiveMailPeer(Path(os.environ['LOCALAPPDATA']) / ('wf_mail_probe_' + nonce) / 'mods/word factori archipelago/archipelago_mail')
    with peer_context as peer, (output / 'runtime.log').open('w', encoding='utf-8') as log:
        process = launch_probe_process([str(game / executable.name), '-debugoutput', str(output / 'native-error.log')], cwd=game, stdout=log, stderr=log, startupinfo=startup)
        try:
            code = process.wait(timeout=600 if interactive else 40)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
            raise RuntimeError('Native Mail probe timed out; scratch evidence preserved')
        if live_bridge:
            peer.verify()
    prefix = 'WF_MAIL_RESULT:' + nonce + ':'
    metadata['exit_code'] = code
    (output / 'run.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    lines = [line[len(prefix):] for line in (output / 'runtime.log').read_text(encoding='utf-8').splitlines() if line.startswith(prefix)]
    if code:
        raise RuntimeError(f'Native Mail process exited with {code}; inspect scratch runtime.log')
    if len(lines) != 1:
        raise RuntimeError('Missing fresh native result; inspect scratch runtime.log')
    result = json.loads(lines[0])
    result.update(metadata)
    if live_bridge:
        expected = {'live bridge displays Python authoritative target', 'live bridge submits native chat',
                    'live bridge receives Python acknowledgment'}
        if not expected.issubset({row['name'] for row in result['tests'] if row['passed']}):
            raise ValueError('Live bridge acceptance is incomplete')
        result['live_bridge'] = True
    (output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    validate_result(result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('cli', 'original', 'runtime', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--case', choices=('input', 'bridge', 'ui', 'all'), default='input')
    parser.add_argument('--interactive', action='store_true', help='Visible scratch UI, F10 ends the inspection')
    parser.add_argument('--factory', action='store_true', help='Compare isolated native production with Mail closed/open')
    parser.add_argument('--editor', action='store_true', help='Exercise native editor Step movement, eraser and tick dispatch')
    parser.add_argument('--live-bridge', action='store_true', help='Run a real Python transport peer against the isolated native panel')
    args = parser.parse_args()
    print(json.dumps(build_probe(args.cli, args.original, args.runtime, args.output, case=args.case, interactive=args.interactive, factory=args.factory, editor=args.editor, live_bridge=args.live_bridge), indent=2))
