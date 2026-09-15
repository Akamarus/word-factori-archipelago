"""Development-only transforms. Proprietary source is supplied locally, never bundled.

These hooks are not included in player releases until native live acceptance.
They modify exact checked hook sites in the allowlisted build.
"""
from __future__ import annotations

import hashlib
import re

ORIGINAL_SHA256 = "d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978"


def verify_original(data: bytes) -> None:
    if hashlib.sha256(data).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("Unsupported game hash; original file has not been changed")


def insert_function_guard(source: str, function: str, guard: str) -> str:
    """Insert an authored guard at a unique native function's body boundary."""
    pattern = re.compile(r"(\bfunction " + re.escape(function) + r"\([^)]*\)\s*\{)")
    if len(pattern.findall(source)) != 1:
        raise ValueError(f"Expected exactly one {function} hook")
    return pattern.sub(lambda match: match[0] + "\n" + guard, source, count=1)


def transform_enforcement(sources: dict[str, str], helper: str) -> dict[str, str]:
    """Apply exact, development-only guards; never emit extracted source into the repo."""
    if any("wf_access_active" in source for source in sources.values()):
        raise ValueError("Enforcement hooks are already present")
    result = dict(sources)
    level = insert_function_guard(result["gml_GlobalScript_LevelFuncs"], "get_level_module_counts",
                                  "    if (wf_access_active()) { var wf_counts = wf_access_entry_counts(); if (arg0 < 0) return wf_counts; var wf_level = wf_ap_counts(arg0); if (is_struct(wf_level)) return wf_level; }")
    level = insert_function_guard(level, "get_current_module_count",
                                  "    if (wf_access_quantity()) return wf_access_remaining(arg0);\n    if (wf_access_active() && wf_access_limit(arg0) == 0) return 0;")
    needle = "current_level_mode != UnknownEnum.Value_1 ||"
    if level.count(needle) != 1:
        raise ValueError("Expected exactly one native mode bypass")
    result["gml_GlobalScript_LevelFuncs"] = level.replace(
        needle, "(!wf_access_active() && current_level_mode != UnknownEnum.Value_1) ||") + "\n" + helper
    building = result["gml_GlobalScript_Building"]
    guards = {
        "consume": "if (!wf_access_allowed(module, tag)) { queued_produce_letter = undefined; exit; }",
        "getRecipe": 'if (!wf_access_allowed(module, tag)) return new Letter("?");',
        "produce": "if (!wf_access_allowed(module, tag)) { queued_produce_letter = undefined; return undefined; }",
        "getTicksTillProduce": "if (!wf_access_allowed(module, tag)) return 10000;",
    }
    for name, guard in guards.items():
        pattern = re.compile(r"(\bstatic " + name + r" = function\([^)]*\)\s*\{)")
        if len(pattern.findall(building)) != 1:
            raise ValueError(f"Expected exactly one Building.{name} hook")
        building = pattern.sub(lambda match: match[0] + "\n    " + guard, building, count=1)
    result["gml_GlobalScript_Building"] = building
    result["gml_GlobalScript_Misc"] = insert_function_guard(result["gml_GlobalScript_Misc"],
        "getModuleRecipe", '    if (!wf_access_allowed(arg0, arg1)) return new Letter("?");')
    return result


def transform_quantity_control(source: str) -> str:
    for name in ('doTick', 'try_win_condition'):
        source = insert_function_guard(source, name,
            '    wf_access_poll(); if (wf_access_quantity() && !wf_access_factory_allowed(buildings)) { wf_access_explain(buildings); return false; }')
    return source



CODE_ENTRIES = ("gml_Object_oLevelButton_Create_0", "gml_GlobalScript_MenuFuncs",
                "gml_GlobalScript_LevelFuncs", "gml_GlobalScript_Building", "gml_GlobalScript_Misc",
                "gml_Object_oControl_Create_0", "gml_Object_oControl_Step_0")


def runtime_helpers(root) -> str:
    return "\n".join((root / "tools" / name).read_text(encoding="utf-8")
                     for name in ("enhanced_runtime.gml", "native_machine_access.gml"))


def transform_sources(sources: dict[str, str], helpers: str) -> dict[str, str]:
    """Return locally transformed code; leave input and every other hook untouched."""
    if any("wf_ap_context" in source for source in sources.values()):
        raise ValueError("Enhanced hooks are already present")
    button = "gml_Object_oLevelButton_Create_0"
    menu = "gml_GlobalScript_MenuFuncs"
    if set(sources) != set(CODE_ENTRIES):
        raise ValueError("Expected exactly the seven verified native code entries")
    # Keep native visibility, animation, paywall, mode and secret checks intact.
    needle = "return (level_index == 0 ||"
    if sources[button].count(needle) != 1:
        raise ValueError("Expected exactly one numbered-level availability hook")
    result = transform_enforcement(sources, helpers)
    result.update({
        button: sources[button].replace(needle, "return (wf_ap_enabled() || level_index == 0 ||"),
        menu: insert_function_guard(sources[menu], "getPageUnlockThresh",
                                    "    if (wf_ap_enabled()) return 4;"),
    })
    result['gml_Object_oControl_Create_0'] = transform_quantity_control(sources['gml_Object_oControl_Create_0'])
    result['gml_Object_oControl_Step_0'] = 'wf_access_poll();\n' + sources['gml_Object_oControl_Step_0']
    return result
