# 1.5.1 feedback fixes — local verification, 2026-09-16

Status: pre-publication verification record for the 1.5.1 tester prerelease. No live installation or player-save edits were performed. Publication is recorded separately by the GitHub release.

## Scope and diagnosis

1. Recipe loading: the original native normalizer exits its machine-group callback when it meets an already-normalized entry. Reversed duplicate inputs in the online table can trigger that branch and leave raw strings behind. A later refresh then treats a string such as `6` as an instance reference. This reproduced the reported instance-index-6 failure without AP hooks or player saves. The patch continues that loop instead. AP sessions reload bundled recipes and reject online replacements, while vanilla sessions retain them.
2. AP groups: define `item_name_groups` and `location_name_groups` in the world class body so registration and YAML expansion see them. Do not insert seed-specific groups later.
3. Type-a-Word: support the 48 verified characters (A–Z plus 22 symbols) in validation, ordinary reachability, quantity witnesses and serialized room contracts. Native goal matching accepts 9 through the rotated-six token `62`; the quantity catalog validates this alias explicitly.

## Evidence

- Baseline: 643 tests, two skipped, no failures.
- Regression-first tests failed before implementation for each of the three missing behaviors.
- Full updated suite: 660 tests, two skipped, no failures. Run `python -m unittest discover -s tests -q`.
- Native recipe-safety acceptance: eight passing assertions. Repeated duplicate refresh, vanilla online acceptance, switching into AP after an online update, AP update rejection and returning to vanilla are covered. Run `tools/run_type_word_native_probe.py --recipe-safety` with the verified original, local runtime, local native tooling and a fresh scratch output directory. It uses an isolated namespace and synthetic responses, not player saves or a live network callback.
- Native production acceptance: 70 passing cases, including all 22 special characters plus repeated/mixed symbol words, against native production and goal code. Run `tools/run_quantity_native_probe.py` with local verified assets in an isolated namespace.
- Production native patch: nine modified code entries compiled, reopened and checked. Delta round-trip reconstructed the expected patched hash from the verified original.
- Real Archipelago 0.6.7: built APWorld generated normal and progressive rooms with six symbol orders each. YAML exercised `Machines`, `Progressive Machines`, `Stickers`, `Campaign Levels`, `Recipe Discoveries` and `Word Orders` through locality, exclusion and priority settings. Both generations exited successfully and contained all requested targets in the spoiler.
- Unit coverage includes symbol normalization/rejection, native alias validation, minimal reachability, quantity witnesses, journal/check handling, tracker reconstruction, static registration, and Windows/Linux upgrade/restore from 1.5.0 as well as older supported patches.
- `python tools/build_release.py` and `python tools/verify_release.py` validate the candidate package, source parity and exclusion of proprietary binaries and player data.

## Native identity

- Original: `d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978`
- Patched: `20ccd780854adcab416f903e8ffb1702930c16fd91c307ec316d746da1567bbe`
- Delta: `75ad933546285aa2c53ccfcc3f0a53afd17029771abe77a40389bb4296ba5cd0`

## Still required before claiming live acceptance

- Load a save and switch vanilla/AP sessions in the full game on Windows and Proton. The isolated runtime harness verifies the failing code path, not the complete GUI/save lifecycle.
- Complete symbol orders with the connected client and Universal Tracker, including 9, key/door and repeated symbols. Exercise both machine modes.
- Run the updated package on a real Linux installation. Local installer simulation and native Windows probes are not Proton gameplay evidence.
- Use the matching candidate APWorld/client/tracker/native patch with a new room and empty mod save. Preserve existing saves and the verified original backup; no save deletion or repair is part of this fix.
