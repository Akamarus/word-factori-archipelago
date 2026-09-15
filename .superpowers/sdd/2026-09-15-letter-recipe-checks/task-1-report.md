# Task 1 report: derived catalog and exact recipe reachability

## Files

- `word_factori/recipe_checks.py`
- `word_factori/letter_recipes.json`
- `tools/build_recipe_catalog.py`
- `tests/test_recipe_checks.py`

## RED evidence

`python -m unittest discover -s tests -p test_recipe_checks.py -v`

- 9 tests ran and errored because `word_factori.recipe_checks` and `tools.build_recipe_catalog` did not exist.
- The direct builder regression subsequently failed with `ModuleNotFoundError: No module named 'word_factori'` before the script-path fix.
- The native canonicalization regression failed with raw `('I', ')')` / `('I', '3')` identities instead of canonical `('(2', 'I')` / `('3', 'I')` identities.
- The numeric-zero regression then failed with an empty normalized token instead of `0`.

Each failure was observed before its corresponding production change.

## GREEN evidence

`python -m unittest discover -s tests -p test_recipe_checks.py -v`

- 12 tests ran, all passed, including isolated import as `worlds.word_factori.recipe_checks`.
- Catalog contains 189 unique explicit IDs beginning at 975302000.
- Machine counts are 24 Bender, 86 Merger2, 60 Merger3, and 19 Merger4.
- All outputs are cleaned single A-Z letters; 121 source-hidden recipes are retained as catalog visibility metadata.
- Minimal route literals pass: `I -> C`, `I1 -> U`, and `I I -> V`.
- Runtime matching is exact against canonical native journal machine/input/output identities.

Deterministic regeneration produced the same packaged file SHA-256 twice:

`77543c8096508a8c25fc03f98c20797e89b8ebb347128b7fe5ef30b4123a6b8c`

After native canonicalization was incorporated, the independently generated native fixture was compared to the packaged catalog:

- catalog identities: 189
- native identities: 189
- missing: 0
- extra: 0
- all actual outputs matched expected outputs
- all native saves succeeded
- all repeated saves left the journal unchanged

`python -m unittest discover -s tests -q` completed with 489 tests passing and 1 skipped. An earlier verbose run transiently showed installer failures while its shared build fixtures were not ready; rerunning the 18 named installer tests passed, and the final complete run was clean. No installer, game, or live-room files were changed.

## Self-review

- Builder reads base64 JSON only from the explicitly provided path and packages mechanics-only derived facts, not the proprietary raw data.
- All 64 unique capability subsets are evaluated once, then reused for every recipe.
- Minimal requirements require the recipe's own machine and every whole canonical input token; duplicate inputs remain present.
- Stable IDs are assigned deterministically and existing canonical identities retain their IDs on regeneration.
- Catalog loading verifies its digest, exact schema, counts, visibility total, unique IDs/names/identities, capability vocabulary, own-machine inclusion, and minimal requirement options.
- Exported records and collections are immutable and have no Archipelago or installed-game runtime dependency.
- No hidden-marker or permutation guessing occurs at runtime: the builder reproduces native `Letter(...).toString()` and `lettersAsString()` canonicalization, and the matcher performs exact lookup.

## Concerns

- None within Task 1. The native fixture is local verification evidence only and is not redistributed.
