# Machine-only progression: local acceptance, 9 September 2026

## Scope

1.4.0 new rooms use explicit machine-only progression model IDs. I remains
available; machine routes, lab/challenge caps, stable AP IDs and native page
thresholds remain intact. Five World Access pool entries become stickers.
Old valid canonical, shuffled, and enhanced contracts preserve their tiers.
No running game, installed client, server, mod, or save was changed.

## Verification

- Seven focused regressions cover new-region access, I availability, pools,
  M's required Merger3 and route limits, old-room reconnects, digest tampering,
  and machine-only sphere replay. Five behavior tests failed before implementation;
  the replay probe also rejected an otherwise reachable J until updated.
- Full unittest suite: **386 tests passed**, 54.248 seconds.
- Actual AP **0.6.7**: **24 generated rooms passed**, covering supported/enhanced,
  Core/Discovery, count/final goals, and seeds 24000–24002.
- Each room's generated model, entire placement pool (no World Access), JSON
  client reconstruction, I availability, pre-goal sphere replay and Victory
  spoiler were checked. Layouts varied across seeds; stable ID sets did not.
- Independent read-only review found no critical/important defects. Mode-specific
  tutorial wording was clarified. The general matrix tool does not itself check
  model/pool identity; the dedicated local probe checked both for every room.
- Release verifier passed source parity, manifest/JSON integrity, fresh recipe
  derivation, and proprietary/user-data exclusion checks. Enhanced package hashes
  and complete manifest membership were independently checked after building.

Local evidence lives under the project mirror's
`artifacts/machine-only-generation-20260909/results.json`; the rerunnable probe
is `probe-tools/machine-only-20260909/verify.py`. These are local development
artifacts, not installed game data or shipped proprietary files.

## Artifact

`word-factori-enhanced-1.4.0-machine-only-20260909.zip`

SHA-256: `4810aa78279d0d070295da96e186012cc097ab7fe3e6f5fa5a2d0dc12b81cc63`

The native r3 patch is unchanged. This package also contains the previously
prepared Chat-to-Items focus correction. Neither change has been installed
over the current live room. Use a new room and empty mod save for machine-only
play; do not treat the old room as upgraded. No public release or push was made.

## Remaining live acceptance

Confirm machine-only levels, lab restrictions, AP Mail tab focus, and item refresh
in the normal game UI. The in-game missing-machine notice remains a separate UI
task, not a delivered part of this progression update. With fewer progression
items, a minimal spoiler can have fewer spheres; completed-level requirements and
normal factory building still apply. Judge pacing in the fresh playthrough.
