"""Scratch-only staging of verified native editor paths, never release code."""
import re

from tools.run_type_word_native_probe import extract_function

EDITOR_ENTRIES = ('gml_Object_oControl_Create_0',)
EDITOR_ASSERTIONS = (
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


def editor_imports(create: str, step: str, fixture: str) -> dict[str, str]:
    # All source comes from the original whose entire binary hash was verified.
    # The fixture invokes the entire Step body as a method at controlled points,
    # with original automatic events disabled. Only external UI boundaries are
    # replaced: hover lookup, movement target, and the fixed rotation widget.
    body, separator, enum = step.partition('\nenum UnknownEnum\n')
    if not separator or not enum.rstrip().endswith('}'):
        raise ValueError('Native editor enum boundary changed')
    if body.count('(100308).image_index') != 3:
        raise ValueError('Native rotation widget references changed')
    body = body.replace('(100308).image_index', 'wf_rotation_widget.image_index')
    body = re.sub(r'UnknownEnum\.Value_(\d+)', r'\1', body)
    control = fixture + '\n'
    for name in ('move_held_object', 'resolve_move', 'delete_components_at_mouse'):
        control += extract_function(create, name) + '\n'
    control += 'function wf_editor_step() {\n' + body + '\n}\n'
    return {'gml_Object_oControl_Create_0': control}
