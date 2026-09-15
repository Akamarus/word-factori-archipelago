# Changelog

## 1.5.0 — Expanded checks and progressive machines (tester prerelease)

All changes below are new since the published 1.4.2 release. This release is for community testing, not a declaration of stable or fully playtested support.

### Upgrade instructions — please read

- Download **word-factori-archipelago-1.5.0.zip**, not GitHub's source-code archives. One ZIP supports Windows and native Linux/Proton setup.
- Close Word Factori and Archipelago. Extract into a separate folder and rerun the included installer: **Install Word Factori Archipelago.cmd** on Windows, or `bash "Install Word Factori Archipelago.sh"` on Linux.
- Restart Archipelago so it loads the new APWorld/client. Update the Word Factori APWorld used by Universal Tracker as well.
- Generate a **new 1.5.0 room** and use a **fresh empty mod save**. Do not reuse a progressed save or assume older rooms/development builds are compatible. YAML changes cannot retrofit an existing room.
- Keep old saves and `data.wf-ap-original.win`. Supported previous native patches upgrade through the verified original backup. Unknown builds and missing/corrupt required backups are rejected.
- Archipelago **0.6.7** and the installer-verified Word Factori Steam build **12616577** are required.

### Added: configurable Recipe Journal checks

- New `recipe_checks` YAML option, **enabled by default**. Set it to `false` for the smaller factory-only campaign (plus any enabled word orders).
- Adds **187 working A–Z-producing recipe checks**, including **119 hidden alternatives**. Different machine/input routes to the same output are distinct locations.
- These are actual global Recipe Journal discoveries, separate from named Discovery Lab level completions.
- Excludes source I, symbol outputs, and two native Merger3 entries with only two inputs that a real factory cannot use.
- Recipe identities normalize native inputs, have stable IDs and a validated catalog digest, and are bound to the connected room's save.
- Recipe scans are idempotent across duplicate scans and reconnects. They wait for native saved journal state; the game's save-flush cadence can delay reporting.
- Recipe checks add filler, not mandatory machinery, and do not unlock pages or count toward either victory goal.

### Added: optional Type-a-Word orders

- New `type_a_word_checks` option, **off by default**.
- `type_a_word_words` supplies your own YAML word list; `type_a_word_count` selects a deterministic seed-specific subset.
- Defaults: count **5**, empty list. Supported count: **1–20**. Maximum list size: **200 entries**. Each entry must contain **2–12 ASCII letters**.
- Input is trimmed, uppercased, deduplicated and sorted before seeded selection. Enabled orders require enough distinct valid words; invalid types, symbols, oversized entries/lists and insufficient lists are rejected.
- Manufacture the selected words in the native Type-a-Word factory. The client reads validated word-completion state from the bound save; unrelated words do not send checks.
- Added `/wf_words` for the selected targets, completion status and missing machine/upgrades.
- Orders have deterministic identities and authoritative room data. Local YAML and tracker reconstruction cannot resample a live room's words.
- Orders add filler checks, not new machinery requirements in the item pool. They do not advance page arrows or campaign victory.
- Strict score parsing rejects malformed, negative and oversized completion values. Reconnects and repeated reports remain idempotent.

### Added: optional progressive machine quantities

- New `progressive_machines` option, **off by default**, within the same integration and installer.
- Six families: Bender, Rotation, Reflection, Merger2, Merger3 and Merger4.
- Each family upgrades through **1 → 2 → 3 → 4 → unlimited** simultaneously placed machines.
- Start with **one Bender** and **unlimited I sources**. There are **29 remaining progressive upgrades** before configured starting-inventory removal. Pipes and target receivers do not consume an allowance.
- Clockwise/counterclockwise share the Rotation allowance; horizontal/vertical share Reflection. Deleting a machine frees its slot.
- The fifth tier removes the AP family limit, not the level's own lab or challenge restrictions.
- Added supported `start_inventory_from_pool`: configured starting copies are removed from the random pool. Use progressive item names in progressive mode and normal access names otherwise.
- World, client and tracker use the same validated, constructive whole-factory quantity budgets. Identical operations can share machinery; different processes are not merged merely because they output the same letter.
- Quantity logic covers campaign targets, restricted labs/challenges, recipe checks and selected word orders. It is conservative, not a guarantee of optimal factory size; better player designs may finish checks before the tracker considers them reachable.
- Progressive page selection requires a funded upgrade path and rejects known dead-end layouts. Page one contains shuffled I/C/V/L plus two later targets; remaining pages are shuffled. The **four-completion page unlock rule is unchanged**.
- A progressive item ordering hook helps Archipelago fill follow the verified path while retaining randomized item locations and other players' pool positions.
- Quantity-based page reachability is cached and evaluated as a single page chain rather than recursively rechecking the same earlier pages.

### Changed: native machinery enforcement and refresh

- Updated the reversible native patch and matching client/installer fingerprints.
- Native production and recipe previews enforce received machine access, including saved factories. Native custom-building production and previews are blocked in the AP mod rather than allowing them to bypass access rules; saved layouts are retained.
- Progressive allowances are polled **during play**, without re-entering a factory or reloading the game. Normal, non-progressive access still refreshes when returning to Levels and entering a factory.
- Progressive accounting includes placed/disconnected machinery and shared directions, excludes placement ghosts, and also validates the simulation graph.
- Imported/saved over-limit layouts stay editable but cannot simulate or award buffered completion checks. Removing excess machines or receiving an upgrade restores eligibility.
- Native over-limit notices identify exceeded family/challenge limits. `/wf_status` shows progressive allowances; `/wf_words` reports whole-route missing upgrades.
- Versioned room-bound runtime acknowledgment prevents an old/mismatched runtime from authorizing new recipe/word checks or progressive campaign checks.
- Same-room reconnect retains validated inventory. Changed-room, stale/conflicting and malformed snapshots fail safely. Duplicate item packets do not increment progressive tiers.

### Fixed: tracker, campaign and integration correctness

- Universal Tracker restores the server's saved shuffled layout and goal instead of generating a different layout from tracker seed/YAML.
- Tracker reconstruction also restores recipe enablement, selected word orders and progressive quantity settings. Invalid or partial contracts are rejected rather than silently reinterpreted.
- Page-aware logic still distinguishes four *solvable* preceding-page levels from four *actually completed* levels in the game. Manual `/send_location` does not write game saves or open native page arrows.
- Corrected **Discover M — Triple Merge Lab** to permit/require **Merger2 plus Merger3**. Merger3 alone was not a valid route. Its existing name, target and check ID are unchanged; the hybrid manifest is now **1.2.1**.
- Fresh-save binding and completion parsing now cover recipe/word progress, slot changes and malformed data. Checks remain paused on campaign/save/runtime identity mismatch.

### Installation, packaging and documentation

- Windows and Linux installers recognize supported prior v1/v2 native patches, preserve the verified original backup, validate receipts/capabilities and refuse unknown game bytes.
- Windows staged-mod validation and Linux manifest validation accept the updated hybrid campaign correctly.
- APWorld includes the new recipe/word/quantity modules and derived catalogs; package verification explicitly checks the runtime payload.
- Native production build was compiled/reopened twice with identical output, and the distributable copy/literal delta was independently round-tripped.
- Full game binaries, proprietary recipes, fonts, music and user saves are not distributed.
- README, AP tutorial, Linux guide and native testing guide now describe 1.5.0 behavior and installation.
- Examples: normal Campaign Count, Final Factory, progressive-machine play, and custom Type-a-Word orders. All new options and defaults are documented.
- Existing 1.4.2 Linux directory/shortcut and receipt fixes remain included. Linux uses the regular native AP client; the AP Mail overlay remains Windows-only.

### YAML example: enable all new features

Merge these settings into your player's existing `Word Factori:` section; do not create a duplicate section.

```yaml
Word Factori:
  custom_level_set: discovery_labs
  goal: campaign_count
  campaign_count: 25
  recipe_checks: true
  type_a_word_checks: true
  type_a_word_count: 3
  type_a_word_words: [JACK, FACTORY, PUZZLE, ISLAND]
  progressive_machines: true
  # Optional extra starting copy; one Bender is already granted.
  start_inventory_from_pool:
    Progressive Rotation Access: 1
```

For the smaller normal-access campaign, use `recipe_checks: false`, `type_a_word_checks: false`, and `progressive_machines: false`.

Total checks: **30 or 40 factories + 187 when recipes are enabled + 1–20 selected word orders when enabled**. Only the 30 canonical campaign locations count toward Campaign Count; Discovery Labs, recipes and word orders do not.

### Verification and what testers should look for

- Local automated suite: **643 tests, 2 skipped, no failures** before release preparation; release verification reruns the suite.
- **88 isolated native enforcement assertions** and **44 native whole-word/goal/journal assertions** passed.
- All **16 progressive campaign/goal/recipe/order generation combinations** passed. Both previously failing seeds, a mixed normal/progressive room and a two-progressive-player room also generated successfully from the packaged APWorld.
- Single-player progressive generation measured about **4.5–5.5 seconds** here; the mixed-mode room took about **20 seconds**. This is evidence, not a speed guarantee or a fix for every generation-performance issue.
- Still needed: connected game/client/Universal Tracker playthroughs, reconnect/disk restart, GUI import/undo/duplicate and restored over-limit layouts, large-factory performance, and real Linux/Proton gameplay. Repeated native scene scans may become expensive on large factories.
- Please report the version, YAML options, target/check name, expected versus actual behavior, and relevant client messages. Redact passwords and personal paths; private setup details do not need to be posted publicly.
- No stable-release claim: exclusive fullscreen, arbitrary Workshop import, custom-building production and the Linux overlay remain unsupported.

## Earlier releases

- [1.4.2 — Linux setup fixes](https://github.com/Akamarus/word-factori-archipelago/releases/tag/v1.4.2)
- [1.4.1 — Linux tester prerelease](https://github.com/Akamarus/word-factori-archipelago/releases/tag/v1.4.1)
- [1.4.0 — Nonlinear tester prerelease](https://github.com/Akamarus/word-factori-archipelago/releases/tag/v1.4.0)
