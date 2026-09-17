"""Private probe staging; native bodies are read from the verified local original.

Only the production methods run. No original save/network/startup object events
are restored. This is not evidence for original placement-event ordering.
"""
import re

from tools.run_type_word_native_probe import extract_function

FACTORY_ENTRIES = (
    'gml_GlobalScript_LevelFuncs', 'gml_GlobalScript_PersistentData',
    'gml_Object_oControl_Create_0', 'gml_Object_oFinalWordMain_Create_0',
)


def factory_imports(sources: dict[str, str]) -> dict[str, str]:
    if set(sources) != set(FACTORY_ENTRIES):
        raise ValueError('Missing or unexpected native factory source')

    def native(entry: str, name: str) -> str:
        return re.sub(r'UnknownEnum\.Value_(\d+)', r'\1', extract_function(sources[entry], name))

    control = 'cycle_count=0; floater_count=0; buildings=[]; win_stats=undefined; win_already_triggered=false;\n'
    control += native('gml_Object_oControl_Create_0', 'doTick') + '\n'
    control += native('gml_Object_oControl_Create_0', 'try_win_condition')
    for call in ('tryStampUnlockAnim', 'google_analytics_screenview'):
        control = re.sub(r'\b' + call + r'\(', 'oPersistent.wf_factory_external(', control)
    level = sources['gml_GlobalScript_LevelFuncs']
    for call in ('analyticsEvent', 'doHTTPRequest', 'AWSLog'):
        level = re.sub(r'\b' + call + r'\(', 'wf_factory_external(', level)
    persistent = re.sub(r'\bspawnNotification\(', 'oPersistent.wf_factory_external(',
                        sources['gml_GlobalScript_PersistentData'])
    return {
        'gml_GlobalScript_LevelFuncs': level,
        'gml_GlobalScript_PersistentData': persistent,
        'gml_Object_oControl_Create_0': control,
        'gml_Object_oFinalWordMain_Create_0': 'counts=[0,0]; num_words_completed=0; tile_width=88; icon=-1;\n' + native('gml_Object_oFinalWordMain_Create_0', 'produce'),
        'gml_Object_oIFactory_Create_0': 'function produce() { building.produce(); }',
        'gml_Object_oIdentity_Create_0': 'current_save_slot=0; save_data={slots:{}}; variable_struct_set(save_data.slots,"0",{}); config={cloud_client:{setAchievement:function() { oPersistent.wf_factory_external(); }}}; function syncToCloud() { oPersistent.wf_factory_external(); } function getExtendedSaveField(name) { return []; }',
    }
