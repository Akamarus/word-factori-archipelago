# Type-a-Word acceptance — UNRELEASED 1.5.0

This is an unpublished feature-branch candidate. Public release remains 1.4.2.
No live installation, game save, AP installation or public release was changed.

## Established evidence

- Isolated native completion gate: 21/21. The production-contract enforcement
  follow-up passed 66/66, extending the original 51/51 gate; see
  [native evidence](type-a-word-native-evidence.md).
- Exact production providers and all five hooks compile and reopen from the
  verified original. Candidate game SHA256:
  `33aeea0ae1429e35a8c8b5a98407d88c07b53eac33b40f1df8d47bb566eb7161`.
- Distributable COPY/data delta SHA256:
  `b698f7bd432fb5982a731188ab4a3c3a7e9e9cf41884a2c9e4696ff128e5adba`.
  It is 914,822 bytes with 8,274 operations and round-trips to that game hash.
- Installer tests use synthetic bytes and isolated destinations, exercising
  fresh install, exact legacy upgrade, idempotence, unknown builds, backup
  validation, rollback/recovery, receipt capability and path safety.
- APWorld packaging includes `word_orders.py` and
  `data/alphabet_requirements.json`. No full game, raw extracted code, probe
  output or user save belongs in either archive.

## Controller matrix evidence

The final APWorld SHA256
`b4f641c8ef3e9ed3cd15d5002d097ff4682b2e6810314a50ae12ddf9a1fb24ff`
passed isolated real Archipelago 0.6.7 generation for orders on/off × recipes
on/off × Core/Discovery × Campaign Count/Final Factory: **16/16 passed**.
Enabled orders used count 3 and JACK, FACTORY, PUZZLE, ISLAND. Balanced item and
location totals were 30/33/40/43/217/220/227/230 as applicable. Slot contracts,
IDs, progression spheres and exclusion of extra checks from factory goals passed.

Authoritative Universal Tracker reconstruction also passed **16/16** using the
real generated room contracts, AP test doubles, conflicting local settings and
RNG checks. Exact slot data, IDs and target regions matched. This is not a
connected live tracker acceptance claim.

Controller commands: `python tests/output-typeword-verification/run_matrix.py`
and `python tests/output-typeword-verification/verify_tracker.py`. Raw reports
are retained in ignored `results.json` and `tracker-results.json` alongside
per-case logs. Generation logs contained only the pre-existing
`pokemon_emerald` `pkg_resources` deprecation; no Word Factori warning or error.
Independent alphabet regeneration matched 26 letters and 64 requirement subsets.

## Connected acceptance still pending

1. Fresh enabled room and fresh empty mod save: enter free-word mode, complete
   selected orders, inspect `/wf_words`, and confirm each server check once.
2. Verify locked machine production and previews across campaign/free-word
   modes and saved layouts. Receive machine items, return to Levels, re-enter
   the factory without restarting, and verify ordinary production resumes.
   Custom-building production/previews remain blocked; layouts must remain.
3. Verify native disk flush, game restart, client reconnect and repeated reads
   preserve order identity and do not duplicate checks. Native isolated probes
   do not establish disk or UI behavior.
4. Confirm orders and journal checks never advance page arrows or campaign
   victory. Confirm old compatible room contracts without order fields disable
   orders and cannot acquire them from changed local YAML.
5. Verify live Universal Tracker against the room's authoritative selected
   orders, layout, goal and recipe settings.
6. Repeat install/upgrade, connected play, reconnect and restore on real
   Linux/Proton. Host-side path/transaction tests are not a Proton playthrough.

No claim of quantity-aware logic, arbitrary Workshop import, online daily
service acceptance, or complete connected acceptance is made.
