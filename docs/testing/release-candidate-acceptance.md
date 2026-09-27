# Release-candidate acceptance — 2026-09-27

Status: **local candidate, not published; not stable**.
The release number remains 1.6.0 until publication preparation. Identify this
candidate by its commit and hashes, not the version label alone.

## Candidate identity

| Artifact | SHA-256 / identity |
| --- | --- |
| Source | release-polish branch, final verification commit recorded at handoff |
| APWorld (pre-review) | 2751d7115561235eadf0c0f08adcb2f18b6097a558604804bf8b06b5b9dcd26b |
| Player ZIP (pre-review) | c22bd116b97eb1f8d90eedb424aab2fe304a74dfe67e4fa66d3d8b4a8d7fc564 |
| Native delta | cec5591dfda00e6e306b2a7c4b6eae071075bb02596ec5080a73f2c43f9fa589 |
| Patched scratch game | 2c51a6e5e67900d0aa3fb613035332e2a51f1c20afcfca85f248240bf25db46c |
| Verified original | d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978 |
| AP test source | 0.6.7, debe4cf035c7c15efe6fb95f72343af0d420c68c |

No installed game or real save was changed. Scratch native code compiled and
reopened successfully; that is not native execution or Linux gameplay evidence.
The patch round-tripped to the exact scratch binary before being packaged.

## Stable gates

Use only **Pending**, **Pass**, **Fail**, **Unsupported**. Record tester/date,
exact package hash, OS/build/Proton/compositor, steps and an evidence link for each result.
Leave unobserved cases Pending. Failures need a fix and affected-gate rerun
against a new exact package. An unsupported feature is never a passing test.

| Gate | Windows | Linux/Proton | Steps / required evidence | Date / package / evidence |
| --- | --- | --- | --- | --- |
| 1. Install lifecycle | Pending | Pending | Clean install, 1.6.0 upgrade, restore and uninstall; compare saved progress/backups before and after | Not observed |
| 2. Connected playthrough | Pending | Pending | Normal/progressive through victory; jointly exercise recipes, chosen words, remote delivery, tracker comparison and all five Mail tabs; no per-item reload | Not observed |
| 3. Recovery | Pending | Pending | Password room; client/server restart; reconnect; no lost checks or duplicate upgrades | Not observed |
| 4. Display/input | Pending | Pending | Windowed/borderless; Windows 100/125/150%; first click, Chat-to-Progress/Items, held keys, scrolling, focus/room change, long words/text | Not observed |
| 5. 60-minute performance | Pending | Pending | Worksheet below, fixed factory baseline; investigate upward memory trend or sustained slowdown | Not observed |
| 6. Exact-candidate verification | Pending | Pending | Full build/tests/integrity, two connected seeds and premature-victory rejection; hosted CI for this commit | Local evidence below; hosted CI not run |

Exclusive fullscreen: **Unsupported**. Ultrawide, mixed-DPI multi-monitor,
Flatpak and unrecorded compositor/Proton variants: **Pending**, not advertised as tested.
No unresolved crash, save-loss risk, progression block, duplicate effect or
confirmed logic error may remain at stable sign-off.

## Local automated evidence (does not complete live gates)

- Native production providers: compiled/reopened in an isolated directory; no game launch.
- Installer transactions: synthetic bytes only; Windows and portable Linux
  1.6.0 upgrade/restore tests preserve the original backup. Not a real OS install.
- Connected tests: real AP server + real clients + packaged APWorld; synthetic save
  and recipe/word journals. Test-side page model, not actual native page buttons.
  Tracker reconstruction is not Universal Tracker UI testing.
- Pre-review full verification: 790 tests, five explicit skips (two platform
  cases, two opt-in connected cases, one opt-in YAML generation).
  The opt-in connected cases passed separately; both YAML examples generated
  successfully with real AP option validation. Source/package integrity passed.
- Final post-review two-seed results: Pending final verification.
- New native UI/bridge acceptance assertions: authored, execution Pending.
- Hosted Windows/Ubuntu CI: Pending authorized push.

See [connected verification](connected-multiworld.md) for rerunnable commands.
Install development test dependencies with
`python -m pip install -r tools/requirements-connected.txt`.

## Performance worksheet (one per supported platform)

Record package hash, game build, OS, Proton/compositor if relevant, factory name,
machine count, simulation speed, display mode and resolution. Keep the same factory
and measure both idle and active states consistently. Exercise Mail and remote item
updates between samples. Record game/client memory separately.

| Time | Machine count / speed | Game memory | Client memory | FPS or frame time (idle / active) | Mail/items exercised | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Warm-up | Pending | Pending | Pending | Pending | Pending | |
| 15 min | Pending | Pending | Pending | Pending | Pending | |
| 30 min | Pending | Pending | Pending | Pending | Pending | |
| 45 min | Pending | Pending | Pending | Pending | Pending | |
| 60 min | Pending | Pending | Pending | Pending | Pending | |

Growing memory or sustained slowdown is a finding, not a pass. Bounded arrays,
fast unit tests or one short session cannot certify absence of a leak.
