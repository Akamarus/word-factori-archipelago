"""Build and structurally inspect a development copy; never installs it.

Only the user's allowlisted original and an official UndertaleModTool CLI are
accepted. Extracted code stays in a temporary directory outside the repository.
No original or patched game binary belongs in a release or source control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.enhanced_hooks import ORIGINAL_SHA256, transform_sources, verify_original

CODE_ENTRIES = (
    "gml_Object_oLevelButton_Create_0",
    "gml_GlobalScript_MenuFuncs",
    "gml_GlobalScript_LevelFuncs",
)


def build_probe(cli: Path, original: Path, output: Path) -> dict:
    if output.exists() or output.with_suffix(".json").exists():
        raise ValueError("Probe output already exists; choose a fresh destination")
    verify_original(original.read_bytes())
    helper_path = ROOT / "tools/enhanced_runtime.gml"
    helpers = helper_path.read_text(encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wf-enhanced-probe-") as temporary:
        scratch = Path(temporary)

        def run(*args: object) -> None:
            result = subprocess.run([str(cli), *map(str, args)], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)

        dump = scratch / "original"
        code_args = [arg for entry in CODE_ENTRIES for arg in ("-c", entry)]
        run("dump", original, "-o", dump, *code_args)
        sources = {entry: (dump / "CodeEntries" / (entry + ".gml")).read_text(encoding="utf-8")
                   for entry in CODE_ENTRIES}
        transformed = transform_sources(sources, helpers)
        imports = scratch / "imports"
        imports.mkdir()
        for entry, source in transformed.items():
            (imports / (entry + ".gml")).write_text(source, encoding="utf-8")
        script = scratch / "compile.csx"
        script.write_text(
            "using System.IO;\n"
            "UndertaleModLib.Compiler.CodeImportGroup group = new(Data) { MainThreadAction = MainThreadAction };\n"
            "foreach (var file in Directory.GetFiles(" + json.dumps(str(imports)) + ", \"*.gml\"))\n"
            "    group.QueueReplace(Path.GetFileNameWithoutExtension(file), File.ReadAllText(file));\n"
            "group.Import();\n", encoding="utf-8")
        staged = scratch / "patched.win"
        run("load", original, "-s", script, "-o", staged)
        run("info", staged)
        inspected = scratch / "inspected"
        run("dump", staged, "-o", inspected, *code_args)
        required_calls = {
            CODE_ENTRIES[0]: "wf_ap_enabled()",
            CODE_ENTRIES[1]: "wf_ap_enabled()",
            CODE_ENTRIES[2]: "wf_ap_counts(arg0)",
        }
        for entry, call in required_calls.items():
            decompiled = (inspected / "CodeEntries" / (entry + ".gml")).read_text(encoding="utf-8")
            if call not in decompiled:
                raise RuntimeError(f"Compiled hook is missing from {entry}")
        patched = staged.read_bytes()
        # Exclusive create: even a late concurrent destination must be preserved.
        with output.open("xb") as stream:
            stream.write(patched)
        metadata = {
            "status": "Compiled and reopened; live acceptance and installer integration pending",
            "original_sha256": ORIGINAL_SHA256,
            "patched_sha256": hashlib.sha256(patched).hexdigest(),
            "helper_sha256": hashlib.sha256(helper_path.read_bytes()).hexdigest(),
            "hooks": list(CODE_ENTRIES),
            "installed": False,
        }
        output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_probe(args.cli.resolve(), args.original.resolve(), args.output.resolve()), indent=2))
