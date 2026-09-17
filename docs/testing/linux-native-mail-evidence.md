# Native Linux AP Mail feasibility evidence

## Current checkpoint — 2026-09-17

The chronological notes below retain failed experiments and earlier blockers.
This checkpoint supersedes their status, not their evidence. Task 1's bounded
native/input feasibility gate passed before production work continued. A 1.6.0
tester candidate is now being prepared; real Linux rollout acceptance remains
pending and is tracked in `linux-mail-acceptance.md`.

- Protocol, transport, adapter and Linux lifecycle modules are implemented and
  packaged. Windows retains its overlay; the Linux installer owns a separate
  enabled marker and capability receipt.
- The final isolated `all --live-bridge` case passes **50 assertions**, exits 0,
  and runs a real Python transport/adapter concurrently with the native runner.
  It displays the authoritative TEST target, submits exactly one chat message,
  and receives one matching acknowledgment. There is no AP server in this test.
- Real wire tests caught runner-specific decoding: JSON booleans become real
  0/1 and null becomes `pointer_null`. The bridge normalizes nullable fields and
  accepts only decoded 0/1 flags; Python retains strict wire-type validation.
  Numeric native headers are emitted as JSON integers. Tests include actual
  JSON parse/stringify round trips, not just in-memory native structures.
- One test-fixture scoping defect was corrected: access stubs must be global,
  like production helpers, so early oInput polling can call them. Host-bound
  stubs had falsely produced intermittent polling failures. Failed runs remain
  scratch evidence; they were not accepted as passing.
- Native UI covers all tabs, rejected-action status, Older/Latest history, one
  send per press, capture/dismissal, room/focus resets and bounded 1,000 toggles /
  100 epochs. This is not a sustained memory or FPS measurement.
- Python history tests cover byte-limit trimming without gaps, reserved space
  for 32 acknowledgments, returning to Latest, and queued-popup advancement.
- A combined production patch compiles/reopens **42 code entries**. Its delta
  round-trips byte-for-byte against the verified original. Patched SHA-256:
  `0284cbb72e966e79f3b4878f2a78d0c9331bab54d3c3780f79364cd912a94d1a`.
  Delta SHA-256:
  `ec5ac3a3f8d72f71e984dae421ee57d0901ea38970fdb4355a69d6714ef887c5`.
- Separate fresh native regression cases pass **99** enforcement/quantity and
  **8** recipe-loading assertions, each with clean exit. These isolated fixtures
  are distinct from a connected full production-patch playthrough.
- Client snapshots/manifests use atomic replacement. The verified game runner
  cannot rename over an existing file: native hello/request writers delete only
  their fixed ephemeral destination then rename a complete temp record. Readers
  can see missing and retry, never a partial write; this is **not** an atomic
  filesystem overwrite and is not used for game saves.

No live installer, save modification, push or publication was performed for this
checkpoint. Actual Linux/Proton, connected multiworld, long-session performance,
and complete production-panel visual acceptance are still open. The earlier
full-object manual checks exercised the developer panel/input architecture;
they must not be relabeled as a full production Linux UI playthrough.

Date: 2026-09-16. Status: **partial feasibility proof; rollout gate NOT passed**.

This is developer evidence, not installation instructions or a shipped feature.
The approved design and implementation plan remain authoritative. Production
Mail transport, client integration, installers and release assets are unchanged.

## Verified here

- Baseline: 676 unit tests passed, two skipped before changes.
- Latest sequential regression run: 699 tests, zero failures/errors, two skipped
  (93.610 seconds), including full-copy external API isolation, factory comparison, crash rejection, mandatory
  teardown evidence, editor evidence/refusal checks and quiet-child error-mode
  validation. The fresh pre-editor baseline was 693 tests (75.040 seconds).
  No native probe was running during this run.
- Fifteen new hook/runner tests were written red, then passed. They cover malformed
  hook inputs, literal-safe reader rewriting, duplicate/changed hook rejection,
  missing compiled calls, incomplete native results and pre-write refusal.
  Interactive results additionally require all four real keyboard assertions;
  omitting any one is rejected even if every automatic assertion passed.
  Factory comparison rejects changed timing/journals and a native crash cannot
  pass validation merely because the assertions printed before shutdown passed.
- A SHA-256-allowlisted original was inventoried privately. Thirty-five native
  entries contain the relevant readers or lifecycle/draw hooks. The repository
  contains their names and hashes only, not extracted game source.
- All 35 transformed entries compile and reopen with their expected Mail calls.
  This structural check is separate from the stripped runtime fixture.
- Twenty-five assertions pass in the actual Windows GameMaker runtime. They
  cover mapped key and mouse consumers, the real clickable-state dispatcher,
  text-buffer suppression, immediate local open/close, tab switching, dismissal
  press/hold/release consumption, restored input, simulated focus loss, the
  native room-start reset and measurement with the installed `fFredokaOne` font.
- The desktop scratch window displayed the left red Mail button and native font.
  No replacement font, game binary or extracted code was added to source control.
- The real desktop keyboard check passed with Jack holding A while Mail was open:
  one press, 108 held frames, one release, and zero events reaching the instrumented
  native consumers. All 29 assertions passed (25 automatic plus four real-input
  assertions). This was a stripped native fixture, not a populated factory.
- Earlier desktop inspection exercised actual button opening, Items/Chat tab
  changes, wheel input, draft entry, dismissal and minimize/restore focus loss.
  These observations supplement the assertions; they do not prove original
  factory event ordering or Linux/Proton behavior.
- All 99 existing native quantity/enforcement assertions passed separately. This is
  baseline regression evidence, NOT proof of Mail plus a running factory.

## Factory comparison and scratch shutdown correction

The new `--factory` probe stages native `Building`, `LetterPipe`, `doTick`,
goal production and completion-journal functions. It advances one native tick
per engine Step with deterministic input; full placement/UI object events are
still disabled. External save/achievement/network calls use scratch-only no-ops
and a fresh in-memory journal. It never loads a player save.

Both observed runs completed ten `II` words in 21 ticks/21 frames with the same
journal and idempotent completion. Mail stayed open during the open-panel run.
Before the teardown correction below, the scratch runtime intermittently exited with `0xC0000005`
(3221225477) after printing its assertions during native shutdown. These are
**not accepted runs**. One clean exit did not reproduce reliably.

Removing the final test-authored instance destruction did not reliably fix the
failure. Splitting closed/open comparisons into fresh game processes also did
not fix it: the closed-panel process still failed during shutdown. The runner
now records the exit code and rejects that process before running the open-panel
case or creating an accepted comparison. Failed logs remain in private scratch.
The single passing earlier run is not used to clear the gate.

Fresh controls after this failure: the existing native enforcement/quantity
probe passed all 99 assertions with exit 0, and the Mail-only probe passed its
25 assertions with exit 0. The initial defect was not yet localized beyond the combined
factory fixture/lifecycle. Neither a production regression nor an engine bug
has been established. No live installation contains these exploratory hooks.

### Shutdown investigation and desktop protection

The probe launcher now sets an inherited, process-local Windows error mode
(`SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX`)
only while spawning its scratch child. It restores the parent mode even when
creation fails. It does not change the registry, system-wide crash reporting,
exception handling, exit-code validation, or the player client. Two executable
regressions verify inheritance and restoration. Diagnostic children still
returned `0xC0000005` without waiting for a fault dialog.

Private differential runs ruled out several proposed fixes. Releasing the
factory graph, recompiling its constructors, retaining the control instance,
changing method-call context, using unique method names, assigning outcome
fields separately, and importing each object event only once did **not**
establish a reliable clean exit. No such change was applied to the integration.
Removing drawing or individual production phases also retained the failure.
Do not reuse a small successful sample as evidence that one of these works.

Twenty-run controls each exited cleanly with factory execution disabled, with
setup only, and with recipes only. Additional twenty-run controls kept the
no-factory and setup-only hosts alive for 110 frames; both remained clean.
These are bounded observations, not proof of the root cause.

A debugger observing only its own scratch child reproduced a shutdown access
violation in an internal linked-list operation. Registers and the referenced
allocation contained Windows freed-heap markers. This establishes an invalid
freed-memory access in that fixture, not which component originally corrupted
its lifetime. A reduced fixture calling only the completion-condition method
also reproduced under the debugger. Production timing and Mail drawing alone
therefore do not explain the failure. Private register captures and code
inspection are diagnostic evidence only; no native addresses are patch targets.

Further reduction reproduced the same fault without Mail, recipes, simulation,
or method calls. An initial nested-struct theory was refuted when an extended
empty-method baseline crashed on attempt 14. Reordering nested code/scripts,
removing global initializers and replacing zero-length stubs with explicit exits
also failed. None of those speculative changes is part of the fix.

The accepted scratch-only correction ends the fixture in two phases: stop its
frame work and explicitly destroy the host-created instances, then let three
normal engine steps elapse before the host's Alarm event reports and quits.
The native assertion requires that only the host remains. All original runtime
object lifecycles remain disabled; this is not cleanup code for a player game.
No simulation/completion body changed, no exception is swallowed, and exit 0 is
still mandatory after the result. Missing teardown evidence is now rejected by
a red/green regression test.

Private lifetime reproductions passed 40 consecutive debugger launches each
for the minimal control and closed-panel factory after this correction. The
rebuilt Mail-open factory passed another 40 consecutive debugger launches.
Ten further ordinary-launch pairs (20 processes, without a debugger) each
passed all 32 comparison assertions with clean exits. Private evidence is under
`mail-factory-orderly-v1`, `mail-debug-orderly-open-v1`, and
`mail-orderly-normal-v1`; earlier failing captures remain separate.
The fresh paired build passes 32 combined assertions: 26 input/teardown and six
factory comparisons. Both modes produce ten `II` words in 21 ticks/21 frames,
with equal journals and idempotent completion. These are bounded Windows
observations; the underlying runner's internal lifetime defect has not been
fully established, and this is not evidence of a live-game or Linux fix.

The shutdown blocker is cleared for this bounded fixture. The full native Mail
gate remains unpassed: original editor-event isolation and platform acceptance
below are still pending. Do not force-terminate a successful-looking process or
accept its printed assertions if the native process fails.

## Actual hook findings

The shared input sampling entry is `oInput` Begin Step (`Step_1`). It updates
mouse instances and clickable state, then maps input. `checkInputFuncs` exposes
mapped keys, mouse state and a text buffer. Clickable objects bypass the normal
input-access lock. Several consumers also read raw engine keys/buttons/wheel
directly, including factory controls and other Begin Step events. Therefore a
lock or a guard around the simulation tick alone cannot isolate Mail input.

The exploratory transform guards shared accessors and clickable state, redirects
raw reads through delegating wrappers, and preserves simulation bodies. It also
guards the console and word-entry consumers of buffered text. Early readers are
blocked on an opening button/F8 edge, before the shared sampler runs. The chosen
draw site is `oCursor` Draw GUI End (`Draw_75`); room-start and cleanup sites are
on `oInput`. Native resources establish the font identity without distributing it.

These are **candidate hooks**, not a production patch. Their full event ordering,
drag state and text-buffer lifecycle still need the tests below. In particular,
the development fixture enables its own UI, does not implement an AP handshake,
and must never be offered as a playable patched game.

Additional source audit: native `oControl` editor modes continue moving dangling
machines and can retain an eraser-held state without a new input edge. Reader
wrappers alone therefore do not establish editor isolation. The bounded native
regression below now reproduces those paths; no such change has been shipped.

## Existing-drag and eraser regression

The new separate `--editor` fixture compiles the complete verified `oControl`
Step body into a method, invoking it with controlled state. It uses the actual
native move, resolve-move and eraser methods. The private staging substitutes
the rotation-widget reference with a fixture widget; hover lookup, intended
move position, visual animation and graph callbacks are explicit test boundaries.
It does not restore the original startup, save, cloud or network lifecycle.

The red run (`mail-editor-red-v3`) exited normally but failed five assertions:
an existing drag moved behind Mail, dismissal did not protect that drag, and the
retained eraser deleted the fixture line. Positive controls established that
the native move and eraser paths executed before capture. Earlier fixture setup
errors (missing physics world and incorrectly bound test methods) were corrected
before accepting this red result; those errors are not regression evidence.

The candidate guard runs at the start of the native editor Step. It clears the
eraser latch and suspends editing while Mail owns input or the window lacks
focus. It preserves the pending gesture, rather than silently placing or deleting
it. After dismissal and release, a fresh press is needed to resume a suspended
gesture; the following normal release commits a desktop drag exactly once.
Disabled Mail releases this guard. Verified simulation, pause and completion
modes continue through their native Step, so the panel does not pause production.

Fresh `mail-editor-green-v2` and ten consecutive ordinary relaunches each passed
41 assertions (26 input/teardown plus 15 editor checks), with exit 0. Coverage
includes real instance movement, the native eraser's deletion callback, dismissal
press/release, fresh-press recovery, one snapshot on normal drag completion,
simulated focus loss/return, disabled-UI recovery and native Step tick dispatch.
A private mutation removing the simulation-mode exemption correctly failed the
production-dispatch check. Results are retained in `mail-editor-verification-v1`.

The editor fixture counts dispatch to `doTick`; it is not itself a production
output test. The separately rebuilt `mail-editor-factory-v1` comparison passes
all 32 assertions, producing ten words in 21 ticks/frames in both modes, with
equal journals and idempotent completion. These complementary tests remain
bounded Windows evidence, not proof of full original-object event ordering,
physical middle-button/laptop gestures, viewport behavior or Linux/Proton.

The installed game and original-backup hashes remain unchanged, and no native
test process was left running. The changes remain uncommitted Task 1 work;
there is no production delta, release asset, installer or player-save change.

## What remains unproved

- Exhaustive physical gesture/modifier combinations, paste/Unicode/IME input,
  and production-panel behavior; the later full-object checkpoints below cover
  basic placement, typing, tabs, wheel, capture/resume and focus recovery.
- Arbitrary resize, mixed display scaling and a supported minimum-resolution
  policy, beyond the particular windowed/fullscreen/smaller-viewport checks below.
- Full-game simulation-speed equivalence, beyond the bounded native tick
  comparison; full-object completion with Mail open is now observed below.
- Production bridge/UI composition, all final-panel input paths and stress.
- Linux/Proton behavior, including X11/Wayland and native/Flatpak installations.

An earlier interactive check stopped on concurrent user input. After Jack resumed
testing, desktop checks continued and the physical-key test passed. No input was
forced into another application. The retained result still marks
`manual_input_validated: false` and `gate_passed: false`: the wider factory and
viewport acceptance checklist is not complete. Do not interpret the keyboard
success as passing that wider gate.

## Reproduce privately

With the existing developer Python and verified UndertaleModTool CLI:

```text
python -m unittest tests.test_native_mail_hooks tests.test_enhanced_hooks -v
python tools/run_mail_native_probe.py --cli <cli> --original <verified-original> --runtime <game-directory> --output <fresh-private-scratch>/mail-input --case input
python tools/run_mail_native_probe.py --cli <cli> --original <verified-original> --runtime <game-directory> --output <fresh-private-scratch>/mail-factory --case input --factory
python tools/run_mail_native_probe.py --cli <cli> --original <verified-original> --runtime <game-directory> --output <fresh-private-scratch>/mail-editor --case input --editor
```

The output must be outside every repository and the game installation, under an
existing scratch parent. Aliases/reparse points, existing output and unrecognized
original binaries are refused before extraction. Each test has a unique save
namespace and result nonce. Runtime/network/save object events are stripped in
the acceptance copy. All proprietary artifacts stay private in that directory.

Run the full Python suite **after** native probes have exited, not concurrently.
Installer tests intentionally refuse installation while any Word Factori process
is active, including a scratch probe. A concurrent run reproduced that guard;
no installer protections were relaxed to accommodate the test harness.

`hooks-only.win` is a compile/reopen artifact and is never executed. The separate
`game` copy runs only the authored host and selected native consumer functions.
`result.json` records hashes, hook names and assertions. `supported: true` means
the bounded automated fixture passed; **`gate_passed: false` remains explicit**.

Add `--interactive` only when the desktop is available for testing. F10 ends
inspection; its real raw-key assertions require holding A for about two seconds
and releasing it while Mail is open, then pressing F10.
This alone is not the populated-factory test. `bridge`, `ui` and `all` cases
deliberately reject execution until implemented. There is no AP connection.
`--factory` runs closed/open subcases in separate private processes and refuses
combination with `--interactive`. It validates orderly fixture teardown and
normal process exit as well as production equivalence. It is a bounded developer
test, not the full acceptance gate.
`--editor` is also a separate deterministic case and rejects combination with
`--factory` or `--interactive`. Every named editor assertion is mandatory, not
just the presence of a successful result flag.

## Failed probes retained privately

The initial host used `window_set_visible`, which this runner does not support;
removing that call fixed startup. A same-frame `keyboard_key_press` assertion
also failed. Automated short key taps subsequently recorded press/release edges
but no held frame; they correctly failed the held-key assertion. Synthetic engine
key injection was removed because it can affect another focused Windows window.
The later physical-key test recorded all three states successfully. These failed
attempts and their output remain in private scratch evidence, separate from the
passing result.

## Full-object desktop checkpoint

A separate private full-game copy now preserves the original rooms, editor,
widgets and object lifecycles. It is not the stripped fixture described above.
It uses a unique scratch save namespace and the native no-op base cloud client.
Developer-only rewriting neutralizes external game API calls and first-class
function references; a reopened bytecode audit found zero remaining references
to the audited Steam/HTTP/network/external/URL/process-launch APIs and zero
active extension initialization/cleanup entrypoints. Three red/green Python
tests cover calls/references, literal preservation and interpolation refusal.
This audit is not a claim that the runner/Steam process makes no OS-level network
traffic. The original debug text `NETWORK REQUEST` still prints, but its compiled
call targets the scratch no-op. No real cloud client or player save is used.

Full-object runs also install a scratch-only unhandled-exception logger that
exits nonzero without GameMaker's modal error form. Windows process-local fault
dialog suppression alone did not contain GameMaker's own error forms. This
handler does not turn an exception into a passing run or ship to players.

The resumed `mail-full-v5/desktop-run-3` ended through its nonce-bound F10 finish
marker, followed by normal process exit 0. It did not require fixture-specific
object destruction. The following are observed desktop checks, supported by
periodic native room/mode/module-count/draft/viewport records, not assertions
from the debug `Native consumers: 0` label (that label is not instrumented for
full-game consumers):

- One click opens Mail over the native menu. Chat then Items changes the selected
  tab without closing the panel.
- An outside dismissal click over native Play closes Mail without opening the
  level selector. A fresh click opens that selector and the I tutorial loads.
- F11 changes the window from 1920x1080 to 2560x1440 fullscreen, with the native
  GUI remaining 1920x1080. Mail and Chat hit tests work at their scaled visible
  positions. F8 closes Mail; F11 restores windowed mode.
- A physical-style `a` key enters the Chat draft. Scrolling changes Mail's
  scroll value without a visible factory zoom. Generic text injection did not
  enter text; this is not accepted as paste/Unicode/IME coverage.
- With Mail closed, the native I hotkey starts a pending machine placement
  (mode 3, two modules including the target). Opening Mail, entering `i` in Chat,
  and dismissing outside retain that mode/count. A fresh factory click commits
  placement (mode 0, still two modules). This directly exercises the capture
  guard in the original object event, beyond the bounded editor assertions.

Limitations from this run are deliberately retained: automated palette drags
and wire drags did not create the expected actions, while keyboard-started
placement worked. The cause is not established (input timing, hit testing or
integration behavior); do not call dragging passed or fix it by guessing.
Dragging the window corner did not change its dimensions, so arbitrary resizing
and minimum viewport acceptance remain pending. Fullscreen is the only verified
viewport change here. No connected factory completion was exercised in this
full-object run; the deterministic paired production fixture remains separate.

Earlier full-object attempts are not counted as passing: a missing Steam app ID
exited before readiness; a sandbox-restricted startup could not initialize its
scratch files; a diagnostic structure field named `room` collided with an engine
builtin and failed. Renaming only that diagnostic field to `room_name` corrected
the instrumentation error. The original full-object run exited without the F10
marker, and the interrupted follow-up has no accepted finish. The private
launcher now requires both the exact finish marker and exit 0, and preserves each
run in a new directory. All failed/incomplete logs remain private.

## Next checkpoint

Follow-up diagnostic (private `mail-full-v6`):
an authored resize to a 1280x720 client viewport preserves the native 1920x1080
GUI coordinate system. Mail opens at the visibly scaled button, Chat switches
without closing, and F8 dismisses it. This verifies that particular smaller
viewport, not arbitrary OS dragging or a production minimum-resolution policy.

Raw input logging narrowed the automated-drag gap: for a palette-to-grid drag,
the first engine-observed press was already at GUI (1213,748), the destination,
not at the palette near (1776,922). The palette's pressed flag was false and the
hit was `none`; the next observation released at the same destination. Repeating
with Mail explicitly disabled produced the same trace and `blocked:false`.
The automated gesture therefore does not exercise the intended native palette
drag. Do not infer a Mail regression or weaken the capture guard from this
automated result.

Jack subsequently confirmed that both physical actions worked in the reopened
isolated window: dragging an I factory from the palette onto the grid, then
connecting its output to the target. This is user-reported manual evidence,
not an automated drag assertion. The `mail-full-v6/manual-drag-run-1` log records
two modules in editing mode. The process exited with code 0 before the follow-up
production check, without the required F10 finish marker; its run record
therefore correctly has `finish_observed: false` and is not an accepted complete
probe. The manual observation remains useful, but does not establish production
with Mail open, simulation equivalence, or Linux/Proton behavior.

### Full-object production follow-up

The fresh `mail-full-v6/production-run-1` reopened the scratch I level with
Jack's placed factory and connection intact. The target counter was initially
zero. Play started native production; F8 then opened Mail, which remained open
through the native completion screen. Periodic logs record mode 4 (production)
and later mode 6 (complete), both with `open:true` and two modules. Closing Mail
revealed the I result: one building, zero overflow, two cycles per box.

F10 emitted the exact nonce-bound finish marker, and the process exited 0.
The launcher accepted this run (`finish_observed:true`), with no recorded
`WF_FULL_EXCEPTION`. This establishes completion while Mail remains open in
the original-object Windows scratch game. It does not measure full-game speed
equivalence or verify AP delivery, since the probe has no AP connection.
The installed binary and original-backup hashes were rechecked and unchanged.

### Full-object focus and smaller-viewport follow-up

`mail-full-v6/focus-run-1` loaded the connected I factory with two modules.
Typing `i` into Chat changed the draft without starting placement. Minimizing
the game through its title-bar control produced native log rows with
`open:false`, an empty draft, editing mode 0 and the same two modules. Restoring
the window left Mail closed. With the pointer returned to the grid, a fresh I
shortcut started placement and a fresh click committed one new factory. Mail
then reopened normally with an empty Chat draft. No other application received
test input.

While Mail was open, the scratch F7 resize changed the client viewport to
1280x720, retaining the native 1920x1080 GUI. Clicking the visibly scaled Items
tab switched from Chat without closing. Clicking outside over native Play
closed Mail but did not start production: logs retained editing mode 0 and
three modules. This is a particular authored resize, not an OS-corner-drag,
mixed-DPI or arbitrary minimum-resolution test.

F10 finish and process exit 0 were both verified; there was no recorded native
exception. These observations establish basic full-object focus recovery and
scaled hit testing on Windows, not every modifier/gesture/platform combination.

Basic physical placement/connection, production with Mail open, focus recovery,
fullscreen mapping and a smaller viewport are now covered by separate manual
and observed checks. Review the bounded Task 1 checklist against this combined
evidence before starting the client bridge. Full UI acceptance still needs
production-panel layout/text, additional input/viewport combinations, stress
and actual Linux/Proton tests; none is implied by this developer panel.
Do not proceed with production wiring or declare Linux AP Mail ready based on
the current fixture. No installed game, player save or published release changed.

The full-object safety audit above supersedes the earlier startup-audit blocker.
The full-object scratch driver remains private research tooling, not a shipped
installer or the supported acceptance-runner interface. The bounded feasibility
checkpoint and the later full-UI/rollout gates must be tracked separately.
Windows results never substitute for Linux/Proton acceptance.
