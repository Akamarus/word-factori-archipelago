"""Development-only Mail hook transforms for the verified original build.

No game source is shipped here. Hashes identify locally extracted hook inputs.
The probe is not wired into the production patch until its input gate passes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

SOURCE_HASHES = json.loads(Path(__file__).with_name('mail_hook_hashes.json').read_text())
CODE_ENTRIES = tuple(SOURCE_HASHES)
READERS = tuple(
    name + suffix for name in ('keyboard_check', 'mouse_check_button', 'device_mouse_check_button')
    for suffix in ('', '_pressed', '_released')
) + ('mouse_wheel_up', 'mouse_wheel_down')
# Consume quoted/comment tokens before considering identifiers. Never rewrite UI text.
TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|\b[A-Za-z_]\w*\b')
PROBE_EXTERNAL = re.compile(r'(?:steam_\w+|http_\w+|network_\w+|external_\w+|url_open\w*|execute_program|execute_shell)\Z')


def isolate_probe_external_calls(source: str) -> str:
    """Developer fixture only: neutralize external APIs, including references.

    This is deliberately NOT used by production transforms. The full probe also
    audits compiled function references and disables extension entry points.
    Interpolated strings are refused when the lexer cannot prove containment.
    """
    def replace(match: re.Match) -> str:
        token = match[0]
        if token.startswith(('"', "'")) and match.start() and source[match.start()-1] == '$':
            if any(PROBE_EXTERNAL.fullmatch(name) for name in re.findall(r'\b\w+\b', token)):
                raise ValueError('External API in an interpolated string needs explicit audit')
        return 'wf_probe_external_blocked' if PROBE_EXTERNAL.fullmatch(token) else token
    return TOKENS.sub(replace, source)


def redirect_readers(source: str) -> str:
    def replace(match: re.Match) -> str:
        token = match[0]
        if token in READERS and source[match.end():].lstrip().startswith('('):
            return 'wf_mail_' + token
        return token
    return TOKENS.sub(replace, source)


def guard_function(source: str, name: str, action: str) -> str:
    matches = list(re.finditer(r'\bfunction ' + re.escape(name) + r'\([^)]*\)\s*\{', source))
    if len(matches) != 1 or 'wf_mail_' in source:
        raise ValueError('Missing, ambiguous or already patched Mail function: ' + name)
    end = matches[0].end()
    return source[:end] + '\nif (wf_mail_blocks_input()) { ' + action + ' }\n' + source[end:]


def transform_mail_sources(sources: dict[str, str], helpers: str) -> dict[str, str]:
    if set(sources) != set(SOURCE_HASHES):
        raise ValueError('Missing or unexpected Mail hooks')
    for entry, source in sources.items():
        if hashlib.sha256(source.encode('utf-8')).hexdigest() != SOURCE_HASHES[entry]:
            raise ValueError('Changed, ambiguous or already patched Mail hook: ' + entry)
    result = {entry: redirect_readers(source) for entry, source in sources.items()}
    entry = 'gml_GlobalScript_checkInputFuncs'
    source = sources[entry]
    # Guard each function against the original, then combine disjoint insertions.
    for name in ('checkPressed', 'checkHeld', 'checkReleased', 'mousePressed', 'mouseHeld', 'mouseReleased', 'keyboardString'):
        action = 'return "";' if name == 'keyboardString' else 'return false;'
        guard_function(sources[entry], name, action)  # Validate uniqueness before insertion.
        marker = re.search(r'\bfunction ' + name + r'\([^)]*\)\s*\{', source)
        end = marker.end()
        source = source[:end] + '\nif (wf_mail_blocks_input()) { ' + action + ' }\n' + source[end:]
    result[entry] = source + '\n' + helpers
    entry = 'gml_GlobalScript_inputClickableUpdateState'
    result[entry] = guard_function(sources[entry], 'inputClickableUpdateState',
        'pressed=false; held=false; released=false; hover=false; hold_started_with_press=false; return;')
    result['gml_Object_oInput_Step_1'] = 'wf_mail_probe_step();\n' + result['gml_Object_oInput_Step_1']
    result['gml_Object_oCursor_Draw_75'] = 'wf_mail_probe_draw();\n' + result['gml_Object_oCursor_Draw_75']
    for entry in ('gml_Object_oInput_Other_4', 'gml_Object_oInput_CleanUp_0'):
        result[entry] = 'wf_mail_reset();\n' + result[entry]
    # These consumers read the input system's text buffer without its access check.
    for entry in ('gml_Object_oInputBox_Step_0', 'gml_Object_oConsole_Step_0'):
        result[entry] = 'if (wf_mail_blocks_input()) { keyboardStringClear(); exit; }\n' + result[entry]
    # Existing drag/selection modes and the eraser latch do not need fresh raw
    # input to mutate the factory. Guard the editor dispatcher, not production.
    entry = 'gml_Object_oControl_Step_0'
    result[entry] = 'if (wf_mail_editor_should_yield()) { physics_pause_enable(true); exit; }\n' + result[entry]
    return result


def reader_helpers() -> str:
    """Built-ins remain authoritative when Mail does not own the input."""
    functions = []
    for name in READERS:
        args = 'a, b' if name.startswith('device_') else '' if name.startswith('mouse_wheel') else 'a'
        functions.append(f'function wf_mail_{name}({args}) {{ if(wf_mail_blocks_input()) return false; return {name}({args}); }}')
    return '\n'.join(functions)


def production_mail_helpers(root: Path) -> str:
    return '\n'.join((root / 'tools' / name).read_text(encoding='utf-8')
                     for name in ('native_mail_bridge.gml', 'native_mail_input.gml',
                                  'native_mail_ui.gml')) + '\n' + reader_helpers()
