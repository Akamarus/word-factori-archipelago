# Type-a-Word native completion evidence

## Scope and result

2026-09-15, verified original SHA256
`d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978`.
The final isolated probe compiled, reopened, and exited with code 0.
All **21 native assertions passed: 15 native_function and 6 native_production**.
This is completion gate evidence for controller review, not an enabled feature,
AP enforcement acceptance, UI playthrough, Steam acceptance, or release.

The two-I-source factory produced ten `II` words after 21 native ticks. Before
the tenth word, the journal remained incomplete. The native win caller recorded
`II` without any campaign credit, then ignored its duplicate call. No produced
letters, goal counts, completion flags, or successful win statistics were injected.

## Reproduce safely

Run `python tools/run_type_word_native_probe.py --cli PATH --original PATH --runtime PATH --output PATH`.
The official UndertaleModTool CLI and exact allowlisted original are required.
`--runtime` is the directory containing the executable and base assets. The runner
discovers its executable, refusing ambiguity. `--output` must be unused beneath
an existing caller-selected scratch directory outside the repository and runtime.
Existing destinations, links/reparse paths, missing inputs and overlapping paths
are rejected; unsupported original bytes fail before writes or subprocesses.

The test copy uses `GeneralInfo.Name = wf_ap_typeword_probe_20260915` and checks
`game_save_id` before harness file reads. It creates new in-memory identity slots,
never loads a user save, and never installs anything. Only base runtime files are
copied; installed `data.win` and mod directories are excluded. The launched copy
has a scratch working directory, hidden startup, and a 40-second timeout. Only
its exact process handle can be terminated. Errors and timeouts remain failures.

Results use native `json_stringify` and a fresh per-run nonce in captured stdout.
The runner accepts exactly one matching result and writes it into the unused
scratch output. This avoids GameMaker's routing of file writes to LocalAppData;
a stale result in the fixed probe namespace cannot satisfy a later run. The JSON
contains schema 1, the save namespace, labeled assertions, snapshots, stubs and
native source digests. Raw native logs and source remain outside the repository.

## Observed completion shape and lifecycle

These are synthetic probe values, not a user's save:

| Scenario | Native journal observation | Evidence |
|---|---|---|
| Fresh slot / open `II`, index -1, mode 3 | Empty `words` and `beaten_levels` | native_function |
| Literal win `(2,8,0)` | `words.II` has buildings 2.0, cycles 8.0, extra_letters 0.0 | native_function |
| Improved win `(1,6,0)` | Same key; individual minima become 1.0, 6.0, 0.0 | native_function |
| Campaign `II`, index 0, mode 0 | Same word key and minima; `beaten_levels["0"] = 1.0` | native_function |
| Hard `II`, index 0, mode 1 | Separate `II_hard` score entry; ordinary `II` remains | native_function |
| Another target `III` | Independent key; existing entries retained | native_function |
| Two physical I sources into `II` goals | `words.II` recorded; `beaten_levels` empty | native_production |

The word value is a score object, not a boolean. Native JSON emits numeric scores
as floating-point literals. The JSON stringify/parse roundtrip retained the slot
shape and scores. The normal on-disk save writer was inspected and uses the same
native serializer, but **native disk-save/restart persistence was not exercised**:
normal identity/cloud/save initialization is disabled. No claim of restart or
connected-client reconciliation follows from these results.

`_hard` is a separate native score identity. It must not be removed blindly from
arbitrary input or treated as an additional selected word. A free win creates no
`beaten_levels["-1"]` entry. The journal alone does not identify the launch mode,
which supports the approved word-production semantics across legitimate modes.

## Entry and input behavior

The original input-box step's filtering/case/truncation block was executed, not
replaced by `setLevel` calls. In vanilla context it accepted ` ii ` as `II`,
`abcdefghijkl` as `ABCDEFGHIJKL`, and truncated 17 letters to 16. It accepted
`A1 B!` as `A1B`: `1` belongs to the game's accepted special characters.
The unmodified `EnterInputBoxGame` accepted the 12-letter value at index -1,
mode 3, without adding a completed word. It ran last because it queues a room
transition. This does not mean the subsequent room UI was played.

The approved order-list parser remains stricter: 2–12 ASCII letters with only
surrounding whitespace trimmed. Native filtering is not equivalent to that rule.
No AP-mod input normalization or free-word machine enforcement is proven here.

## Native source references and simulation boundaries

All references identify locally extracted entries from the verified original;
no proprietary excerpts are distributed.

- `gml_GlobalScript_LevelFuncs`: `setLevel`, `beatLevel`, `isLevelBeaten`,
  `updateLocalScoreAndMakeUpdateStruct` retain their native completion logic.
- `gml_GlobalScript_LoadConfig`: native `refreshRecipeList` prepares source
  recipes; `refreshWordList` refreshes the completed-word list.
- `gml_GlobalScript_Building`: native `Building.consume`, `progressPipes`,
  `produce`, and `LetterPipe` move real generated I letters and validate goals.
- `gml_Object_oControl_Create_0`: native `doTick` and `try_win_condition` form
  scores only after native goal production reaches ten words. The normal step
  event's invocation is replaced by a bounded synchronous loop.
- `gml_Object_oFinalWordMain_Create_0`: native `produce` consumes goal counts and
  accumulates completed words. Counts start at zero. Goal Building tags select
  the two I positions. No success condition is replaced.
- `gml_Object_oInputBox_Step_0`, `gml_GlobalScript_MenuFuncs`: actual input
  filtering and `EnterInputBoxGame`; native default input limit is 16.
- `gml_GlobalScript_writeJsonFile`: inspected native serialization boundary;
  output transport uses native JSON plus captured stdout rather than disk save.

The graph has no visual line objects, so native score averaging yielded cycles
0.0, buildings 2.0 and extra_letters 0.0. That cycle value is a simulation
limitation, not a normal gameplay score. Literal-score tests separately prove
score minima and serialization. The native factories generate their own I
letters; the runner never preloads successful letters into the pipes.

## Exactly what the test copy replaces

All ordinary object event bodies are blanked before the listed harness events
are added. This disables ordinary room UI/control startup, identity save loading,
cloud sync, notification UI and background event work. Authored initialization
creates only the required identity, input, control, goal and I-source state.
I-source module presentation is replaced with forwarding to native
`Building.produce`; letter visual spawning is omitted. Goal output visual objects
have empty events. Native completion and pipe functions remain in the copy.

Identity achievement and sync methods are recording stubs; extended achievement
fields return an empty test list. `LevelFuncs` calls to analytics, HTTP and AWS
logging, plus control stamp animation/screen-view calls, are recording stubs.
`__GoogSystem` exits before its cache or analytics initialization. Extension
init/cleanup callback fields are empty, while function descriptors remain valid.
**Steam's DLL automatic initialization still attempted and failed**; it is not
claimed to be stubbed or successful. No Steam login, authentication or cloud
write was performed. Controller accepted that explicit isolation caveat.

## Verification and retained diagnostics

Focused safety tests: initial RED was 9 failures for the absent runner. Function
extraction added one observed RED; nonce transport added two observed REDs.
Final focused run: 12 tests, OK, 1 skip because this Windows session cannot create
symlinks. Existing-output preservation and unsupported-hash tests use real temp
files; subprocess execution is forbidden in the unsupported-hash test.

Final native run: scratch `typeword-native-20260915-r15`; patched SHA256
`c4d457b250aa0906eaa1dff4397d3857f183d0ad9f78608fbe22f003e2b59cef`.
Its nonce makes future patched hashes differ. Earlier failed attempts remain in
scratch, including r11's native input characterization and missing recipe
preparation error, r12's UI-stub binding error, and r14's queued room-transition
ordering error. They are not acceptance evidence. Extension-removal experiments
and timeout/error logs are also retained, without weakening the native win gate.

Full repository suite: `python -m unittest discover -s tests -q` ran 518 tests
in 68.821 seconds, OK with 2 skips (the baseline skip plus symlink privilege).
This change adds only authored development tooling, safety tests and this note.

## Native enforcement gate (Task 2)

The isolated candidate compiled, reopened, and exited 0 on 2026-09-15.
Final scratch: `typeword-enforcement-20260915-r6` under the same external
`probe-tools` directory. The nonce-bound result reports
`enforcement_supported: true`, **50/50 assertions: 40 native_function and
10 native_production**. Patched test SHA256:
`b8ed830420aa4375c385733d01b14e7671e858a31e26c722fff341393e1008f5`.
This is feasibility evidence for review; no distributable patch or production
APWorld, client, runtime snapshot, receipt, or installation changed.

Add `--enforcement` to the reproduction command above. The runner uses the same
verified original, fresh output, GeneralInfo namespace, empty identity,
service isolation, native JSON nonce transport, and exact-process timeout rules.
Missing or false enforcement results fail the runner, even if the test list
otherwise reports success. Reopened output includes all three guarded global
source entries, as well as the harness and native control functions.

### Controls, production, and saved layouts

| Scenario | Observed native result |
|---|---|
| Stock mode 3 with Bender-only limit structure | Merger2 count is -1 (unlimited) |
| Candidate free-word entry, Bender-only snapshot | Bend and I are -1; rotation, reflection, Merger2/3/4 are 0 |
| Locked Merger2 graph built from serialized template | 60 native ticks, zero completed words, no V recipe or word journal entry |
| Same graph after Merger2 receipt and native `setLevel` re-entry | Ten VV words at total tick 79; V recipe and VV scores recorded; no campaign credit |
| Saved graph through lock/unlock | Original serialized layout unchanged; the same native merger Building instance resumes |
| Native custom factory while AP disabled | Produces V; real native timing cache returns 3 ticks for cycle key 400 |
| Same warmed custom factory under AP, full inventory | Repeated native `produce(400)` returns no output; cached timing path and recipe previews blocked; saved template unchanged |

The saved/import fixture is authored JSON with the native template fields
`uuid`, `buildings`, `pipes`, `module`, `tag`, `topo_index`, `from`, `to`, and
`dist`. Native `makeBuildingsFromTemplate` constructs eight actual Buildings
and six LetterPipes: four I sources, two Merger2 machines, and two V goals.
Native source consume/produce creates every I. Native pipes supply both inputs
to each merger, which produces V through the native recipe lookup. Native
`oControl.doTick`, goal production, and `try_win_condition` reach ten VV words
and call native `beatLevel`. No successful letters, goal counts, win flags,
statistics, or journal entries are injected. The loop calls the native tick and
win functions synchronously; this is not a UI save-file load/import playthrough.
Visual line-score objects are still omitted, so cycles 0 remains the Task 1
simulation limitation.

The custom fixture uses native `Building(oCustomBuilding, uuid)`,
`Misc.tagAsState`, `getBuildingTemplateFromUUID`, and
`makeBuildingsFromTemplate`, followed by real nested simulation and cache
population. Cached output was tested after its native warm-up, not manufactured
by setting a countdown or queued letter. Custom production and previews are
**unavailable in AP even with every family owned**. The candidate does not
validate individual custom trees or claim support for unrestricted custom
factories. This conservative restriction preserves their saved layouts and must
be disclosed before any eventual release or installation.

The r2 native RED control used no-op candidate helpers and the same original
simulation. It compiled/reopened/exited 0 but failed 34 of 46 assertions,
reporting `enforcement_supported: false`. Its supposedly locked imported graph
produced 28 VV words in 60 ticks and wrote the V recipe; its warmed custom
factory continued emitting V. This demonstrates that the acceptance detects
the native bypass, not only toolbar presentation. r1 failed compilation due to
an authored array-literal accessor; r3 was the initial 46/46 GREEN and r4 added
integer-token and campaign-cap checks. Controller clarification established
Bender as guaranteed precollected starting equipment. r5 added the fallback
assertion and failed ten native tests; r6 changed safe fallback to I plus Bender
and passed all 50. Only r6 is the final acceptance result.

### Minimal confirmed native hook surface

Seven hook names are reported in the native result:

- `LevelFuncs.get_level_module_counts`: refreshes explicit probe inventory on
  native factory entry; supplies complete limits for negative-index factories.
- `LevelFuncs.get_current_module_count`: removes the mode bypass for AP and
  returns zero for an unowned family even if imported instances already exist.
  Existing finite campaign limits still use native counting.
- `Building.consume`: blocks locked machines before input consumption and both
  native recipe-discovery paths.
- `Building.getRecipe`: blocks recipe/template traversal before its independent
  native journal writes. A blocked result is the native invalid Letter `?`.
- `Building.produce`: blocks cached/queued production, including custom output.
- `Building.getTicksTillProduce`: blocks custom timing/cache traversal under AP.
- `Misc.getModuleRecipe`: blocks direct previews and custom template resolution
  before their native recipe lookup. `tagAsState` and serialized construction
  remain native and unchanged.

The toolbar and production checks use exactly the family module names from
`word_factori.mod.MODULES`. Native rotation/reflection objects map their tag to
the corresponding family variant. I and final-word goal consumption remain
available. Native `getModuleRecipe` returns a Letter with `?` for an invalid
recipe; returning undefined from guarded Building preview calls would violate
the native caller's `.toString()` expectation.

Native assertions cover missing/non-struct snapshots, stale revision, wrong
room/layout, missing family, malformed count, missing context, old word contract,
and old acknowledgment. Invalid snapshots retain a validated snapshot only for
the same room/layout/contract; a new room receives safe I-plus-Bender limits,
preserving guaranteed precollected equipment. The previous-room test first
unlocks Merger2, then proves that unlock cannot leak into the new room. Parsed
client integer tokens for count 0/-1 and revision 9000000001 were accepted.
Finite campaign Bend cap 2 survives; a native Merger2 cap cannot grant its locked
family. Noncampaign modes 0, 1, 3, 5, and 7 obey the same restrictions. AP-off,
vanilla, and another mod retain the native count behavior. The final
recipes-on/orders-off fixture remains restricted. These are explicit native
mode/function cases, not online daily/shared launch-service acceptance.

### Required production migration and remaining limits

The helper accepts an explicit probe-owned gate with context, payload, and last
validated snapshot. It reuses existing `schema`, `mode`, `room`, `layout`, and
`revision` conventions. `probe_family_counts`, `probe_contract`, and `probe_ack`
are deliberately test-only fields. The harness owns its AP-enabled switch and
folder identity. Its `enabled` field is a harness baseline switch only and must
not become an externally supplied production bypass. No production sidecar
loader, automatic room binding, or receipt writer is added or inferred from that
fixture.

A later reviewed implementation must add authoritative per-family inventory and
the word/recipe contract to the existing runtime snapshot, validate its room and
layout before use, preserve campaign caps, and retain safe same-room state on
read/replacement failures. Factory entry is the refresh boundary; no per-tick
disk read is needed. Receipt/native acknowledgment must explicitly advertise
free-word production and recipe enforcement. An older generic enhanced
acknowledgment cannot authorize order reporting or new-client recipe-only
reporting. The player-facing custom-factory restriction belongs in that migration.

Native disk-save/restart persistence, ordinary UI entry/import, connected item
delivery/client checks, tracker play, and Linux/Proton remain separate acceptance
work. Task 1's service limitations are unchanged: automatic **SteamAPI_Init
attempted and failed**, despite cleared callbacks; it is not a successful login
or a stubbed SDK call. No authentication or cloud write occurred. Task 2 adds
only a notification-UI stub around native `saveRecipe`; native recipe writes and
refresh logic remain intact. Normal module presentation forwards to native
Building production; no injected win logic substitutes for production.

Python TDD: four new expected failures before enforcement runner implementation;
then 19 focused tests passed with one symlink-privilege skip. Native r2 RED and
r6 GREEN evidence above is retained outside all Git repositories.
Final full suite after the starting-equipment correction: 525 tests in
58.949 seconds, OK with two skips. No production artifacts were changed.
