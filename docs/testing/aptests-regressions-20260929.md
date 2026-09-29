# APTests regression fixes — September 29, 2026

These fixes were prepared for the 1.7.0 tester prerelease, not stable approval.
The browser report and candidate hashes below predate the release version bump.

## What the exported report showed

The supplied Word Factori 1.6.0 report classified 1,450 fuzz runs as 691 successes, 579 failures, 176 ignored and four timeouts. Ignored cases are not passes. There were ten browser timeout events before hook reclassification; only five short timeout logs were exported, without seeds.

Of the 579 failures:

- 545 enabled Type-a-Word checks without providing any words. These are invalid configurations, not solvable seeds.
- Nine progressive seeds failed item placement with recipes and word orders disabled.
- 25 Universal Tracker runs rejected saved layout keys.

## Changes

**Tracker:** Archipelago saves JSON-style arrays as tuples in multidata. The test service's Tracker passed those tuples directly to the world. The reconstruction boundary now creates a detached, list-based payload before applying the same strict validation. Corrupt keys, duplicate identities, bad digests and non-array containers are still rejected.

**Progressive placement:** The existing upgrade-path proof ordered items, but reverse fill could consume the early checks needed for early upgrades. The fill hook now also orders this player's campaign locations by their first reachable upgrade step, late-first. Shuffled ties, optional checks and other players' positions are preserved. Archipelago still places the items; nothing is preplaced or locked.

**Generation performance:** Normal-machine rules previously expanded every preceding level before checking whether the requested machine was owned. They now check machinery first and stop predecessor evaluation at the page threshold. No page gates or machine requirements changed. On exported Tracker case 9, the same profiled generation dropped from approximately 34 seconds to 1.8 seconds locally. Profiling adds overhead; these numbers are not browser timing or game-FPS guarantees.

**Invalid options:** Type-a-Word validation raises Archipelago's `OptionError`, allowing test tools to recognize invalid input. Invalid configurations remain errors for players. The supplied meta YAML provides 20 valid targets, including symbols, while leaving the enable switch and selected count randomized.

No native patch, installed game, save, YAML default or location ID was changed by these fixes.

## Full-run follow-up: mixed-world timeouts

The first corrected package passed the quick browser run (1,450 generations). The subsequent full report classified all 14,500 generations as successes, but recorded five raw timeout/restart events in `check-gerpocalypse`. That hook reclassifies outcomes other than two specific entrance errors as successes, so the headline alone does not prove those generations completed. The report did not preserve the individual timeout seeds.

Profiling independently reproducible mixed rooms with the service's Kingdom Hearts companion exposed repeated normal-machine page traversal during item placement. The earlier short-circuit improvement was insufficient: one generation still invoked the page rule more than eight million times. Campaign rules now share predecessor answers only during one synchronous root evaluation. They still call AP's actual location/region rules; answers are discarded after the root returns or raises, and nested different states are isolated. Inventory must remain stable during a single synchronous access-rule call, as in ordinary AP evaluation.

In the same local profiling setup, fixture `ut-1` improved from 18.407 to 0.591 seconds and `ut-38` from 31.301 to 1.017 seconds. All 25 mixed fixtures completed with beatability and configured accessibility verified. These are independent reproductions, not identification of the five unseeded browser timeouts. Progressive catalog construction is a separate cold-start cost; this change does not claim to remove it.

Regression tests compare all 64 normal-machine inventories across both campaigns and three layouts, bound repeated predecessor traversal, and cover changed inventories between queries, exceptions, overridden predecessor/region rules and nested different states.

## Repeat the browser test

1. Build the corrected `word_factori.apworld` with `python tools/build_release.py`.
2. Select that APWorld in APTests.
3. Supply [aptests-meta.yaml](aptests-meta.yaml) as the fuzz meta YAML.
4. Run the unit, generation and Universal Tracker checks and export the complete report.

Do not disable word checks or count ignored configurations as successes. Inspect `environment.json` for raw timeout/restart counters as well as the headline results.

### Completed full browser retest

The follow-up run started at `2026-09-29T21:40:24.854Z` and finished normally in 11 minutes 34 seconds against the service's AP 0.6.7/Pyodide runtime. All 205 unit tests and 14,500 generations passed: 5,000 default, 5,000 unrestricted-start and nine 500-case hook categories, including Universal Tracker and mixed-world GER. The exported `environment.json` records **zero raw timeouts, restarts, fatal errors and skipped variants**. All classified failure, timeout and ignored counts are also zero. No failure annotations were supplied; the valid Type-a-Word meta YAML was supplied, and the browser calibrated its timeout to 22 seconds per generation.

Report: `waimea-word_factori-1.6.0-2026-09-29T21-40-24.zip`; fuzz seed `d3cf29b44486`. This is a new randomized full run, not a replay of the earlier five unrecorded timeout cases. It demonstrates clean browser stress results for this run, not a guarantee for every future seed or third-party world. The index CI remains a separate authoritative service check.

## Repeat local packaged regression tests

Use an official Archipelago 0.6.7 source checkout with its dependencies installed. From this repository:

```text
python tools/build_release.py
python -m unittest discover -s tests -q
python tools/verify_aptests_regressions.py --ap-source /path/to/Archipelago --output /path/to/new-results --extra-seeds 40
python tools/verify_release.py
```

Add `--tracker /path/to/tracker.apworld` to replay all 25 Tracker fixtures and compare each sphere with actual Universal Tracker. The exported service used Tracker 0.2.26. Without that argument, the runner still validates saved tuple-based room data but does not run the actual Tracker.

For mixed-world generation, use `--kingdom-hearts /path/to/trusted/kh1.apworld` instead of `--tracker`. This adds the same 25 option fixtures with a default Kingdom Hearts companion, matching the browser hook's companion setup. The runner requires successful generation, victory and configured accessibility for both players; it does not reclassify timeouts as passes. Supply a trusted companion package yourself; this project does not redistribute it. Set `WF_KH_APWORLD` alongside `WF_AP_SOURCE` to enable the dedicated slow-seed mixed-world unit regression. Tracker sphere replay remains single-player and cannot be combined with the companion option.

Use `--dependency-path /path/to/dependencies` only for dependencies installed outside the active Python environment. The output directory must not already exist. The runner freezes and hashes the input APWorld and stages disposable AP copies; it does not modify installed worlds or start the game.

The full matrix contains nine original placement failures, 25 original Tracker failures and 40 additional progressive seeds. It checks victory, the configured accessibility requirement, exact saved-room reconstruction, and (with Tracker supplied) matching reachable checks in every sphere. The added seeds vary campaign, goal, accessibility, optional checks and starting inventory.

Set `WF_AP_SOURCE` (and optionally `WF_AP_DEPS`) when running `tests.test_aptests_regressions` to enable the real-AP tests, including a negative test that must reject a beatable world with an inaccessible required check. The CI connected job also replays the nine placement failures and 12 additional seeds.

## Local verification result

The follow-up package passed all 74 matrix cases with the test service's actual Tracker 0.2.26, including victory, configured accessibility and sphere agreement. A separate 74-case mixed-world matrix with Kingdom Hearts passed generation, victory and configured accessibility for both players. The full local suite ran 808 tests successfully (eight expected skips); a separate opt-in connected/regression group ran 16 tests successfully, including the deliberately inaccessible-world rejection and mixed-world regression. Release verification passed source parity, JSON/index integrity, recipe derivation and data-exclusion checks. These results are local; the added GitHub CI job has not run remotely yet.

The browser/matrix input SHA-256 is `46d4bd069456ead958a8f80523ebfc4871a2ff28836059c95d93521df1e26db0`. Review then clarified one helper docstring; the rebuilt package SHA-256 is `6b4a39e5edaf76349c642e5f665b339702c5794681b0d4023c5dbddfef3c2830`. Archive comparison found only that docstring changed, and AST comparison confirmed identical executable code. The final full suite and 16 opt-in tests used the clarified source/package.

## Remaining browser and live-game limits

The unseeded browser timeout logs cannot be replayed exactly. Local generation uses native Python rather than the service's Pyodide runtime. This regression matrix does not establish compatibility with every third-party world's fill hooks or arbitrary plando. Connected tests simulate the game boundary; Windows/Linux live playthrough, display and sustained native performance acceptance remain separate release gates.
