"""Build and run an isolated native completion probe; never install a patch.

All extracted native source, binaries and raw results stay in a fresh caller
selected scratch directory outside this repository and the game installation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.enhanced_hooks import ORIGINAL_SHA256, verify_original, transform_enforcement, transform_quantity_control

SAVE_NAMESPACE = "wf_ap_typeword_probe_20260915"
CODE_ENTRIES = (
    "gml_GlobalScript_LevelFuncs", "gml_GlobalScript_PersistentData",
    "gml_GlobalScript_Building", "gml_GlobalScript_UIControlFuncs",
    "gml_Object_oControl_Create_0", "gml_Object_oControl_Step_0",
    "gml_Object_oFinalWordMain_Create_0", "gml_Object_oFinalWordMain_Step_0",
    "gml_Object_oInputBox_Create_0", "gml_Object_oInputBox_Step_0",
    "gml_Object_oIdentity_Create_0", "gml_Object_oPersistent_Create_0",
    "gml_GlobalScript_LoadConfig", "gml_GlobalScript_MenuFuncs", "gml_Object_oInput_Create_0",
    "gml_GlobalScript___GoogSystem",
)
ENFORCEMENT_ENTRIES = ("gml_GlobalScript_Misc", "gml_Object_oModule_Create_0")
ENFORCEMENT_HOOKS = ["LevelFuncs.get_level_module_counts", "LevelFuncs.get_current_module_count",
                     "Building.consume", "Building.getRecipe", "Building.produce",
                     "Building.getTicksTillProduce", "Misc.getModuleRecipe"]



def validate_native_assertions(result: dict, *, enforcement: bool = False) -> None:
    if (result.get("failure") or not result.get("tests") or
            not all(test.get("passed") is True for test in result["tests"])):
        raise RuntimeError("Native assertions failed")
    if enforcement and result.get("enforcement_supported") is not True:
        raise RuntimeError("Native enforcement gate failed or is absent")


def _reject_links(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and
                getattr(part.stat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError(f"Symlink/reparse paths are unsupported: {part}")


def validate_probe_paths(cli: Path, original: Path, runtime: Path, output: Path) -> None:
    """Validate without subprocesses or filesystem writes; do not resolve links away."""
    for path in (cli, original, runtime, output):
        _reject_links(path.absolute())
    if not cli.is_file() or not original.is_file() or not runtime.is_dir():
        raise ValueError("CLI/original must be files and runtime must be a directory")
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Output must be unused beneath an existing scratch directory")
    destination = output.resolve()
    for ancestor in destination.parents:
        marker = ancestor / ".git"
        if marker.is_dir() or marker.is_file():
            raise ValueError(f"Output is inside a repository/worktree: {ancestor}")
    for protected in (runtime.resolve(), original.resolve(), original.parent.resolve(), ROOT):
        if destination == protected or destination.is_relative_to(protected) or protected.is_relative_to(destination):
            raise ValueError(f"Output overlaps protected input/repository: {protected}")


def discover_executable(runtime: Path) -> Path:
    candidates = [p for p in runtime.iterdir() if p.is_file() and p.suffix.lower() == ".exe"]
    if len(candidates) != 1:
        raise ValueError("Runtime must contain exactly one unambiguous game executable")
    _reject_links(candidates[0])
    return candidates[0]


def extract_function(source: str, name: str) -> str:
    """Copy a native function verbatim into scratch, ignoring braces in strings/comments."""
    matches = list(re.finditer(r"\bfunction " + re.escape(name) + r"\([^)]*\)\s*\{", source))
    if len(matches) != 1:
        raise ValueError(f"Expected one native function: {name}")
    match = matches[0]
    depth = 1
    token = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|[{}]')
    for item in token.finditer(source, match.end()):
        if item[0] == "{":
            depth += 1
        elif item[0] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():item.end()]
    raise ValueError(f"Unclosed native function: {name}")


def parse_native_result(log: str, nonce: str) -> dict:
    prefix = "WF_TYPEWORD_RESULT:" + nonce + ":"
    lines = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
    if len(lines) != 1:
        raise ValueError("Expected exactly one fresh native result")
    result = json.loads(lines[0])
    if not isinstance(result, dict) or result.get("schema") != 1 or not isinstance(result.get("tests"), list):
        raise ValueError("Invalid native result schema")
    return result


def build_probe(cli: Path, original: Path, runtime: Path, output: Path, *, enforcement: bool = False, quantities: bool = False) -> dict:
    if quantities and not enforcement:
        raise ValueError('Quantity acceptance requires enforcement')
    validate_probe_paths(cli, original, runtime, output)
    verify_original(original.read_bytes())  # Mandatory pre-write/pre-subprocess boundary.
    executable = discover_executable(runtime)
    output.mkdir(exist_ok=False)
    cli, original, runtime, output = (p.resolve() for p in (cli, original, runtime, output))

    def run(*args: object) -> None:
        try:
            result = subprocess.run([str(cli), *map(str, args)], cwd=output,
                                    capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired as failure:
            with (output / "build.log").open("a", encoding="utf-8") as log:
                # TimeoutExpired can carry bytes even with text=True.
                for captured in (failure.stdout, failure.stderr):
                    log.write(captured.decode("utf-8", errors="replace")
                              if isinstance(captured, bytes) else captured or "")
                log.write("\nNative CLI timed out; partial diagnostics preserved.\n")
            raise
        with (output / "build.log").open("a", encoding="utf-8") as log:
            log.write(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Native CLI failed; see {output / 'build.log'}")

    entries = CODE_ENTRIES + (ENFORCEMENT_ENTRIES if enforcement else ())
    code_args = [arg for entry in entries for arg in ("-c", entry)]
    run("dump", original, "-o", output / "original", *code_args)
    sources = {entry: (output / "original/CodeEntries" / (entry + ".gml")).read_text(encoding="utf-8")
               for entry in entries}
    hashes = {entry: hashlib.sha256(text.encode()).hexdigest() for entry, text in sources.items()}
    imports = output / "imports"
    imports.mkdir()
    def stage(entry: str, text: str) -> None:
        (imports / (entry + ".gml")).write_text(text, encoding="utf-8")
    def native(entry: str, name: str) -> str:
        # The decompiler's enum names are local to each entry; preserve literal values.
        text = extract_function(sources[entry], name)
        return re.sub(r"UnknownEnum\.Value_(\d+)", r"\1", text)

    if enforcement:
        helper = (ROOT / "tools/type_word_enforcement_probe.gml").read_text(encoding="utf-8")
        helper += "\n" + (ROOT / "tools/native_machine_access.gml").read_text(encoding="utf-8")
        transformed = transform_enforcement(sources, helper)
        for entry in ("gml_GlobalScript_Building", "gml_GlobalScript_Misc"):
            stage(entry, transformed[entry])
        # Preserve native recipe journal writes; suppress notification UI only.
        persistent = re.sub(r"\bspawnNotification\(", "oPersistent.wf_probe_external(", sources["gml_GlobalScript_PersistentData"])
        stage("gml_GlobalScript_PersistentData", persistent)
        level = transformed["gml_GlobalScript_LevelFuncs"]
    else:
        level = sources["gml_GlobalScript_LevelFuncs"]
    for call in ("analyticsEvent", "doHTTPRequest", "AWSLog"):
        level = re.sub(r"\b" + call + r"\(", "wf_probe_external(", level)
    stage("gml_GlobalScript_LevelFuncs", level)
    goog = sources["gml_GlobalScript___GoogSystem"]
    stage("gml_GlobalScript___GoogSystem", "exit;\n" + goog)
    control = "cycle_count=0; floater_count=0; buildings=[]; win_stats=undefined; win_already_triggered=false;\n"
    control += native("gml_Object_oControl_Create_0", "doTick") + "\n"
    control += native("gml_Object_oControl_Create_0", "try_win_condition")
    if enforcement:
        control = transform_quantity_control(control)
    for call in ("tryStampUnlockAnim", "google_analytics_screenview"):
        control = re.sub(r"\b" + call + r"\(", "oPersistent.wf_probe_external(", control)
    stage("gml_Object_oControl_Create_0", control)
    stage("gml_Object_oFinalWordMain_Create_0", "counts=[0,0]; num_words_completed=0; tile_width=88; icon=-1;\n" + native("gml_Object_oFinalWordMain_Create_0", "produce"))
    stage("gml_Object_oIFactory_Create_0", "function produce() { building.produce(); }")
    if enforcement:
        stage("gml_Object_oMerger2_Create_0", "function produce() { building.produce(); }")
    stage("gml_Object_oIdentity_Create_0", 'current_save_slot=0; save_data={slots:{}}; variable_struct_set(save_data.slots,"0",{}); config={cloud_client:{setAchievement:function() { oPersistent.wf_probe_external(); }}}; function syncToCloud() { oPersistent.wf_probe_external(); } function getExtendedSaveField(name) { return []; }')
    stage("gml_Object_oInput_Create_0", 'full_keyboard_string=""; keyboard_string_index=0; function registerEvent() {}')
    stage("gml_Object_oInputBox_Create_0", 'max_input=16; step=0; hover_mod=1; minimize_cooldown=0; pressed=false; text="";')
    # Keep the actual keyboard filtering, truncation and case conversion block.
    input_step = sources["gml_Object_oInputBox_Step_0"]
    stage("gml_Object_oInputBox_Step_0", input_step[input_step.index("with (oInput)"):input_step.index("interactable =")])
    harness_name = "type_word_enforcement_acceptance.gml" if enforcement else "type_word_completion_acceptance.gml"
    harness = (ROOT / "tools" / harness_name).read_text(encoding="utf-8")
    if quantities:
        harness = harness.replace('    var supported=array_all(tests,',
            (ROOT / 'tools/quantity_machine_acceptance.gml').read_text(encoding='utf-8') + '\n    var supported=array_all(tests,')
    nonce = uuid.uuid4().hex
    harness = harness.replace("NATIVE_SOURCE_HASHES", json.dumps(hashes)).replace("NATIVE_NONCE", nonce)
    harness = harness.replace("NATIVE_ENFORCEMENT_HOOKS", json.dumps(ENFORCEMENT_HOOKS))
    harness = harness.replace(SAVE_NAMESPACE + "/", SAVE_NAMESPACE + "_" + nonce + "/")
    stage("gml_Object_oPersistent_Create_0", harness)
    script = output / "compile.csx"
    script.write_text(
        'using System.IO;\nUndertaleModLib.Compiler.CodeImportGroup group = new(Data) { MainThreadAction = MainThreadAction };\n'
        '// Disable unrelated room startup, network, save and UI events in this copy.\n'
        'foreach(var code in Data.Code) { if(code.ParentEntry == null && code.Name.Content.StartsWith("gml_Object_")) group.QueueReplace(code.Name.Content, ""); }\n'
        f'foreach(var file in Directory.GetFiles({json.dumps(str(imports))}, "*.gml")) group.QueueReplace(Path.GetFileNameWithoutExtension(file), File.ReadAllText(file));\n'
        'group.Import();\nforeach(var extension in Data.Extensions) foreach(var file in extension.Files) { file.InitScript=Data.Strings.MakeString(""); file.CleanupScript=Data.Strings.MakeString(""); }\n'
        f'Data.GeneralInfo.Name.Content = "{SAVE_NAMESPACE}_{nonce}";\n', encoding="utf-8")
    game = output / "game"
    game.mkdir()
    # Only base runtime files: no installed data.win, mod tree or save is copied.
    for asset in runtime.iterdir():
        if asset.is_file() and asset.suffix.lower() in {".exe", ".dll", ".ogg", ".ttf", ".ini", ".json", ".data"}:
            _reject_links(asset)
            shutil.copy2(asset, game / asset.name)
    (game / "steam_appid.txt").write_text("2072840\n", encoding="ascii")
    run("load", original, "-s", script, "-o", game / "data.win")
    run("info", game / "data.win")
    reopen_entries = ("gml_Object_oPersistent_Create_0", "gml_Object_oControl_Create_0") + (
        ("gml_GlobalScript_LevelFuncs", "gml_GlobalScript_Building", "gml_GlobalScript_Misc") if enforcement else ())
    run("dump", game / "data.win", "-o", output / "reopened", *[arg for entry in reopen_entries for arg in ("-c", entry)])
    result_path = output / "typeword_results.json"
    startup = None
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    with (output / "runtime.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([str(game / executable.name), "-debugoutput", str(output / "native-error.log")], cwd=game, stdout=log, stderr=log,
                                   startupinfo=startup)
        try:
            exit_code = process.wait(timeout=40)
        except subprocess.TimeoutExpired:
            process.kill()  # Exact handle owned by this runner; never process-name termination.
            process.wait(timeout=10)
            raise RuntimeError(f"Native probe timed out (including possible error dialog); see {output}")
    metadata = {"output": str(output), "probe": str(game / executable.name), "results": str(result_path),
                "exit_code": exit_code, "original_sha256": ORIGINAL_SHA256,
                "patched_sha256": hashlib.sha256((game / "data.win").read_bytes()).hexdigest()}
    (output / "run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if exit_code != 0:
        raise RuntimeError(f"Native probe failed with exit {exit_code}; see {output}")
    result = parse_native_result((output / "runtime.log").read_text(encoding="utf-8"), nonce)
    with result_path.open("x", encoding="utf-8") as result_file:
        json.dump(result, result_file, indent=2)
    validate_native_assertions(result, enforcement=enforcement)
    return metadata


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("cli", "original", "runtime", "output"):
        parser.add_argument("--" + argument, type=Path, required=True)
    parser.add_argument("--enforcement", action="store_true", help="Run development-only native enforcement gate")
    parser.add_argument("--quantities", action="store_true", help="Include finite machine allowance acceptance")
    return parser


if __name__ == "__main__":
    args = argument_parser().parse_args()
    print(json.dumps(build_probe(args.cli, args.original, args.runtime, args.output, enforcement=args.enforcement, quantities=args.quantities), indent=2))
