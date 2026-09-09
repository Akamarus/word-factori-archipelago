# Nonlinear Progression Acceptance Matrix

The 2026-09-09 correction supersedes the September 2 four-of-six beta evidence.
That earlier generator passed its own incorrect model; the live game exposed
the tutorial restriction. Old beta rooms must be regenerated. Automated checks
below do not certify live gameplay.

| Behavior | Automated evidence | Live acceptance |
|---|---|---|
| Tutorial remains I, C, V, L, O, A in both level sets | Layout tests and native-order validation | Pending corrected-build playthrough |
| Tutorial levels require their immediate predecessor | Access-rule and independent sphere-replay regressions | Pending |
| Page two requires all six tutorial levels | Boundary and tutorial-gap regressions | Pending |
| Page three onward uses four of the previous six, with independent siblings | Access-rule tests and sphere replay | Pending |
| Later page membership/order varies; IDs do not | 200 distinct real AP seeds, repeatability and canonical projection checks | Pending |
| Missing/tampered layout and invalid beta contracts are rejected | Layout, identity and client tests | Pending |
| Correct save is selected using slot zero's previous_save pointer | Multi-slot, stale-flag and selection-menu fixtures | Pending |
| Duplicate items/checks, reconnect and both goals remain idempotent | Bridge, client lifecycle and goal tests | Pending |
| Enhanced AP-only menu and factory-entry hooks compile | Exact-hash isolated build, reopen and hook inspection | Pending; not installed or shipped |

## Corrected model

Supported rooms use `tutorial_six_then_four_v1`; shuffled layouts use
`balanced_pages_v2`. Slot identity includes supported integration mode and
separate tutorial (6) and later-page (4) thresholds, all covered by the digest.
The unpublished `four_of_six_v1` contract is rejected with regeneration guidance.
Legacy 1.2.x rooms keep their canonical mapping.

The tutorial is sequential. Later full pages retain at least three machine
profiles. Reflection, Merger3 and Merger4 are unavoidable for at most three
checks per page; at most one later Core page may have four Rotation-dependent
checks. Challenges stay outside the first two pages and Pitchfork stays on the
last page. AP fill requests local-early Merger2 and Rotation.

The independent replay counts recipe- and tier-reachable locations in native
order. It stops the tutorial at the first missing capability, requires all six
before page two, then uses four-of-six gates. Spoiler checks are validated
against that state, and already-used checks are removed from the available
choice count. The existing minimum number of broad pre-goal states
(`min(3, total pre-goal states)`) was retained.

## Real AP 0.6.7 generation — 2026-09-09

An isolated copy of the installed AP 0.6.7 runtime loaded the newly built
APWorld; the installed APWorld and game saves were not modified.

| Level set / goal | Shuffled seeds | Result | Fixed-layout seed |
|---|---|---|---|
| Core / Campaign Count | 19000–19049 | 50/50 pass | 19201 pass |
| Core / Final Factory | 19050–19099 | 50/50 pass | 19201 pass |
| Discovery / Campaign Count | 19100–19149 | 50/50 pass | 19201 pass |
| Discovery / Final Factory | 19150–19199 | 50/50 pass | 19201 pass |

All 204 cases passed generation, requested identity, exact canonical
key/name/ID projection and progression replay. This is 200 distinct shuffled
seeds across the four cases, not 200 seeds per case. These are solo-room tests;
a mixed-game multiworld is still a live acceptance case.

Discovery Count seed 13000 reproduced layout digest
`28e1521bea2e9cdde22cf36417ebd34a170d497bcc8db6fa94af334de0f19ef9`.
Seed 13001 changed it to
`33e1c1a85afdb7f3e5d83d0862c3d5683e2f4ab3751f36a51454375e0a664389`
while preserving all 40 stable keys and AP IDs.

Local per-case evidence, the four-worker runner and the combined report are
under `tests/output-native-20260909/`. The combined report is
`completed-evidence.json`. The APWorld used for generation had SHA-256
`4feccdb2f2db0b9fa2a15aea9ecbd0d6d6f0d53eda1d0591d008221ec29fbbf4`;
subsequent changes concern save parsing, client validation and documentation,
not world generation rules.

## Prepared supported-mode playthrough

- AP version: 0.6.7; seed: 19200; player: `WF_Live_Discovery_Count_19200`.
- Level set: Discovery Labs, 40 locations; goal: 25 campaign checks.
- Room archive: `tests/output-native-20260909/word-factori-ap067-live-refiqevy/output/AP_44962264437902995202.zip`.
- Player YAML: same room directory, `players/player.yaml`.
- Layout digest: `115b6429e5097b1e4a2f0cebdbd2b39e393d9eb9d95bf7bf43bff20eb764c0b1`.
- First page: I, C, V, L, O, A.

Install the candidate using the normal installer, host the room archive, and
connect the client before entering an empty AP mod save. Existing saves must
not be deleted. Confirm sequential tutorial selection and a closed page-two
arrow after five checks. After A, verify every page-two button is selectable;
machine/world restrictions can still make individual puzzles temporarily
unsolvable. Finish any four page-two checks, advance, then return to a deferred
check. Check AP names, reconnect without duplicate rewards, and complete the
25-check goal.

Supported mode still requires reselecting the AP save after machine/world
unlocks. No restart-free claim is made for this package.

## Enhanced prototype boundary

See [enhanced probe notes](enhanced-patch-probe.md). The three narrow hooks
compiled into an isolated copy and were found again after reopening it.
Native execution, malformed/wrong-room runtime behavior, vanilla isolation and
live machine refresh have not yet been tested. Enhanced room generation,
client state publication, reversible player installation and binary delta
distribution are not enabled. They remain follow-on work before enhanced mode
can be offered in the normal installer.
