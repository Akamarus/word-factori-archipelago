# Release-candidate acceptance — 2026-09-27

Status: **local candidate, not published; not stable**.
The release number remains 1.6.0 until publication preparation. Identify this
candidate by its commit and hashes, not the version label alone.

## Candidate identity

| Artifact | SHA-256 / identity |
| --- | --- |
| Source | test/connected-multiworld, e3ba89c525adda86196c906adfb37ad93452828a (final implementation; later commits record evidence only) |
| APWorld | 45df9c95209cb65c87c5e81e2a8d2ea408479b0aa61f7b11dc30011c472ccd18 |
| Player ZIP | dda229cd0b4ab0964f6013531ba274434b8a3b599b129a5fcdb567e2b32f861d |
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
- Final full verification: 795 tests run, 790 passed, five explicit skips (two platform
  cases, two opt-in connected cases, one opt-in YAML generation).
  All 12 opt-in/CI/example tests passed separately, including a real connected room,
  deliberate premature-victory rejection and real generation of both shipped YAML
  examples. Source/package integrity passed.
- Final post-review seeds 160929 and 160930: **Pass**, each with 263/263 checks,
  2/2 server-confirmed goals, 20 tracker comparisons and nine replay rounds.
  Cross-player deliveries: 54/52; page-gate observations: 108/122. Both reports
  identify the final APWorld hash above. These are not native game playthroughs.
- New native UI/bridge acceptance assertions: authored, execution Pending.
- Hosted Windows/Ubuntu CI: Pending authorized push.

The final independent review found two Important presentation defects. Regression
tests reproduced both, then passed after fixing Linux publication following failed
scans and preventing word readiness from surviving a room/generation change.
An additional guard rejects publication from a delayed old-generation scan.

One Minor is deferred: a malformed Type-a-Word journal with valid campaign data
can show current campaign progress alongside the broad “Completion scanning paused”
message. Word checks are safely withheld; campaign scanning remains valid. Narrow
that recovery wording in a later polish pass. Native font/DPI/input behavior and
the extreme-text 2,500-line rendering limit still require actual UI acceptance.

Local verification logs, the review ledger and both complete seed reports are
retained in the project workspace at `release-polish-20260927/verification-final/`.
They contain synthetic test data, not evidence from the installed game. Rerun the
commands below to reproduce results; hosted evidence will be attached after a push.

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
