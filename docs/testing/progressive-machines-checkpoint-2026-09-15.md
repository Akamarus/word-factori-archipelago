# Progressive machines: unpublished development candidate

No live installation, seed replacement, GitHub push or release was performed. Installed game hash remains `5a964d5155f8f7acc63fd90bc81882a0559c4586f5de4fd9a0657badd8594194`.

## Implemented and verified

- Optional default-off machine tiers 1, 2, 3, 4, unlimited; one starting Bender, unlimited I sources, shared Rotation/Reflection directions.
- Constructive whole-factory quantities for campaign, all 187 recipe checks and optional word orders, with exact room identity and matching tracker reconstruction.
- Approved M lab correction: Merger2 plus Merger3; hybrid manifest 1.2.1, stable name/target/check ID.
- Approved quantity-aware page selection. Exact seed 271928 layout formerly stalled at four checks and is now rejected; a funded 29-upgrade witness is required. Search exhaustion fails closed. Sixty shuffled layouts pass regression coverage.
- Real AP 0.6.7 matrix: all 16 campaign/goal/recipe/order combinations passed (4.469–5.453 seconds wall time; mean 4.833). Both original failures, seeds 271928 and 272030, also pass using the packaged APWorld.
- Packaged mixed normal/progressive two-player room passes (20.390 seconds); two-progressive-player room passes (5.578 seconds). These are generation tests, not connected gameplay tests.
- Actual spoiler confirms configured pool inventory: one starting Bender, two starting Rotation copies and three remaining placed Rotation copies.
- 44 isolated native whole-word/goal/journal assertions passed in `progressive-words-20260915-r2`.
- 88 isolated native enforcement assertions passed in `quantity-final-20260915`: live upgrades without setLevel, imported over-limit scenes preserved, buffered wins blocked, deletion recovery, ghost exclusion, shared Rotation and Reflection, challenge caps, unlimited sentinel, invalid numeric rejection, reconnect and changed rooms. Existing boolean-mode assertions pass alongside them.
- Production patch compiled/reopened twice, identical SHA-256 `39e48a5eb63924b970bc3e3907f62b0b659fc64ba5fa973c45f4e2dcf767c704`. Helper digest `c81fbad89f64345e05720bac8627a3cd9f96edd35416bfd27c3feb920b64eb8d`.
- Copy/literal delta independently round-tripped to that production build. Delta SHA-256 `c9ac2637268c94813d6c3be0c1ba19c0997968d6b75ba375c4816479f596c1cc`. Only delta and authored integration files are bundled, not the full game, fonts or proprietary sources.
- Windows/Linux installer pins and previous v1/v2 migration paths updated, with original-backup preservation and invalid-receipt rejection coverage. APWorld allowlist includes every quantity module and derived catalog.

## Final verification

Clean full-suite rerun: **643 tests, 2 skipped, no failures, 79.170 seconds**. Strengthened previous-v2 Linux receipt migration test also passed separately. An earlier full run overlapped the isolated native executable and correctly triggered installer game-running safeguards; the clean run was performed with native probes closed.

Player archive verification checks source parity, explicit file allowlists, manifest hashes, JSON/index integrity, fresh recipe derivation and proprietary-data exclusions.

## Review and remaining acceptance

Reviewed inline following the requested execution preference. Pure quantity, contract and layout code are separate from native IO. Page selection proves viability without placing item locations; the fill hook retains other players' pool positions. Installer migration retains verified original backups.

The isolated probes suppress unrelated GUI/network events and use private saves. They do not establish actual GUI duplication/undo/import, notification appearance, a connected AP playthrough, live Universal Tracker or Proton behavior.

Before proposing a public release:

1. Connected game/client/tracker playthrough: demonstrate finite limit, live item update, reconnect and victory.
2. Real GUI import/undo/duplicate and restored over-limit save, with no lost layout and no invalid check.
3. Large-factory native performance review: repeated scene scans can scale quadratically; do not infer performance from small probe factories.
4. Linux/Proton gameplay acceptance. Mixed-room generation took longer than single progressive rooms; retain this measurement in performance follow-up.

The player ZIP is explicitly `UNRELEASED development`. Packaging is not live acceptance or authorization to publish.
