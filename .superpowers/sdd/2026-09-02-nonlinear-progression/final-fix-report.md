# Nonlinear Progression Final Fix Report

## Scope

Base HEAD: `af6cef3380fe0026a11600db63455ed0ad4dbcdc`

This fix wave scopes all persisted client state and goal resend identity to a validated immutable room contract, rejects an entire native save observation when any index is outside the authoritative layout, and validates every generated location row against the canonical stable-key/name/AP-ID projection with exact cardinality.

No Word Factori process was launched. No save was read outside the existing automated temporary fixtures, written, moved, or deleted. No external APWorld installation was performed.

## RED evidence

Focused command:

```powershell
C:\Users\Jack\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_core.ClientCoreTests.test_native_slot_translation_rejects_the_whole_observation_on_any_invalid_index tests.test_core.ClientCoreTests.test_bridge_identity_is_room_contract_scoped_and_canonical tests.test_core.ClientCoreTests.test_bridge_identity_fails_closed_without_authoritative_room_data tests.test_core.ClientCoreTests.test_legacy_bridge_identity_uses_canonical_manifest_and_available_options tests.test_client_lifecycle.ClientLifecycleTests.test_room_contract_scopes_sidecar_binding_pending_checks_and_goal_resend tests.test_client_lifecycle.ClientLifecycleTests.test_mixed_valid_and_invalid_save_indices_submit_nothing_and_preserve_pending_state tests.test_client_lifecycle.ClientLifecycleTests.test_mixed_valid_and_negative_save_indices_do_not_escape_client_loop tests.test_verify_generation_matrix.IdentityExtractionTests.test_extracts_layout_order_digest_and_canonical_sets tests.test_verify_generation_matrix.IdentityExtractionTests.test_canonical_location_projection_rejects_every_row_mutation_and_cardinality_change
```

Observed result: `FAILED (failures=5, errors=5)` across nine focused tests/subtests for the expected missing behavior:

- `state_identity` accepted no slot-data contract and returned the same identity after goal/layout changes.
- `{valid, 400}` and `{valid, -1}` observations silently filtered the invalid value and partially queued the valid check; lifecycle assertions also observed save binding and goal/check side effects.
- `GenerationIdentity` had no full location projection, so duplicate, wrong-key, wrong-name, wrong-ID, omission, and extra-row mutations were not definitively validated.

## GREEN evidence

Focused command after the minimal production changes:

```powershell
C:\Users\Jack\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_core.ClientCoreTests.test_native_slot_translation_rejects_the_whole_observation_on_any_invalid_index tests.test_core.ClientCoreTests.test_bridge_identity_is_room_contract_scoped_and_canonical tests.test_core.ClientCoreTests.test_bridge_identity_fails_closed_without_authoritative_room_data tests.test_core.ClientCoreTests.test_legacy_bridge_identity_uses_canonical_manifest_and_available_options tests.test_client_lifecycle.ClientLifecycleTests.test_room_contract_scopes_sidecar_binding_pending_checks_and_goal_resend tests.test_client_lifecycle.ClientLifecycleTests.test_mixed_valid_and_invalid_save_indices_submit_nothing_and_preserve_pending_state tests.test_client_lifecycle.ClientLifecycleTests.test_mixed_valid_and_negative_save_indices_do_not_escape_client_loop tests.test_verify_generation_matrix.IdentityExtractionTests.test_extracts_layout_order_digest_and_canonical_sets tests.test_verify_generation_matrix.IdentityExtractionTests.test_canonical_location_projection_rejects_every_row_mutation_and_cardinality_change
```

Result: `Ran 9 tests ... OK`.

Affected-suite regression command:

```powershell
C:\Users\Jack\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_core tests.test_client_lifecycle tests.test_verify_generation_matrix
```

Result: `Ran 154 tests ... OK`.

Final full verification command:

```powershell
.\tools\verify.ps1 -PythonExecutable C:\Users\Jack\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

Result: `Ran 336 tests ... OK`; release verification passed source parity, JSON/index integrity, fresh recipe derivation, and data exclusions.

- Final APWorld SHA-256: `F6CF0D532F02D46E8B1769E3A2EEF398E1DE2413EB27C7B076C9CFE9B2FB781F`
- Final release SHA-256: `E81F61E7D39F1DC5D8B934F5EA9FF8BB74DFDCF83CFCD6278DCEF1757D34A387`

## Implementation result

- Room state identity now hashes a canonical JSON room contract containing stable seed/team/slot/auth identity. New-layout contracts include manifest, layout, and base-manifest digests; progression model and layout algorithm; level set; goal; and campaign count. Legacy contracts retain the canonical bundled manifest digest and include available level-set, goal, and campaign-count fields.
- Identity construction validates authoritative slot data and fails closed when stable connection identity or authoritative campaign data is unavailable. Invalid connected contracts reset transient presentation state without opening any state or dispatch sidecar.
- Sidecar path, dispatch identity, `game_slot_id`, pending checks, and goal resend identity therefore cannot cross goal or layout boundaries. Reconnecting the identical contract deterministically reuses the same identity and sidecar.
- Native save indices are validated as a complete observation before save binding, reconcile, queuing, check submission, or victory submission. Any negative or out-of-range index yields an actionable `Campaign/save mismatch` status/log message while preserving bridge state.
- Real-generation extraction retains every raw `(stable_key, name, id)` row. Definitive validation compares the complete projection against the selected canonical campaign with exact cardinality, detecting duplicate rows, wrong keys, names, IDs, omissions, and additions. Every matrix row persists `canonical_identity_validation` explicitly.

## Definitive 200-case matrix

The installed APWorld was not changed because this task was not authorized to install externally. Its SHA-256 remains `8A1AC5102B841CEDE7575BEC432D253B4E79BFA847C58F7B261F12697E1A1F2E`, which differs from the final build.

To validate the final bytes without an external install, an isolated copy of the installed AP 0.6.7 runtime was created inside the worktree, its copied Word Factori APWorld was replaced with the freshly built APWorld, and the copied APWorld hash was verified as `F6CF0D532F02D46E8B1769E3A2EEF398E1DE2413EB27C7B076C9CFE9B2FB781F`. The isolated runtime was removed after generation.

Matrix command:

```powershell
C:\Users\Jack\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools\verify_generation_matrix.py --generator <isolated-ap067-runtime>\ArchipelagoGenerate.exe --evidence-output .superpowers\sdd\2026-09-02-nonlinear-progression\final-fix-generation-evidence.json --seed-start 13000 --seed-end 13049 --live-seed 13050
```

Evidence: `.superpowers/sdd/2026-09-02-nonlinear-progression/final-fix-generation-evidence.json`

- Started: `2026-09-02T16:07:57-04:00`
- Completed: `2026-09-02T16:28:51-04:00`
- Matrix: `200 pass, 0 fail`
- `identity_validation`: `Pass` in 200/200 rows
- `canonical_identity_validation`: `Pass` in 200/200 rows
- Deterministic identity: `Pass`
- Same-seed digest: `b3cd5448ff934026163258f8a2087c88863ae3f8a414493e30413f82466210db`
- Different-seed digest: `c5b48378ad56b76ed01c8f17f9e291d58421879d02745f69329c517e2fbe0d5d`

## Fresh live room

- Status: prepared; live gameplay pending
- AP: 0.6.7
- Seed: 13050
- Player: `WF_Live_Discovery_Count_13050`
- Archive: `C:\Users\Jack\AppData\Local\Temp\word-factori-ap067-live-_wer3wzd\output\AP_87260292545628931117.zip`
- Archive SHA-256: `314B87C5420CCC34A3B2014D126A760E1D4ED0E3A8937BF577F31EDBB5942BC3`
- YAML: `C:\Users\Jack\AppData\Local\Temp\word-factori-ap067-live-_wer3wzd\players\player.yaml`
- Layout digest: `d07d55295bd9bb46d44822872e8482f675a465d5bc167869b02f003ff3889dbe`
- Page one: Complete A, Complete C, Complete L, Complete I, Complete O, Complete V

## Remaining concerns

- The final APWorld still requires the controller-authorized installation step; this task deliberately did not modify `C:\ProgramData\Archipelago\custom_worlds`.
- Live Word Factori gameplay acceptance remains pending. The prepared room is evidence for generation and inspection only until the documented in-game steps are observed.
- The live room is under the Windows temporary directory and should be copied to a durable controller-owned location before routine temporary cleanup if it will be used later.
