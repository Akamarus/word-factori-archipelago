# Native Open Pages Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for inline execution, as requested in this conversation. Track tasks below.

**Goal:** Make the randomized campaign agree with verified native unlock behavior, then prototype optional enhanced behavior against an isolated game copy.

**Architecture:** The immutable layout is the shared contract for AP rules, native slots, rendering, and the client. Supported rooms use a fixed sequential tutorial followed by shuffled open pages. Enhanced patch work is isolated from the supported release until binary and live acceptance checks succeed.

**Tech Stack:** Python, unittest, Archipelago 0.6.7, GameMaker VM, UndertaleModTool for development probes only.

**Spec:** ../specs/2026-09-02-native-open-pages-and-enhanced-patch-design.md

## Execution record — 2026-09-09

- Tasks 1 and 2 implemented and verified: corrected tutorial/layout contract,
  native access rules, independent replay, client rejection, and real selection
  pointer. All 200 distinct shuffled seeds plus four fixed-layout cases passed
  real AP 0.6.7 generation and replay; repeatability passed.
- Task 3 reached a compiled, reopened isolated native probe with all three
  hooks present. It is deliberately not integrated into player installation or
  enabled in room/client contracts. Native gameplay and malformed-state checks
  remain required before that integration; no live behavior is claimed.
- Task 4 produced a supported player archive and a fresh Discovery Count room
  for seed 19200. Source parity, JSON/index integrity, fresh recipe derivation
  and proprietary-data exclusions passed. No install, save change, push or
  publication was performed.
- Pending enhanced work: native acceptance, enhanced room/client contracts,
  reversible delta installer/restore tests, and optional installation UI.

## Global Constraints

- Supported mode must work without proprietary binary changes or save writes.
- Tutorial order: I, C, V, L, O, A; thresholds 6 then 4.
- Supported progression: `tutorial_six_then_four_v1`; shuffled layout: `balanced_pages_v2`.
- Stable location IDs survive permutations; challenge levels stay outside the first two pages and Pitchfork stays on the last page.
- Reject invalid unpublished beta contracts with regeneration guidance; preserve canonical 1.2.x rooms.
- No proprietary code or assets in source control or release artifacts.
- Enhanced mode is optional, reversible, hash-verified, and not enabled for users before acceptance.
- Do not publish, push, or alter the user's live save while developing.

## Task 1: Correct supported layout and native rules

Files: `word_factori/layout.py`, `word_factori/requirements.py`, `word_factori/client_core.py`, `word_factori/mod.py`, `tests/test_layout.py`, `tests/test_core.py`, `tests/test_world_layout.py`.

Interfaces: `CampaignLayout` adds integration_mode, tutorial_page_unlock_count, later_page_unlock_count; layout_slot_data/from_slot_data round-trip them and cover them in the digest. `access_rule_for(location, locations, player)` uses native slot predecessors, retaining recipe checks.

- [ ] Add regressions: tutorial stays canonical for both sets; V with Merger2 but no reachable C is inaccessible; second page with only five tutorial levels is inaccessible; later siblings remain independent.
- [ ] Run `python -m unittest tests.test_layout tests.test_core tests.test_world_layout -q` and observe failures.
- [ ] Preserve `starter_page` order instead of sorting/shuffling it. Use predecessor singleton for native slots 1–5, six predecessors for page two, four for later pages. Migrate digest, slot data and installed identity together.
- [ ] Reject `four_of_six_v1` and mode/threshold tampering before any files or checks change. Test legacy canonical resolution and new identity round trip.
- [ ] Rerun focused tests and repair only obsolete expectations.

## Task 2: Generation and save reconciliation evidence

Files: `tools/verify_generation_matrix.py`, `tests/test_verify_generation_matrix.py`, `word_factori/save.py`, `tests/test_core.py`.

Interfaces: independent `replay_progression_choices` uses tutorial prefix reachability and six-then-four gates; generation identity requires balanced_pages_v2. Save parser retains unambiguous read-only binding and rejects ambiguous selection.

- [ ] Add replay fixtures rejecting page-two access after four tutorial completions and rejecting a tutorial level beyond a missing predecessor.
- [ ] Run replay regressions, then correct replay and expected generation identities.
- [ ] Test multiple active-looking save slots including ambiguous previous_save matches; never infer selection from dictionary order.
- [ ] Build current APWorld and verify real AP 0.6.7 generation in an isolated runtime, both sets/goals/layouts and 200 shuffled seeds. Preserve evidence and fail on actual self-locks.

## Task 3: Optional enhanced patch investigation

Files: integration-authored tooling and tests under `tools/` and `tests/`, isolated probe files outside the repository.

- [ ] Inspect the existing isolated exact-hash game copy and identify narrow AP-only menu and factory-entry hooks.
- [ ] Prototype only authored changes in a copied binary. Determine whether room identity and fallback checks can be enforced at those hooks.
- [ ] Before any installation path, test unknown hashes, staged-output verification, backup preservation, rollback and restore refusal on changed files using synthetic files.
- [ ] If hook isolation or runtime verification cannot be established, retain supported mode and record the concrete enhanced blocker; do not ship a guessed patch.

## Task 4: Packaging and handoff

Files: `tools/verify_release.py`, README, setup tutorial, `docs/testing/nonlinear-progression-acceptance.md`, generated project artifacts.

- [ ] Update player instructions for tutorial sequencing, later route choice, beta regeneration, and honest reload limitations.
- [ ] Build mod/APWorld/player archive with existing build tooling and run unit/release verification.
- [ ] Record new automated evidence separately from still-pending live acceptance. Prepare a fresh playthrough archive without altering existing saves.
- [ ] Commit the reviewed changes locally and hand off files and remaining live steps.
