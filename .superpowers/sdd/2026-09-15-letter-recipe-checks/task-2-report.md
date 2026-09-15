# Task 2 report: recipe integration

## Result

Connected the reviewed 187-recipe catalog to world generation, room validation,
Universal Tracker restoration, save parsing, client polling/reconciliation, and
release packaging. Recipe checks default on for normal generation; false and
legacy-absent rooms retain their prior progression model and state identity.

## RED evidence

`python -m unittest tests.test_recipe_integration` initially failed importing
`RECIPE_MODEL`; the recipe progression contract did not exist. The tests were
written before production changes and cover contract validation, native-slot and
victory isolation, journal parsing, and fresh-binding protection.

## GREEN evidence

- `python tools/build_release.py`: exit 0; APWorld SHA-256
  `63368ef0722284dae87f2b17bfebb9f27ab2d72db385ead5ec21c8154fc346c9`.
- `python -m unittest discover -s tests`: 500 tests in 62.072s, OK (1 skipped).
- Controller's independent real-AP generation smoke test reported core campaign
  counts of 30 with recipes off and 217 with recipes on; full matrix remains a
  controller-owned final verification.

## Self-review

- Native `level_count`, level-code conversion, goals, patch receipt, runtime
  marker, current room, and install behavior are unchanged.
- Enabled contracts use `machines_enhanced_recipes_v1`, exact JSON boolean
  validation, and the catalog digest. New rooms always emit the boolean; only
  enabled identities append recipe fields.
- Recipe discoveries share the existing observed/pending/acknowledged idempotent
  check path. They are included in server acknowledgment/scout reconciliation but
  excluded from native slots and victory.
- Fresh enabled binding refuses recognized prior discoveries and malformed
  journals. Disabled rooms ignore journal contents.
- Recipe locations use catalog-minimal capability alternatives and require the
  ordinary `complete-i` factory, which enhanced layout anchors on page zero.
- Release metadata version remains unchanged; no install, push, merge, or release
  action was performed.

## Review fixes

- Moved recipe-contract validation ahead of the legacy-room return. Focused RED
  tests demonstrated that legacy payloads previously accepted `recipe_checks:
  true`, non-boolean values, and a stray catalog digest; all are now rejected.
- Added real `WordFactoriContext` polling tests backed by temporary native save
  files. They cover combined level/recipe reporting, no second send after server
  acknowledgment, queued offline discovery replay after reconnect, wrong bound
  saves, malformed journals, recipe-disabled journal ignoring, and unchanged
  level-only reporting.
- Added direct assertions that the ordinary `complete-i` factory is on page zero
  and has no intrinsic module limits.
- Focused GREEN command: `python -m unittest tests.test_recipe_integration
  tests.test_client_lifecycle tests.test_world_layout tests.test_publication
  tests.test_verify_generation_matrix` — 164 tests in 12.686s, OK.
- Fresh package command: `python tools/build_release.py` — exit 0, APWorld SHA-256
  `14a9cebb4969552fc620ce71f1377d47c6d375ac8fdbacb223290414743b6f4a`.
