# Release-candidate polish implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task, inline as Jack previously selected. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain campaign readiness and recovery in both AP Mail clients, protect that behavior with connected verification, and prepare an evidence-based release candidate.

**Architecture:** A pure Python presentation module consumes validated room, inventory and save observations. Both bounded Mail transports carry the same read-only presentation to their existing renderers. No renderer decides progression or mutates the game.

**Tech Stack:** Python 3.12, unittest, existing Windows Kivy overlay, existing GameMaker native Mail, GitHub Actions, official Archipelago 0.6.7.

**Spec:** `docs/superpowers/specs/2026-09-27-release-polish-design.md` (approved 2026-09-27).

## Global constraints

- Preserve the single enhanced integration, shuffled pages, four-of-six progression, normal and optional progressive machines, optional recipe checks and word orders.
- Do not change item/location IDs or canonical names, generation rules, goals, machine allowances, YAML defaults, or save format. I production remains available.
- No new sticker grants, filler options, recipes, speed controls, or layouts.
- Campaign rows are bounded at 40; word orders retain the existing 20-row limit. Native snapshots retain the 256 KiB ceiling.
- Preserve progressive 1/2/3/4/unlimited semantics, room identity validation and input isolation.
- Ship no proprietary game binary in the distribution. Native artifacts must be rebuilt from the verified original in a scratch directory, never in the installed game.
- Keep the Akamarus credit and full approved AI-assistance disclosure.
- No publication, live installation changes or game launches during implementation preparation. Request a separate live-test session when required.
- Stable status requires all six acceptance gates in the specification; missing evidence stays Pending.

## Review focus

1. Server-cheated checks must not unlock the displayed local page: Task 1 tests independent completion/page inputs.
2. A delayed scan from the previous room/save must not repaint current readiness: Task 2 tests generation and save-binding races.
3. Mixed protocol versions and oversized snapshots must not crash Mail or silently truncate progression: Task 3 tests version rejection and payload limits.
4. Tab changes and long multilingual/symbol text must not leak input or hide controls: Task 4 tests layout, focus, and input transitions.
5. Failed CI setup and absent live evidence must not look like passing acceptance: Tasks 5 and 6 test required execution and honest evidence states.

## Execution context

Reuse `.worktrees/nonlinear-progression`, branch `test/connected-multiworld`, after checking its current status and applicable instructions. It contains three existing untracked connected-test files; preserve them and integrate only in Task 5. The approved specification is committed separately. Do not stage unrelated files.

All commands below run from that worktree. `python` means Python 3.12 with the repository's test dependencies; on this host use `C:/Users/Jack/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. `AP_SOURCE` means the trusted 0.6.7 checkout; `AP_DEPS` is an optional existing isolated dependency directory. These are command placeholders, not paths to invent or delete.

Each task follows red test, minimal implementation, green test, inline review, and a focused local commit. Do not use broad refactoring to satisfy a test. Do not claim a native probe or CI job passed until actually executed.

## Task 1: Pure campaign and word-order presentation

**Files:** Create `word_factori/progress_presentation.py` and `tests/test_progress_presentation.py`. Read existing `client_core.py`, `requirements.py`, `quantity_logic.py`, `quantities.py`, `layout.py` and `word_orders.py`; do not change their progression rules.

**Interfaces:** Produce frozen `ProgressRow(code: int, page: int, slot: int, name: str, target: str, kind: str, completion: str, page_status: str, machine_status: str)` and `ProgressPresentation(rows: tuple[ProgressRow, ...], summary: str, freshness: str)`. `freshness` is `current`, `last_known`, or `unavailable`; `page` and `slot` are one-based. Produce `build_progress(campaign: ResolvedCampaign, inventory: InventoryView, *, local_slots: frozenset[int] | None, checked: frozenset[int], pending: frozenset[int], freshness: str) -> ProgressPresentation` and `word_machine_status(word: str, inventory: InventoryView) -> str`.

- [ ] Write unittest cases `test_server_completion_does_not_unlock_page`, `test_four_of_six_and_earliest_blocking_page`, `test_partial_final_page`, `test_unknown_save_is_not_locked`, `test_completion_precedence`, `test_normal_alternative_routes`, `test_progressive_quantities_and_unlimited`, `test_lab_restrictions`, and `test_word_machine_status`. Use existing campaign fixtures. Assert the boundary with three local completions still locked and four unlocked; all server checks with zero local completions still locked; Completed takes priority over Sending.

  Core assertion (with the test's resolved campaign and full inventory fixtures):
  ```python
  result = build_progress(campaign, inventory, local_slots=frozenset(),
                          checked=all_campaign_codes, pending=frozenset(), freshness="current")
  self.assertEqual(result.rows[6].completion, "Completed")
  self.assertEqual(result.rows[6].page_status, "Locked: finish 4 more on page 1")
  ```
- [ ] Run `python -m unittest tests.test_progress_presentation -v`; verify failure is missing presentation behavior, not a broken fixture/import of the existing world.
- [ ] Implement the frozen models and functions. Order by shuffled `slot_index`; reuse per-location requirements/budgets, not target-word budgets for restricted labs. Identify the earliest incomplete predecessor page. Missing routes return `No verified route under this level's restrictions`, never ready. Present lab kind as `Campaign lab`. Format bounded alternatives at 512 characters maximum without dropping an alternative's meaning mid-sentence; use a summary if needed.
- [ ] Add `test_no_io_or_input_mutation` and `test_bounds_and_stable_order`: construction must not touch disk or mutate inventory/sets; 40 rows accepted, invalid/duplicate slots or excess rows rejected, repeat calls deterministic.
- [ ] Run `python -m unittest tests.test_progress_presentation tests.test_quantity_logic tests.test_world_layout -v`; require zero failures. Review behavior against the approved spec and commit only this task's two files.

## Task 2: Cached observations and actionable health

**Files:** Create `word_factori/recovery_presentation.py`, `tests/test_recovery_presentation.py`, `tests/test_progress_client.py`; modify `word_factori/client.py`. Extend `tests/test_client_lifecycle.py` when exercising its existing fixtures.

**Interfaces:** Produce frozen `RecoveryPresentation(code: str, severity: str, title: str, action: str)` and `recovery_presentation(code: str, *, platform: str) -> RecoveryPresentation`. Codes: `ready`, `disconnected`, `auth_failed`, `patch_missing`, `patch_outdated`, `unsupported_build`, `room_mismatch`, `save_unbound`, `save_mismatch`, `mod_unselected`, `native_waiting`, `mail_stale`, `journal_invalid`, `unknown_error`. Severity: `info`, `warning`, `error`. Add client methods `progress_presentation() -> ProgressPresentation` and `recovery_presentation() -> RecoveryPresentation`; both consume cached observations only.

- [ ] Write tests asserting fixed, platform-specific recovery copy and absence of sensitive values. For example, `patch_missing` instructs closing the game and running the matching installer; `unsupported_build` does not promise reinstall will fix it. Unknown errors point to the regular client without echoing exception text.

  ```python
  result = recovery_presentation("patch_missing", platform="linux")
  self.assertEqual(result.code, "patch_missing")
  self.assertIn("Close the game", result.action)
  self.assertIn("Linux installer", result.action)
  self.assertNotIn("delete", result.action.casefold())
  ```
- [ ] Add failing client tests for scan failure invalidation, unselected mod, changed save, disconnect/reconnect, and a delayed old-generation scan. Snapshot repeated rendering calls with save readers and binary hashing patched to raise: publishing must not call them.
- [ ] Run `python -m unittest tests.test_recovery_presentation tests.test_progress_client -v`; observe expected failures.
- [ ] Record validated local campaign completions during the ordinary scan, after room/mod/save guards, independently of server confirmation. Store only transient presentation state keyed by connection generation, room contract and bound save ID. Invalidate on failed scan, disconnect or identity/binding change; discard old-generation results. Cache derived presentation by immutable input values rather than elapsed frames.
- [ ] Map existing validation branches to recovery codes at their source, not by parsing arbitrary exception strings. Choose the first actionable blocker in this order: connection/authentication, setup/patch, room contract, mod/save, acknowledgment/journal, renderer transport. Keep detailed diagnostics in the regular client and deduplicate unchanged warnings. Do not change scan/report/reconcile authorization or persisted bridge schema.
- [ ] Run `python -m unittest tests.test_progress_client tests.test_recovery_presentation tests.test_client_lifecycle tests.test_machine_runtime_v2 tests.test_word_order_bridge -v`; require zero failures. Verify progressive missing acknowledgment still blocks reports and I remains available. Commit only task-owned files.

## Task 3: Versioned presentation transport

**Files:** Modify `word_factori/overlay_model.py`, `overlay_protocol.py`, `native_mail_protocol.py`, `native_mail_adapter.py`, `client.py`, and `tools/native_mail_bridge.gml`. Tests: extend `tests/test_overlay_model.py`, `test_overlay_supervisor.py`, `test_native_mail_protocol.py`, `test_native_mail_adapter.py`, `test_native_mail_bridge.py`; create `tests/test_progress_protocol.py`.

**Interfaces:** Overlay protocol becomes version 4; native Mail becomes version 2. Add `progress_rows`, `progress_status`, `progress_freshness`, and `recovery` to snapshots. Rows serialize Task 1 fields with exact keys; recovery serializes Task 2 fields. Word-order rows gain `machine_status`. Both adapters use the same field semantics. Add `open-progress` and `open-status` overlay actions/views; neither grants network or game authority.

- [ ] Write round-trip/parity tests for both protocols and reject bool-as-int row IDs, unknown keys/statuses, duplicate IDs, 41 campaign rows, 21 word rows and text longer than 512 characters. Assert native maximum snapshot size remains 262144 bytes. Test JSON-native boolean/null conversions using the existing fixtures.

  ```python
  self.assertEqual(overlay_protocol.PROTOCOL_VERSION, 4)
  self.assertEqual(native_mail_protocol.VERSION, 2)
  self.assertEqual(native_mail_protocol.SNAPSHOT_BYTES, 262144)
  self.assertEqual(windows_payload["progress_rows"], native_payload["progress_rows"])
  ```
- [ ] Run `python -m unittest tests.test_progress_protocol -v`; verify missing-field/version failures.
- [ ] Extend frozen snapshots and strict validators together. Preserve existing legacy Windows snapshot decoding with empty/unavailable progress defaults; never derive legacy key sets by accidentally including new fields. Reject unsupported future versions with a user-facing update instruction. The native version mismatch stays fail-closed with a regular-client fallback, not a partially accepted envelope.
- [ ] Publish cached Task 2 state identically through `publish_overlay` and `publish_native_mail`. Remove any automatic reuse of previous-room targets; same-room disconnected retention must be visibly `last_known`. Keep all campaign/word rows while bounded history is trimmed, including reserved acknowledgment space. Detect an impossible payload rather than looping indefinitely on a non-history validation failure.
- [ ] Run `python -m unittest tests.test_progress_protocol tests.test_overlay_model tests.test_overlay_supervisor tests.test_native_mail_protocol tests.test_native_mail_adapter tests.test_native_mail_bridge tests.test_native_mail_transport -v`; require zero failures. Assert failed presentation delivery cannot stop authoritative item reconciliation. Commit task-owned files.

## Task 4: Windows/Linux Progress and recovery displays

**Files:** Modify `word_factori/overlay_renderer.py`, `tools/native_mail_ui.gml`, `tools/native_mail_ui_acceptance.gml`, `tools/native_mail_bridge_acceptance.gml`, `tools/native_mail_live_acceptance.gml`, and `tests/native_mail_fixtures.py`. Create `tests/test_progress_renderer.py`; extend `tests/test_native_mail_hooks.py` and `tests/test_mail_full_isolation.py`. Update `tools/mail_live_peer.py` fixtures to the new snapshot schema.

**Interfaces:** Both UIs expose Items, Chat, Type-a-Word, Progress and Status; Windows keeps its connection/password forms. Progress renders Task 3 rows without recomputing rules. Status renders the recovery title/action plus existing safe connection details. Native draw/hit-testing share tab geometry, rather than duplicating row/column arithmetic.

- [ ] Write tests for Progress/Status tab actions, two-row tabs at narrow width, all labels/hitboxes inside the panel, long target/requirement wrapping, page headers, unknown/last-known labels, symbols and empty state. Compare semantic displayed row text on both platforms.

  ```python
  state = apply_action(OverlayState.closed(), OverlayAction("open-progress"))
  self.assertTrue(state.is_open)
  self.assertEqual(state.active_view, "progress")
  self.assertFalse(state.is_focused)
  ```
- [ ] Run `python -m unittest tests.test_progress_renderer tests.test_native_mail_hooks -v`; observe missing view/geometry behavior.
- [ ] Implement scrollable progress and status panels using current style/font handling. Add machine details to existing word cards. Show local page availability separately from server completion; never create a combined unconditional `Ready to play` label. Keep canonical lab names visible alongside the friendly kind label.
- [ ] Extend native acceptance cases for every new tab, Chat-to-Progress-to-Items, dismissal, held-key capture, focus/room reset, narrow layout, wrapping and repeat toggles. Update native protocol fixtures rather than bypassing validation. Do not add new OS hooks or auto-focus behavior.
- [ ] Run `python -m unittest tests.test_progress_renderer tests.test_overlay_model tests.test_overlay_supervisor tests.test_mail_full_isolation tests.test_native_mail_hooks tests.test_native_mail_bridge -v`; require zero failures. Compile/reopen through Task 6's scratch build before claiming native integration works. Mark actual UI/native execution pending until its separate session is authorized. Commit task-owned files.

## Task 5: Required connected CI

**Files:** Integrate existing `tools/verify_connected_multiworld.py`, `tests/test_connected_multiworld.py`, `docs/testing/connected-multiworld.md`. Create `tools/requirements-connected.txt`, `tests/test_connected_ci.py`; modify `.github/workflows/verify.yml`.

**Interfaces:** Keep the runner's current CLI and real AP clients/server. AP source pin is `debe4cf035c7c15efe6fb95f72343af0d420c68c`, locally verified as tag `0.6.7`. CI sets `WF_AP_SOURCE` explicitly so the real-room and premature-victory tests cannot opt out. Two-seed reports remain in unique per-job directories.

- [ ] Write tests that inspect the workflow's parsed structure: Windows/Ubuntu connected jobs use the exact AP revision, Python 3.12, build before running, both seeds, bounded job timeout, and failure-artifact upload. Require an explicit AP source directory check before unittest to prevent absent-environment skips.

  ```python
  self.assertEqual(source_pin, "debe4cf035c7c15efe6fb95f72343af0d420c68c")
  self.assertEqual(set(connected_platforms), {"windows-latest", "ubuntu-latest"})
  self.assertEqual(set(scheduled_seeds), {160929, 160930})
  self.assertLessEqual(job_timeout_minutes, 15)
  ```
- [ ] Run `python -m unittest tests.test_connected_ci -v`; confirm failure for missing connected jobs.
- [ ] Pin the minimal core import dependencies in `requirements-connected.txt`: colorama 0.4.6, websockets 13.1, PyYAML 6.0.3, jellyfish 1.2.1, jinja2 3.1.6, schema 0.7.8, platformdirs 4.9.4, orjson 3.11.7, typing_extensions 4.15.0. Validate in an isolated environment; add a dependency only if an actual core import identifies it. Do not use AP's optional-world installer or install Kivy for headless tests.
- [ ] Add connected CI jobs with contents-read permission, 15-minute timeout, loopback tests, isolated AP checkout, no secrets and artifact retention of 7 days. Commands: `python tools/build_release.py`; `python -m unittest tests.test_connected_multiworld -v` with `WF_AP_SOURCE` set; then `python tools/verify_connected_multiworld.py --ap-source AP_SOURCE --seed 160929 --output connected-results/160929` and the corresponding seed 160930 command. Upload only synthetic reports/logs, not AP/game source, on success or failure.
- [ ] Run local connected tests and both seeds with the real trusted AP source/dependencies against the newly built APWorld. Require 263/263 checks and 2/2 goals per report plus existing required coverage counters. Record new package hash rather than copying the 1.6.0 evidence. Run `python -m unittest tests.test_connected_ci -v` and commit all six task-owned files. Actual GitHub job results remain pending until a later authorized push.

## Task 6: Candidate packaging, documentation and acceptance handoff

**Files:** Modify `README.md`, `CHANGELOG.md`, `examples/WordFactori.yaml`, `examples/WordFactoriProgressive.yaml`, `tools/build_release.py`, and distribution tests if required to include examples. Create `docs/testing/release-candidate-acceptance.md`, `tests/test_release_polish_docs.py`. Native artifact owners: `tools/build_enhanced_probe.py`, `tools/enhanced.patch.gz`, `word_factori/enhanced_runtime.py`, `tools/install_enhanced.ps1`, `tools/install_linux.py`, and associated installer/integrity tests.

**Interfaces:** Existing one-ZIP install contract stays intact. Matching patch, receipt and installer hashes come from the new scratch artifact, never invented constants. Retain the prior 1.6.0 hash as an explicitly supported upgrade source. Keep current release version/status until separate publication preparation; use an Unreleased changelog section and identify local candidates by commit/package hash.

- [ ] Write failing documentation/distribution tests for both quick-start paths, troubleshooting and the two YAML examples parsing/generating successfully. Reuse AP option validation in the connected environment, not only YAML syntax. The normal example stays straightforward; the progressive example explicitly enables recipe checks and three chosen word orders with a valid list. This edits example choices only, not option defaults.

  ```python
  self.assertTrue(progressive_options["progressive_machines"])
  self.assertTrue(progressive_options["recipe_checks"])
  self.assertTrue(progressive_options["type_a_word_checks"])
  self.assertEqual(progressive_options["type_a_word_count"], 3)
  self.assertGreaterEqual(len(set(progressive_options["type_a_word_words"])), 3)
  ```
- [ ] Write the acceptance record covering all six spec gates, including exact package/hash/date/platform/evidence columns and Pending/Pass/Fail/Unsupported states. Initialize unobserved live cases Pending, exclusive fullscreen Unsupported. Include the 60-minute measurement worksheet at warm-up, 15, 30, 45 and 60 minutes with a fixed comparable factory state.
- [ ] Rewrite concise README quick-start/check-type/recovery sections and changelog; preserve author/disclosure. Link maintainer testing documents through repository URLs if they are intentionally excluded from the player ZIP. Clearly distinguish install/update restart from prohibited per-item reload dependency.
- [ ] Compile the updated native helpers in a new scratch directory using `python tools/build_enhanced_probe.py --cli CLI --original ORIGINAL --output SCRATCH/data.win`. Resolve all three inputs from verified existing tooling and allowlisted original; refuse if unavailable or if output is an installed path. Update build metadata to native Mail protocol 2. Compile/reopen checks must pass before producing a delta with `python tools/enhanced_delta.py ORIGINAL SCRATCH/data.win SCRATCH/enhanced.patch.gz`. Verify exact round-trip before replacing the repository's delta through a controlled artifact update.
- [ ] Update hash owners and upgrade tests from that artifact; preserve matching receipt validation and original backup checks. Test 1.6.0-to-candidate upgrade and restore transactions with fixtures on both platforms. Do not run the real installer or alter live game files. If tooling/original is unavailable, stop the packaging step and report that blocker rather than shipping a stale patch.
- [ ] Run `python -m unittest tests.test_release_polish_docs tests.test_installer tests.test_linux_installer tests.test_enhanced_installer tests.test_enhanced_delta tests.test_unified_distribution tests.test_publication -v`, then `powershell -ExecutionPolicy Bypass -File tools/verify.ps1 -PythonExecutable PYTHON`. Repeat Task 5's two seeds against the final package and compare contract/ID/YAML-default invariants with the baseline. Require zero unexpected failures and explicitly account for skipped platform/live cases.
- [ ] Commit scoped documentation, fixtures and verified generated artifacts. Provide the acceptance checklist to Jack, with headless verification separated from pending native/live results. Do not tag, push, publish or call the candidate stable.

## Separately authorized native/live acceptance session

The implementation is not a stable-release sign-off. After Jack authorizes a suitable session, run the existing isolated probe with updated fixtures:

`python tools/run_mail_native_probe.py --cli CLI --original ORIGINAL --runtime RUNTIME --output NEW_SCRATCH --case all --live-bridge`

Run editor/factory cases as well, using fresh outputs and existing bounded process/error handling. Require clean process exit, complete assertions and teardown; a printed pass followed by a crash fails. Do not create repeated crash dialogs or launch unattended visible windows. These Windows-runner results still do not constitute Linux gameplay evidence.

Then perform the actual six spec gates on supported Windows and Linux setups, record evidence against the exact package, investigate failures, and rerun affected gates after fixes. Jack controls live launches and final publication. Untested cases remain visibly pending; there is no automatic stable promotion.

## Plan self-review

- Spec coverage: Tasks 1–2 cover readiness, freshness and recovery; Tasks 3–4 cover both transports/UIs; Task 5 covers required connected CI; Task 6 and the separate session cover documentation, package integrity and all live gates.
- Interfaces: presentation field names, 40/20 row limits, 512-character detail limit, overlay v4/native v2 and generation-bound observations are consistent across tasks.
- Safety: no game/save writes from presentation, no UI-derived authority, no hidden native launch, no unauthorized release.
- Existing untracked work is preserved until its dedicated integration task. No new rule/check/default changes are planned.
- Execution method remains inline. Plan awaits Jack's review before implementation.
