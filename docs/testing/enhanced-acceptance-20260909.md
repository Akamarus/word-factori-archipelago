# Enhanced integration: local evidence, 9 September 2026

## Scope and release status

Opt-in development playtest, not public-release acceptance. No changes were
installed into Jack's Steam game or existing saves. Its original `data.win`
hash was rechecked after the native tests and still matched the allowlist.

The final Python suite passed 374 tests. Release verification passed source
parity, JSON/index integrity, fresh recipe derivation, and data exclusions.

## Generation

40 actual AP 0.6.7 generations passed: Core and Discovery, count and final
goals, seeds 22000–22009. Each was independently replayed against recipe
requirements, region tiers, page thresholds, and stable location identities.
Evidence: local `tests/output-enhanced-20260909/matrix.json`. The matrix writer
labels that file `matrix_in_progress` even after all rows finish; the summary
has 40 completed, 40 passed, zero failed. No visual playthrough is implied.

## Native engine

Original SHA-256:
`d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978`

Final patch SHA-256:
`fb95c2ab10896a7e62ffa92788389d21b1b6378b7afe73b4b3307a127dfc87d8`

The patch was compiled and reopened using UndertaleModTool 0.9.2.0. The
authored harness `tools/native_runtime_acceptance.gml` ran in an isolated copy
of the actual game runner. Its game name/save directory was changed only in
the harness copy to `wf_ap_native_acceptance_20260909`. The regular game
startup and unrelated UI dependencies were substituted. The real patched
button method, native secret check, threshold function, and module-count hook
were retained.

Final native run: **33 assertions passed, process exit 0**. This includes all
six first-page button positions, visibility/UI-state guards, native room
acknowledgement, four/six thresholds for enhanced/vanilla, new machine counts,
unchanged loaded baseline, duplicates, wrong-room/layout/target, stale
revisions, challenge caps, and quiet missing/malformed runtime handling.
A review regression first failed for acknowledgement retry after a write
failure. The corrected hook retries after a five-second cooldown without a
campaign reload; both retry and cooldown assertions now pass in the runner.

The earlier harness exposed two cap failures and a GameMaker struct-literal
issue with the reserved `room` key. Both were fixed and exercised again.
The failed acknowledgement test opened missing-file/error dialogs; these
were from the isolated copy, not the installed game. The runtime now uses a
quiet loader, and the harness has bounded process termination on a stall.
One earlier immediate-startup/exit harness run returned an access violation
after writing passing results; three repeats and the final expanded run
exited cleanly. This is retained as a live-test watch item, not dismissed.

## Installer

On an isolated exact-original copy, Windows PowerShell 5.1 applied the delta,
the Python client verified the installed patch receipt and file hash, and
restore returned the file to the exact original hash. The final r2 archive's
installer also passed a repeated install before restoration. Its 23 payload
file hashes matched the playtest manifest. Unknown builds are covered by an executable
PowerShell regression test. The backup is retained; no game save is modified.

## Still required before public release

Run a full normal-screen session with a live AP server: select the new room's
empty save, verify the shuffled first page, complete four levels in a different
order, advance with two unfinished, receive progression while in a factory,
return to Levels and enter another factory, reconnect, and finish the goal.
Also watch shutdown behavior and verify restore after the playthrough.
