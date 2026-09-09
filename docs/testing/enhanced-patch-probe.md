# Enhanced native hooks — development probe

Historical first probe. Subsequent client integration, native execution, and
installer evidence are recorded in [enhanced acceptance](enhanced-acceptance-20260909.md).

On 2026-09-09 the integration-authored hook transforms compiled successfully
against an isolated, exact-hash copy of the installed game. The resulting copy
reopened in UndertaleModTool and decompiled with all three hook calls intact.
This is structural evidence only; no patched game was launched or installed.

- Original SHA-256: `d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978`
- Probe output SHA-256: `bac75fa72ee9bc51fa2ec8a211bbc46424dbd85214fbac1fee47b6c4bd2079d9`
- Authored helper SHA-256: `48ddcdeaf514ccc80cd0d7d2428056004979ef792838084f0fe8b9cd18e148cf`
- Tool: official UndertaleModTool CLI 0.9.2.0.

## What the probe changes

The numbered-level availability expression gains an AP-only alternative,
retaining native visibility, animation, paywall, secret and mode guards. The
page threshold function returns four for enhanced AP campaigns. The factory
module-count function first tries an integration-owned runtime snapshot and
otherwise executes its existing logic.

The authored helper requires the selected AP mod folder and a loaded first-level
`wf_ap` marker containing schema `1`, mode `enhanced`, and 64-character room and
layout identities. Ordinary supported levels do not have this marker, so the
probe leaves them and the vanilla campaign on their existing rules.

The optional runtime file is `mods/word factori archipelago/archipelago_runtime.json`.
Its fields are `schema`, `mode`, `room`, `layout`, `revision` and `levels`.
Each level contains `text` and `module_counts`, using the same module names as
the normal JSON renderer. The hook checks identity, level count, target text,
known module names, integer limits and revision monotonicity within the loaded
campaign. A missing or rejected snapshot falls back to loaded native limits.
No runtime file is currently published by the supported client.

## Reproduce without changing an installation

Use an isolated copy of the recognized original and choose a fresh output path
outside the repository:

```powershell
python tools/build_enhanced_probe.py --cli C:/path/to/UndertaleModCli.exe --original C:/isolated/data.win --output C:/isolated/enhanced-probe.win
```

The builder refuses unknown originals and existing destinations. Extracted
proprietary source exists only in its temporary directory and is removed after
the run. Output is a local development binary, never a distributable artifact.
The repository contains only authored transforms, helpers and tests; the
normal player package excludes all probe tooling and binaries.

## Next exact probe

Use a separate Windows test profile, a copied game installation and an empty
AP-only save. Prepare a marked six-level development campaign with fixed room
and layout IDs. First prove every first-page level is selectable and that four
genuine completions open page two. While the game is running, atomically replace
the matching runtime snapshot with a higher revision that permits Rotation;
leave and re-enter a factory and verify both rotation tools appear. Then repeat
with missing JSON, malformed JSON, wrong room/layout, stale revision and
invalid limits; each must use the original loaded limits without a crash.
Finally switch to vanilla and verify native tutorial restrictions return.

This probe requires native gameplay and separate save isolation. Do not modify
the user's existing AP save or install this binary into Steam for that test.
Only after these behaviors pass should enhanced APWorld/client contracts and
the reversible hash-verified delta installer be completed. Enhanced mode must
never be inferred solely from a patched executable.
