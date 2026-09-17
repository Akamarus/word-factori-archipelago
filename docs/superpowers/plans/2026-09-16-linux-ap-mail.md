# Linux AP Mail Implementation Plan

## Execution checkpoint — 2026-09-17

Jack authorized preparation for GitHub release, including the local 1.6.0 tester
version/package. No push, merge, live installation or publication is authorized
by this checkpoint. Execution remains inline. Historical checklists below are
preserved rather than falsely marking unperformed manual/commit steps complete.

- Task 1: bounded feasibility passed using combined native and full-object
  scratch evidence; Jack confirmed physical placement/connection. Linux proof
  and full production UI acceptance are separate gates.
- Tasks 2–5: strict protocol, owned transport, presentation/actions and real
  native/Python interoperability implemented and tested. Native JSON boolean/null
  representation and scratch global-stub scope were corrected after failing runs.
- Task 6: all native tabs, input isolation, status, Older/Latest history and
  popups implemented; final combined bridge/UI case passes 50 assertions. Manual
  production-panel visual and sustained performance acceptance remain pending.
- Task 7: 42 production hook entries compile/reopen; final delta round-trip
  passes. Linux owned marker/receipt and all Python module packaging are included.
  Fresh separate 99 quantity/enforcement and 8 recipe assertions pass. Final
  full-suite/package verification is recorded in the release-preparation report.
- Task 8: player docs, release notes and a private two-player Linux acceptance
  matrix are prepared. Actual Linux/Proton execution is pending, not waived.

See `docs/testing/linux-native-mail-evidence.md` for the current checkpoint and
`docs/testing/linux-mail-acceptance.md` for explicit remaining platform coverage.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Jack previously selected inline execution; do not dispatch subagents or ask him to choose the execution mode again.

**Goal:** Deliver native in-game AP Mail for Linux/Proton with Items, Chat, Type-a-Word and status, preserving progression and simple installation.

**Architecture:** The existing native Linux client remains authoritative for networking and progression. A separate bounded file transport presents its state to a native game UI and returns validated user actions. Native UI failures release input and fall back to the regular client; Windows retains its current overlay.

**Tech Stack:** Python 3.12+, unittest, integration-authored GML, existing UndertaleModTool CLI and exact-build reversible delta tooling. No new runtime dependency, compositor extension, service or Wine-hosted AP client.

**Spec:** `docs/superpowers/specs/2026-09-16-linux-ap-mail-design.md` (read fully before execution).

## Global Constraints

- The first complete delivery includes Items, Chat, Type-a-Word, delivery popups and connection status. It is not an items-only release.
- Initial connection, server/slot selection and password entry remain in the regular Linux client.
- No connection password is included in either envelope.
- No YAML changes, check IDs, recipe requirements or room layout changes are needed for Mail.
- Do not merge, install or publish this work as part of approving this document.
- Read the manifest at most four times per second from the normal UI update path.
- Heartbeats advance once per second. Five seconds without an observed advance marks the bridge unavailable and disables outbound actions.
- Manifest limit: 4 KiB. Snapshot limit: 256 KiB, with at most 50 item rows, 50 transcript rows, 20 word targets, three active notifications and 32 action acknowledgments.
- Submitted text is capped at 1,024 code points and 8 KiB for the whole request.
- Windows scratch probes do not count as Linux evidence.
- Do not distribute game binaries, extracted native source, raw recipe tables or proprietary fonts.
- Preserve unrelated edits, game saves, installed files and the original-game backup.

## Starting state and execution rules

Use the existing isolated `feature/type-a-word` worktree, not the main checkout.
Its design commit is `20ef51e`; the preceding AP Mail word-tab, performance and
source-generation fixes are still uncommitted. They passed 676 unit tests
(two skipped) and 99 isolated native assertions before this plan. Those are
baseline evidence, not permission to skip fresh verification.

Before editing, record `git status --short` and `git diff --stat` in private
scratch evidence. Review changes to overlapping client/installer/release files
so previous work is preserved. Commit only completed task changes. For a file
containing earlier uncommitted work, use deliberate hunk staging or leave that
task uncommitted with an explicit report; never sweep it into an unrelated commit.

Commands below assume the repository root and `python` refers to the selected
Python 3.12+ interpreter. On this Windows host the bundled interpreter is known
to be usable; the installed game is read-only input, never a probe destination.
Set developer-local `WF_ORIGINAL`, `WF_RUNTIME`, `WF_CLI` and `WF_SCRATCH` to
verified paths before running native commands. Each native output subdirectory
must be fresh and outside both the repository and installed game directory.
Do not hardcode the developer's paths in committed files or player documentation.

Task 1 is a hard feasibility gate. Later tasks are executed only after its
evidence supports native presentation and input isolation. If a requirement
cannot be proved, record the blocker and stop the affected implementation;
do not substitute a companion window or remove chat without Jack's direction.

## File responsibilities

| Files | Responsibility |
|---|---|
| `tools/mail_hooks.py` | Exact native Mail hook transforms; no networking or game data |
| `tools/run_mail_native_probe.py`, `tools/native_mail_acceptance.gml` | Scratch-only native fixture and acceptance assertions |
| `word_factori/native_mail_protocol.py` | Strict wire schema, bounded encoding/decoding and pure freshness checks |
| `word_factori/native_mail_transport.py` | Paired filesystem paths, ownership, atomic snapshots, requests and acknowledgments |
| `word_factori/native_mail_adapter.py` | Convert existing presentation into bounded snapshots and route permitted actions |
| `tools/native_mail_bridge.gml` | Bounded native reads, handshake, freshness and action submission |
| `tools/native_mail_ui.gml` | Native UI state, drawing, hit testing, text input and cleanup |
| `word_factori/client.py` | Small lifecycle/presentation integration points only |
| `tools/enhanced_hooks.py`, `tools/build_enhanced_probe.py` | Compose verified Mail hooks with existing progression hooks |
| `tests/test_native_mail_*.py`, `tests/native_mail_fixtures.py` | Pure, transport, lifecycle, hook and packaging regressions |
| Existing installer/build/verification files | Ship verified modules/delta and preserve upgrade safety |

Do not move or rewrite the existing Windows renderer, quantity solver or native
machine enforcement as part of this feature.

## Task 1: Prove native drawing and input ownership

Checkpoint 2026-09-16: partial native proof is recorded in
`docs/testing/linux-native-mail-evidence.md`. The scratch fixture passes 25
automatic runtime assertions and all 35 hook entries compile/reopen. A resumed
desktop test also passed four physical keyboard assertions: one press, 108 held
frames, one release, zero native consumer events. Populated-factory and viewport
acceptance remain pending; Task 1 is NOT complete and Tasks 2–8 have not started.
No production wiring was changed.

Factory checkpoint: a cross-frame native simulation comparison was added, with
identical observed production for closed/open Mail, but the scratch process
crashes during shutdown. Separate processes did not eliminate the failure.
The runner correctly refuses it; Task 1 remains blocked, not passed. Fresh
Mail-only (25 assertions) and existing enforcement/quantity (99 assertions)
controls exit cleanly. See the evidence document before continuing native work.

Shutdown investigation checkpoint: scratch children now inherit process-local
Windows no-dialog error handling, verified by child-process tests. Exit failures
are still rejected. A private debugger captured freed-memory access during
shutdown; multiple isolated candidate changes were disproved, including cases
that first passed normal runs. No candidate gameplay or lifecycle fix was
accepted. Task 1 remains incomplete; the next diagnostic is a minimal native
completion-call/lifetime reproduction, not additional production UI wiring.

Later shutdown checkpoint: the reduced case also failed with empty methods and
no Mail or simulation, disproving the initial struct/completion theories.
Scratch-only two-phase teardown (destroy host-created objects, allow normal
engine steps, then report/quit from an Alarm) passed 40 minimal, 40 closed-factory
and 40 rebuilt open-factory debugger runs. The new paired probe passes 32
assertions with matching ten-word production in 21 ticks/frames. Exit validation
is unchanged; teardown evidence is mandatory. This clears the bounded fixture's
shutdown blocker, not Task 1's remaining original-editor/viewport/platform gate.
No live installation, production patch or release changed. See current evidence
for the sequential full-suite and ordinary-launch results.

Editor checkpoint: the complete verified native editor Step, invoked in a
bounded fixture with native movement/eraser methods, reproduced five failures
from existing drags and a retained eraser latch. A mode-aware capture guard now
passes 41 input/teardown/editor assertions in a fresh build and ten consecutive
ordinary launches. Dismissal does not re-arm a drag; a fresh click resumes it and
normal release commits once. Native production dispatch remains active, and a
blanket-pause mutation is rejected. A fresh paired factory run still passes 32
assertions with equal production/journals. Full-object physical input, viewport
and Linux/Proton evidence are still pending. Task 1 remains incomplete; no
production bridge, installation or release changed.

**Files:** create `tools/mail_hooks.py`, `tools/run_mail_native_probe.py`,
`tools/native_mail_acceptance.gml`, `tests/test_native_mail_hooks.py` and
`docs/testing/linux-native-mail-evidence.md`.
Full-object checkpoint: a private cloud-isolated copy retains original rooms and
object lifecycles and now exits cleanly with an explicit finish marker. Desktop
tests confirm immediate Mail opening, Chat/Items switching, dismissal without
native-menu click-through, fullscreen coordinate mapping, and pending placement
capture/resume through original editor events. Automated palette/wire dragging
and arbitrary resizing were not established; populated-factory completion and
minimum viewport checks remain pending. Keep Task 1 incomplete and Tasks 2–8
unstarted. See the evidence document for the separate safety audit and failed
probe history; no production wiring or installed files changed.

Manual follow-up: Jack confirmed palette-to-grid placement and wire connection
both worked in the isolated full-object copy. A diagnostic 1280x720 viewport
also preserved Mail hit testing. The manual run exited 0 without its mandatory
finish marker before production-with-Mail-open could be checked, so it is not
an accepted complete probe. Preserve the user-reported observation separately
from automated assertions. Task 1's remaining acceptance gate is unchanged.

Production follow-up: `mail-full-v6/production-run-1` reopened that connected
scratch factory, started Play and opened Mail at counter zero. Native logs
progressed from production mode 4 to completion mode 6 while `open:true`;
dismissing Mail revealed the completed I result. F10 finish and exit 0 were both
verified, so this is an accepted full-object production observation. It does
not establish speed equivalence, AP delivery or Linux behavior. Remaining
input/focus and viewport checklist gaps still need review before Task 1 closes.

Focus/viewport follow-up: `mail-full-v6/focus-run-1` passed the full-object
minimize/restore check (panel closed, draft cleared, two modules unchanged).
Returning the pointer to the grid allowed normal I-shortcut placement and one
new machine; Mail reopened normally. Resizing the open panel to a 1280x720
client viewport preserved tab hit testing and consumed an outside dismissal
over native Play without starting production. F10 finish and exit 0 verified.
Review Task 1 against the combined bounded/native/desktop evidence next; keep
Task 6's complete panel/input/viewport acceptance and Task 8's Linux acceptance
separate rather than treating the developer panel as production-ready.

Read existing `tools/run_type_word_native_probe.py`, `tools/enhanced_hooks.py`
and `tools/build_enhanced_probe.py` for scratch isolation and exact-hook patterns.

**Interfaces:** `transform_mail_sources(sources: dict[str, str], helpers: str)
-> dict[str, str]`; native runner command accepts `--cli`, `--original`,
`--runtime`, `--output` and `--case`. Cases: `input`, `bridge`, `ui`, `all`.
The first task implements `input`; the other cases reject use until supported.
Every completed case emits `result.json` with `supported`, named assertion
results, input hashes and the active hook list. A failed assertion exits nonzero.

- [x] Record fresh baseline: `python -m unittest discover -s tests -q`.
- [ ] Verify the original with `tools.enhanced_hooks.verify_original`. Use the
  CLI's object/event inventory to identify actual GUI draw, early input dispatch,
  focus and cleanup sites. Inspect private extracted code, including independent
  native widgets and factory placement paths. Record exact hook names/hashes and
  event ordering in scratch evidence; never guess them from object names.
- [x] Write failure tests against integration-authored minimal fixtures. A missing,
  duplicate, already-patched or changed hook must be refused before output writes:

```python
def test_missing_mail_hooks_are_refused(self):
    from tools.mail_hooks import transform_mail_sources
    with self.assertRaises(ValueError):
        transform_mail_sources({}, "// authored helpers")
```

- [x] Run `python -m unittest tests.test_native_mail_hooks -v`; confirm the new
  tests fail before implementing their guards.
- [ ] Implement exact transforms only for verified sites, using the existing
  uniqueness-check pattern. Preserve the native tick and progression guards.
  The runner must verify inputs before writing, reject existing outputs and
  symlink/reparse destinations, retain raw data outside Git, use an isolated save
  namespace and suppress external network/save services in the test copy.
- [ ] Build a minimal panel fixture with game-font drawing, F8/button toggle,
  two tab targets and native input consumers instrumented with counters. Exercise
  mouse press/hold/release, outside close, Escape, wheel, typing and focus loss.
  Counters for native placement/shortcuts must remain zero for consumed events;
  normal gameplay input must resume after release. No AP connection is needed.
- [ ] Run the isolated case:

```text
python tools/run_mail_native_probe.py --cli "$WF_CLI" --original "$WF_ORIGINAL" --runtime "$WF_RUNTIME" --output "$WF_SCRATCH/mail-input" --case input
```

- [ ] Compile and reopen all touched hooks; inspect actual rendered panel and
  coordinate behavior in the scratch game. Record programmatic versus manual
  evidence separately, including any manual input still awaiting validation.
- [ ] Gate: no production wiring until immediate toggle, font selection, input
  dispatch suppression and cleanup work. Structural compilation alone is not a
  passed native input test. Re-run hook tests and existing enforcement tests.
- [ ] Commit only authored probe/transforms/tests and sanitized evidence:
  `test: prove native AP Mail drawing and input isolation`.

## Task 2: Define and test the bounded protocol

Execution checkpoint: the combined native fixtures and accepted full-object
production/focus/viewport runs now support the bounded Task 1 feasibility gate.
The 34 targeted Python hook/isolation/enforcement tests pass. Proceed to the
protocol, retaining the separate full UI, composition, stress and Linux rollout
gates. Earlier partial checkpoints above remain historical evidence. Task 1
files remain uncommitted pending the final scoped review; no live patch changes.

**Files:** create `word_factori/native_mail_protocol.py`,
`tests/native_mail_fixtures.py`, `tests/test_native_mail_protocol.py`.

**Interfaces:** `encode_envelope(value: dict, *, kind: str) -> bytes`,
`decode_envelope(raw: bytes, *, kind: str) -> dict`,
`heartbeat_fresh(last_advance: float | None, now: float) -> bool`.
Allowed kinds are `manifest`, `snapshot`, `hello`, `request`. Unknown kinds
and extra fields fail with `ValueError`. Export the spec's byte/row limits as
named constants. This module has no filesystem, GUI or Archipelago imports.

Manifest fields: `version`, `session`, `renderer`, `revision`, `heartbeat`.
Hello fields: `version`, `renderer`, `heartbeat`. Request fields: `version`,
`session`, `renderer`, `room`, `sequence`, `action`, `payload`.
Use protocol version 1, UUID-hex session/renderer identifiers and nonnegative
integer revisions/heartbeats (reject booleans). Room is a bounded identity string
or null only for connection control. Include the bound contract in snapshots.

Snapshot fields: `version`, `session`, `renderer`, `revision`, `room`,
`contract`, `connection`, `items`, `chat`, `words`, `notifications`, `unread`,
`acks`, `history`. Project only necessary display fields from existing immutable
presentation rows. History cursors are opaque bounded client-issued strings.
Required row keys are frozen in schema tests before transport work:

- Items/notifications: `key`, `direction`, `item`, `player`, `location`,
  `historical`, `unread`. Direction is received/sent/self; the last two are booleans.
- Chat: `key`, `kind`, `text`; kind is chat/hint/command/error.
- Words: `name`, `word`, `status`; status is Not completed/Sending/Completed.
- Acks: `sequence`, `status`, `message`; status is queued/forwarded/rejected/uncertain.
- History: `items` and `chat`, each a cursor string or null.

Use at most 512 code points per display text field and 128 per
identity/cursor field; targets preserve all 12 supported characters. Never pass
raw AP packets, paths, options dictionaries or credentials.

Request action/payload pairs are exact: `submit-text` with `text`; `mark-read`
with `through_key`; `history` with `view`, `filter`, `cursor`; `disconnect` and
`reconnect` with an empty object. History view is items/chat; filter is
all/received/sent for items and all for chat. `through_key` and history cursors
must refer to a snapshot actually issued in this renderer/session. Mark-read
affects only deliveries at or before that displayed boundary, never later arrivals.
Reject other action names, payload fields and invalid pairings before dispatch.

- [ ] Start with strict round-trip and malformed-manifest tests:

```python
def test_manifest_round_trip_and_rejects_boolean_revision(self):
    from word_factori.native_mail_protocol import encode_envelope, decode_envelope
    value = dict(version=1, session="a" * 32, renderer="b" * 32,
                 revision=0, heartbeat=0)
    self.assertEqual(value, decode_envelope(
        encode_envelope(value, kind="manifest"), kind="manifest"))
    value["revision"] = True
    with self.assertRaises(ValueError):
        encode_envelope(value, kind="manifest")
```

- [ ] Run `python -m unittest tests.test_native_mail_protocol -v` and observe red.
- [ ] Implement UTF-8 byte ceilings before decode, rejection of duplicate JSON
  keys/nonfinite numbers/nested unknown payloads and exact per-kind keys. Encode
  only schema-whitelisted fields with `ensure_ascii=False`; validate both paths.
- [ ] Add boundary tests at and above every limit, malformed UTF-8, empty text,
  credentials/extra fields, wrong versions, surrogate text and deep nesting.
  Add freshness tests at 4.999 seconds and 5 seconds using an injected clock.
- [ ] Define fixture builders `mail_manifest()`, `mail_snapshot()` and
  `mail_request(sequence=1, action="submit-text", text="hello")`, each returning
  a fresh valid dictionary with session `a*32`, renderer `b*32`, room `room-A`.
  Reuse them in later test modules, not in production.
- [ ] Run protocol tests; commit `feat: define bounded native Mail protocol`.

## Task 3: Atomic transport, ownership and duplicate handling

**Files:** create `word_factori/native_mail_transport.py` and
`tests/test_native_mail_transport.py`. Read `platform_paths.validate_state_target`
and the existing atomic persistence helpers; retain their alias/path checks.

**Interfaces:** `NativeMailTransport(root: Path, session: str, *, clock: Callable[[], float])`;
`start() -> None`, `publish(snapshot: dict) -> None`, `poll() -> tuple[dict, ...]`,
`acknowledge(request: dict, status: str, message: str) -> None`, `close() -> None`.
The adapter never receives unvalidated envelopes. No GUI or network imports.

- [ ] Write temporary-directory tests for atomic publication and duplicate input:

```python
def test_wrong_session_request_never_reaches_client(self):
    from tests.native_mail_fixtures import mail_request
    from word_factori.native_mail_protocol import encode_envelope
    request = mail_request()
    request["session"] = "c" * 32
    (self.mail_root / "request.json").write_bytes(
        encode_envelope(request, kind="request"))
    self.assertEqual((), self.transport.poll())
```

Test setup creates a temporary paired root, injected monotonic clock, transport
and matching renderer hello; close resources through `addCleanup`.

- [ ] Run transport tests red. Implement fixed filenames `manifest.json`,
  `snapshot.json`, `hello.json`, `request.json` and one client ownership lock.
  Only the client writes manifest/snapshot; only the game writes hello/request.
- [ ] Acquire an OS-released advisory ownership lock for the native client,
  with a Windows test-host implementation behind the same small interface.
  Reject a second client. Bind one renderer for the active session; a conflicting
  fresh hello suspends Mail rather than allowing either renderer's new actions.
- [ ] Publish snapshot first and manifest second using same-directory atomic
  replacement. Serialize publication through one owner; cleanup temporary files
  on failure. Game readers require matching session/revision and never mix pairs.
- [ ] At most one new request enters dispatch at a time. Reserve its sequence
  before asynchronous routing. Keep a bounded acknowledgment ring of 32 entries
  plus a high-water sequence: old evicted sequences are rejected, never reissued.
  Duplicate pending requests do not dispatch again. New client sessions invalidate
  all earlier requests; uncertain chat is never retried across a session change.
- [ ] Add failure tests for interrupted writes, read-only directories, aliases,
  process ownership, old renderer IDs, backward sequence/revision, full queue,
  shutdown during dispatch and malformed files. Assert no save/level file writes.
- [ ] Test manifest heartbeat independently of snapshot revision and enforce
  four polls/second without wall-clock comparisons. Publish changed presentation
  only; coalesce updates rather than growing an unbounded queue.
- [ ] Run transport/protocol tests; commit `feat: add native Mail file transport`.

## Task 4: Client presentation and safe action routing

**Files:** create `word_factori/native_mail_adapter.py`,
`tests/test_native_mail_adapter.py`; modify `word_factori/client.py`,
`tests/test_client_lifecycle.py` and `tests/test_linux_client.py` narrowly.

**Interfaces:** `NativeMailAdapter(transport: NativeMailTransport)`;
`publish(value: OverlaySnapshot, *, room: str | None, contract: str | None) -> bool`,
`async process_once(context: WordFactoriContext) -> None`, `close() -> None`.
The existing `word_order_presentation()` remains the authoritative target source.
History requests page the existing ledger/transcript using validated opaque
cursors; they must not re-read saves or rebuild quantity reachability.

- [ ] Write adapter tests proving words/status projection and action isolation:

```python
def test_words_are_preserved_when_history_is_trimmed(self):
    self.adapter.publish(self.large_snapshot, room="room-A", contract="contract-A")
    sent = self.transport.published[-1]
    self.assertEqual(self.expected_words, sent["words"])
    self.assertLessEqual(len(sent["items"]), 50)
    self.assertLessEqual(len(sent["chat"]), 50)
```

Use a recording fake transport and existing snapshot/dispatch/transcript
constructors to build fixtures; do not instantiate a GUI in these tests.

- [ ] Run adapter tests red. Whitelist and truncate display fields, trim oldest
  history until the total byte ceiling passes, preserve word targets, and avoid
  replaying historical delivery popups. Persist read acknowledgment through the
  existing dispatch-ledger method only after a matching view acknowledgment.
- [ ] Route plain chat and `!` server commands through the current submit path.
  Permit only `/help`, `/wf_status`, `/wf_words` as local native-panel commands;
  reject other slash commands with regular-client guidance. Never route arbitrary
  native action names into command attributes, eval, shell or filesystem calls.
- [ ] Recheck session/room immediately before forwarding any awaited chat action.
  A disconnect/reconnect request applies only to the currently paired client's
  configured address/slot; missing configuration sends the user to that client.
- [ ] Wire Linux-only adapter startup, presentation changes, action polling and
  cleanup without starting Kivy. Keep Windows overlay behavior unchanged. UI
  disablement or adapter exceptions must not cancel progression reconciliation.
- [ ] Test wrong-room actions, reconnect with retained history, stale draft/session,
  missing configuration, unsupported native capability, unavailable bridge and
  duplicate acknowledgment. Assert no item/check changes from any Mail action.
- [ ] Run adapter, Linux client, full client lifecycle and existing overlay tests;
  commit only reviewed hunks as `feat: connect Linux client to native AP Mail`.

## Task 5: Native bridge and lifecycle

**Files:** create `tools/native_mail_bridge.gml`; extend the Task 1 runner and
native acceptance fixture for `--case bridge`; add `tests/test_native_mail_bridge.py`.

**Interfaces:** `wf_mail_bridge_step(now_ms)`, `wf_mail_bridge_ready()`,
`wf_mail_submit(action, payload)`, `wf_mail_bridge_shutdown()`.
One native owner holds validated snapshot, pending request and session identity;
UI consumers never read files directly. Functions return unavailable/rejected
states on errors, not unhandled exceptions. Poll scheduling uses elapsed game time.

- [ ] Add authored transform/runner tests requiring the bridge entry points and
  refusing compilation on ambiguous hooks. Run them red before adding helpers.
- [ ] Implement bounded native reads with file-size checks and exception-safe
  handle closure. Check the manifest at 250 ms intervals and only parse the large
  snapshot when its revision changes; freshness requires observed heartbeat
  advancement. Never perform this work from Draw or production callbacks.
- [ ] Match native room/contract context to the accepted snapshot. Session/room
  changes clear drafts, pending view state and old target rows. A missing client
  yields a local status explanation. Corrupt data disables sending immediately.
- [ ] The native writer uses a unique temporary filename and verified replacement
  behavior from the scratch probe. It retains one numbered pending action, blocks
  overwrite and distinguishes forwarded/rejected/uncertain outcomes. Do not claim
  exactly-once delivery to the AP server across crashes.
- [ ] Extend native fixture with bounded good/bad files, wrong identities, restart,
  stale heartbeat, duplicate sequence, interrupted replacement and queue-full
  cases. Record file-read counters and handle/resource counts.
- [ ] Run `--case bridge` in a fresh scratch directory; require every assertion
  plus baseline quantity enforcement to pass. Commit `feat: add native Mail bridge`.

## Task 6: Full native panel and notifications

**Files:** create `tools/native_mail_ui.gml`; extend `tools/mail_hooks.py`,
`tools/native_mail_acceptance.gml`, `tests/test_native_mail_hooks.py` and
`docs/testing/linux-native-mail-evidence.md`.

**Interfaces:** `wf_mail_ui_step()`, `wf_mail_ui_draw()`, `wf_mail_ui_blocks_input()`,
`wf_mail_ui_reset()`; consume Task 5's cached snapshot and submit function.
Use Task 1's proven hook locations/font/GUI-coordinate mapping, not guessed IDs.

- [ ] Add native assertions before wiring production behavior. The input trace is:

```text
closed -> press Mail -> open Items; placement counter remains unchanged
open Items -> press Chat -> open Chat; close counter remains unchanged
focused Chat -> type "hi" -> draft only; factory shortcuts unchanged
focused Chat -> Enter -> one numbered request; repeated hold sends nothing
open -> outside click -> closed; same click does not place a machine
open -> focus loss -> input capture released
```

- [ ] Implement local view/filter/scroll/draft state with edge-triggered buttons.
  Red Mail button stays left, delivery popups blue/left, panel dark/purple. Native
  game font is referenced from installed resources and never copied into a ZIP.
- [ ] Render all Items filters, Chat/hints/results, word targets/status and status
  page. Cache wrapped/clipped visible rows by snapshot revision and layout size;
  do not allocate retained surfaces per frame. Provide readable glyph fallbacks.
- [ ] Limit notifications to three, deduplicate by delivery identity and never
  show them over the expanded panel or steal focus. Opening/read acknowledgment
  must not mark items received after the viewed snapshot as already read.
- [ ] Consume captured input at the proven dispatcher boundary while leaving
  simulation running. Opening/closing is local and same-frame. Keep the dismissal
  press consumed until release; focus loss/error cleanup never leaves a stuck
  key or mouse latch. Apply text limits before writing requests.
- [ ] Exercise minimum supported viewport, fullscreen/windowed/resize/scaling,
  long names, symbols, maximum rows, keyboard shortcuts, wheel and focus changes.
  Record screenshots only in private scratch unless separately approved for docs.
- [ ] Run `--case ui` and `--case all`, hook tests and previous native quantity
  acceptance. Record failures honestly; a screenshot alone is not input proof.
- [ ] Commit `feat: render native Linux AP Mail panel` after review of evidence.

## Task 7: Performance, production patch and packaging

**Files:** modify `tools/enhanced_hooks.py`, `tools/build_enhanced_probe.py`,
`tools/build_release.py`, `tools/verify_release.py`, installer hash/upgrade lists
and associated existing tests. Regenerate `tools/enhanced.patch.gz` only through
the existing verified build/delta tools. Add new Python files to the explicit
APWorld source list and matching publication assertions.

- [ ] Add missing-file/capability/upgrade tests before changing production lists.
  Add a native stress fixture of 1,000 open/close cycles and 100 simulated room
  transitions. After warm-up, require stable owner/handler/surface/handle counts,
  bounded arrays and no unbounded background tasks. Measure frame/tick timing
  separately from Mail polling and record distributions, not just one average.
- [ ] Compose exact Mail hooks with current enhanced transforms, preserving the
  earlier tick optimization. Add compile/reopen assertions for every new hook.
  Re-run all native production, recipe, quantity and Mail cases against originals.
- [ ] Build a fresh scratch production candidate; round-trip its delta against
  the verified original. Update hash pins together only after byte parity passes;
  retain prior supported release hashes for upgrade/restore, including 1.5.1.
- [ ] Use the existing installer ownership policy for Mail runtime files; no
  broad deletion of the mod directory or saves. Verify unknown binaries, missing
  backups, alias paths and transaction interruption still refuse safely.
- [ ] Run complete verification:

```text
python -m unittest discover -s tests -q
python tools/build_release.py
python tools/verify_release.py
git diff --check
```

Build release artifacts in a fresh candidate staging copy when preserving older
local artifacts is necessary. Do not call a build a publication, replace public
assets, change release version or run live installers without separate authority.

- [ ] Verify package excludes native authored/extracted GML, full game binaries,
  proprietary fonts, raw recipes and internal planning documents. Confirm all
  new required Python modules and player documentation are included.
- [ ] Commit reviewed production/build changes as
  `feat: package verified native Mail support` without unrelated earlier edits.

## Task 8: Linux acceptance and player documentation

**Files:** update `docs/linux-proton.md`, `README.md`, `CHANGELOG.md`,
`word_factori/docs/setup_en.md`; create `docs/testing/linux-mail-acceptance.md`.

- [ ] Record a matrix with explicit pending/pass/fail evidence for X11/Wayland,
  fullscreen/windowed, native/Flatpak Steam installation paths, resize/scaling
  and reconnect. Windows probe results remain a separate column and cannot turn
  a Linux pending entry into a pass.
- [ ] Supply a reproducible two-player test configuration using existing YAML
  options: enable recipe checks, progressive machines and three Type-a-Word
  targets. The second player supplies remote deliveries/chat. Verify factory
  completions, duplicate checks, reconnect, all Mail tabs and victory.
- [ ] Publish no test room automatically. Run locally where a Linux environment
  exists; otherwise leave the matrix pending and give Jack a private/redactable
  tester checklist. Do not ask for personal installation paths in public chat.
- [ ] Explain the unchanged one-ZIP installer, credentials in the regular client,
  Mail controls, offline/uncertain-send states and fallback. Mark Linux Mail
  experimental until actual acceptance evidence supports stronger wording.
- [ ] Link current evidence and document any manual gaps. Do not claim the full
  official-release client requirement has been waived.
- [ ] Run documentation/package verification and final full suite after all
  edits, then review the complete diff against the approved spec. Commit docs
  separately where possible. Keep the branch; merge, installation and release
  publication require Jack's separate instruction.

## Review checklist and handoff

- [x] Every spec requirement maps to a task above: appearance/input (1,6),
  ownership/transport/errors (2,3,5), authoritative presentation/actions (4),
  performance and packaging (7), real platform acceptance and simple setup (8).
- [x] Function names/types in producer/consumer tasks agree.
- [x] No unidentified native site is treated as already verified.
- [x] Each task has a red/green test cycle and its own evidence/review checkpoint.
- [x] No current Windows behavior or progression rule is silently replaced.
- [ ] Preserve failed-probe evidence and report genuine blockers without
  requesting user guidance on routine engineering choices.

Execution stays inline. The first checkpoint reports Task 1's actual native
feasibility results before production implementation continues. A later Linux
acceptance blocker does not prevent completing safe Python/native-scratch work,
but it prevents claiming that Linux AP Mail has been playtested or is stable.
