"""Development-only transforms. Proprietary source is supplied locally, never bundled.

These hooks are not included in player releases until native live acceptance.
They modify only three exact hook sites in the allowlisted build.
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


def transform_sources(sources: dict[str, str], helpers: str) -> dict[str, str]:
    """Return locally transformed code; leave input and every other hook untouched."""
    if any("wf_ap_context" in source for source in sources.values()):
        raise ValueError("Enhanced hooks are already present")
    button = "gml_Object_oLevelButton_Create_0"
    menu = "gml_GlobalScript_MenuFuncs"
    levels = "gml_GlobalScript_LevelFuncs"
    if set(sources) != {button, menu, levels}:
        raise ValueError("Expected exactly the three verified native code entries")
    # Keep native visibility, animation, paywall, mode and secret checks intact.
    needle = "return (level_index == 0 ||"
    if sources[button].count(needle) != 1:
        raise ValueError("Expected exactly one numbered-level availability hook")
    return {
        button: sources[button].replace(needle, "return (wf_ap_enabled() || level_index == 0 ||"),
        menu: insert_function_guard(sources[menu], "getPageUnlockThresh",
                                    "    if (wf_ap_enabled()) return 4;"),
        levels: insert_function_guard(sources[levels], "get_level_module_counts",
            "    var wf_counts = wf_ap_counts(arg0);\n"
            "    if (is_struct(wf_counts)) return wf_counts;") + "\n" + helpers,
    }
