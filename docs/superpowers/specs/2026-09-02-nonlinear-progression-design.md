# Nonlinear Progression and Shuffled Pages Design

**Status:** Draft for user review; concept approved

**Date:** 2026-09-02

**Target release:** Word Factori Archipelago 1.3.0

## Summary

Word Factori Archipelago 1.3.0 will replace its fixed, one-location-at-a-time progression model with deterministic, seed-specific page layouts. A shuffled room will place the curated levels on different Word Factori pages while preserving stable Archipelago location identities. Each page will use Word Factori's native rule: six visible levels, with any four completions unlocking the next page.

The result is a campaign with genuine route choice. A player may encounter a level that needs a missing machine, complete other levels on that page, advance after four successes, and return to the deferred level later. The implementation will use only Word Factori's supported JSON mod format and read-only save discovery. It will not patch `data.win` or write unverified save fields.

## Verified game constraint

The installed game's official `tips.json` states that each page contains six words and that completing four of the six unlocks the next page. The supported mod tutorial exposes level target text and module limits but no separate per-level or per-page unlock field.

The integration must therefore work with the native six-slot page and four-completion threshold. It must not claim arbitrary graph presentation that Word Factori cannot display.

## Goals

- Randomize which curated levels appear together on each page.
- Give different seeds meaningfully different routes through the same curated content.
- Match Word Factori's native four-of-six page progression in Archipelago logic.
- Allow up to two difficult levels per complete page to be deferred and revisited.
- Mix Discovery Labs into later pages in the 40-location level set instead of always appending them as a fixed block.
- Keep location names, numeric Archipelago IDs, and stable keys unchanged across layouts.
- Translate Word Factori's position-based completion indices into the correct stable AP checks.
- Reproduce and validate the exact same layout after reconnect, reinstall, or restart.
- Preserve the existing simple installation and single-mod workflow.
- Preserve safe support for legacy 1.2.x rooms.

## Non-goals

- Randomly generating factory layouts or recipes.
- Importing arbitrary Workshop campaigns.
- Patching proprietary game binaries.
- Writing Word Factori save data to force page unlocks.
- Creating multiple mod folders or requiring players to switch save slots between branches.
- Allowing unrestricted random permutations that have not passed balance and reachability validation.
- Adding live progression-item refresh; that remains a separate tracked feature.

## Terminology

- **Canonical level:** A curated campaign record identified by a stable key, stable AP location name, and stable numeric AP location ID.
- **Native slot:** A zero-based position in the generated `levels.json`. Word Factori records completions by this position.
- **Page:** Six consecutive native slots. A final partial page may contain fewer than six.
- **Layout:** The deterministic permutation mapping native slots to canonical levels for one room.
- **Frontier:** The currently available page whose locations may be completed in any order.
- **Layout digest:** A canonical hash covering the base manifest identity, layout algorithm version, progression model, and ordered stable keys.

## Player-facing options

A new `campaign_layout` choice will be added:

- `shuffled_pages` — default and recommended. Uses constrained, seed-specific page composition.
- `fixed_pages` — retains the curated page composition while still using the native four-of-six progression rules.

The old fully sequential AP rule will not be offered in new 1.3.0 rooms. Existing 1.2.x room files retain their server-side rules.

## Canonical content and stable identities

`campaign.json` remains the source of canonical level records. The existing stable key and canonical index continue to determine each location's name and numeric AP code. A shuffled layout must never recalculate an AP code from the level's native slot.

The implementation will separate the two concepts currently combined in `LocationData.index`:

- `canonical_index` identifies the stable AP location and produces its numeric code.
- `slot_index` identifies where that level appears in Word Factori for this room.

The canonical content manifest remains reusable across layouts. A new immutable layout model carries the ordered stable keys and derived slot/page data.

## Layout model

The design introduces pure data types equivalent to:

```text
CampaignLayout
  algorithm: "balanced_pages_v1" | "fixed_pages_v1"
  level_set: "core_campaign" | "discovery_labs"
  page_size: 6
  page_unlock_count: 4
  ordered_stable_keys: tuple[str, ...]
  digest: str

LayoutEntry
  slot_index: int
  page_index: int
  canonical_record: CampaignRecord
```

The digest is calculated from a canonical JSON representation. It includes the base campaign digest and all layout-defining fields. It excludes cosmetic or runtime state.

Layout validation rejects:

- unknown or repeated stable keys;
- omitted selected levels;
- noncontiguous native slots;
- incorrect page sizes other than the final partial page;
- missing required anchors;
- forbidden early challenges or Discovery Labs;
- an incorrect algorithm-specific anchor placement;
- an unknown algorithm or progression model;
- a digest mismatch.

There is no silent fallback from an invalid shuffled layout to the fixed layout. Generation fails with a precise error rather than creating a room whose game and AP mappings disagree.

## Shuffled-page generation

The layout is generated before regions and access rules are created, using the player-specific Archipelago random source. The same seed, player, options, and implementation version produce the same ordered stable keys.

The `balanced_pages_v1` algorithm applies these constraints:

1. The layout is an exact permutation of the selected curated level set.
2. `Complete I` and `Complete C` are placed on the first page as bootstrap checks. Their exact positions on that page may vary.
3. The remaining first-page slots are selected from normal Core Campaign word levels. Challenge, Discovery Lab, and final records cannot appear there.
4. `PITCHFORK — Final Factory` is placed on the final page.
5. Challenge levels use `page_index >= 2`; they cannot appear before the third displayed page.
6. In the 40-location level set, Discovery Labs are distributed across pages after the first page rather than reserved for a fixed post-campaign block.
7. Every complete page contains at least three distinct minimal machine-requirement profiles.
8. No complete page may contain four locations for which the same non-precollected machine is unavoidable across every valid recipe route.
9. Ties and candidate order are resolved by the room's deterministic random source.

Generation uses bounded deterministic search over the small curated set. If no valid layout is found, it raises a generation error naming the failed constraint. It does not weaken constraints based on retry count.

`fixed_pages_v1` uses the current canonical order and the same layout serialization, identity, and four-of-six access model. This keeps one code path for client mapping and validation. In the 40-location fixed layout, PITCHFORK retains its historical slot before the appended Discovery Labs; the final-page PITCHFORK anchor applies only to `balanced_pages_v1`.

## Archipelago access rules

Location access is the conjunction of three independent conditions:

1. **World Access:** the canonical level's existing region/tier entrance is reachable.
2. **Page frontier:** page zero has no page prerequisite. A later page requires at least four locations on the immediately preceding native page to be reachable.
3. **Recipe capability:** at least one deterministic recipe requirement option for the canonical level is satisfied.

In conceptual form:

```text
can_reach(level) =
  can_enter_world_tier(level)
  AND reachable_count(previous_native_page) >= 4
  AND can_build_target(level)
```

The dependency graph is acyclic because a page references only the immediately preceding page. Transitivity covers all earlier pages.

Archipelago reachability represents locations the player can eventually complete with current items. At runtime, Word Factori itself enforces the actual four completed levels needed to enable the next-page arrow.

The rule builder receives the selected layout explicitly. It must not consult the default global 40-level tuple when generating a 30-level room.

## Regions and World Access

The existing World Access item and canonical region assignments remain in the first implementation. Shuffling changes page placement, not the curated level's recipe or World Access classification. This deliberately allows a page to contain a mixture of immediately usable and later-gated contracts.

World Access remains an independent progression axis. The page-balance validator considers machine dependency diversity; it does not remove intentional World Access gates.

## Slot data and room identity

New rooms include these additional or expanded slot-data fields:

```json
{
  "campaign_id": "word-factori-hybrid",
  "manifest_version": "1.2.0",
  "manifest_digest": "<layout digest>",
  "progression_model": "four_of_six_v1",
  "layout_algorithm": "balanced_pages_v1",
  "page_size": 6,
  "page_unlock_count": 4,
  "base_manifest_digest": "...",
  "layout_digest": "...",
  "level_order": ["complete-i", "complete-cat", "..."],
  "locations": [
    {
      "slot_index": 0,
      "stable_key": "complete-i",
      "name": "Complete I",
      "id": 975301000,
      "kind": "word"
    }
  ]
}
```

The client reconstructs the layout from bundled canonical records and the ordered stable keys. It independently recalculates and validates the layout digest before writing mod files, binding a save, or reporting checks.

The installed `archipelago_campaign.json` adds the progression model, layout algorithm, and layout digest. Campaign compatibility requires all three to match the connected room.

For every new 1.3.0 room, the existing `manifest_digest` compatibility field is set to the layout digest, while `base_manifest_digest` retains the canonical content digest. This makes both shuffled and fixed 1.3.0 layouts distinct from legacy canonical rooms. A 1.2.x client therefore fails closed on the digest comparison instead of accepting a room whose position mapping it cannot understand.

## Legacy room compatibility

The 1.3.0 client recognizes slot data without a progression model as a legacy 1.2.x room. For such a room it uses the canonical fixed order, canonical manifest digest, and legacy index mapping. It does not retrofit shuffled pages or four-of-six AP rules into an already generated server room.

Legacy compatibility is read-and-render support only. New 1.3.0 rooms always emit an explicit progression model and layout identity.

## Client and save reconciliation

Word Factori save files remain read-only. The client performs this translation:

1. Read the set of completed native slot indices from the active bound save.
2. Resolve each native slot through the validated room layout.
3. Convert the corresponding canonical level to its stable AP location code.
4. Reconcile and submit those canonical checks idempotently.

Bridge state stores canonical location identity, not shuffled native slot identity. A reconnect may rebuild the mapping from authoritative slot data, but it must produce the same layout digest before applying save completions.

Manual check resolution continues to use canonical location names and stable keys. Status output will show both the canonical level name and its page/slot position for mapping diagnostics.

The client writes `levels.json` in native slot order. Module limits and received-machine rendering remain properties of the canonical level placed in that slot.

## Victory behavior

- **Campaign Count:** counts completed canonical Core Campaign locations regardless of their shuffled page positions. Discovery Labs do not accidentally replace Core checks in this count.
- **Final Factory:** requires `PITCHFORK — Final Factory`. In shuffled mode the final factory is anchored on the last native page, so reaching it exercises the full page progression of the selected level set. Fixed mode preserves the historical 40-location placement before the appended Discovery Labs.

The existing configurable campaign-count range remains 20–30.

## Failure handling

The integration fails closed when:

- slot data names an unknown layout algorithm;
- stable keys are missing, duplicated, or not part of the selected curated set;
- the layout or installed identity digest does not match;
- a native completion index is outside the validated layout;
- the connected room and installed campaign layouts differ.

In these states the client may continue presenting Archipelago chat and item history, but it does not rewrite the mod or report Word Factori checks. The player receives an actionable campaign-mismatch message.

## Testing strategy

### Pure layout tests

- The same seed and options produce byte-identical layouts and digests.
- Different seeds produce different page compositions.
- Both 30- and 40-location layouts are exact permutations with stable IDs.
- Bootstrap, final-page, challenge, Discovery Lab, page-size, and diversity constraints hold.
- Tampered, duplicate, incomplete, or unknown layout data is rejected.
- Fixed-page mode uses the canonical order through the same layout interface.

### Logic tests

- Locations on the same page do not require one another.
- Page two requires any four reachable page-one locations, not a particular predecessor.
- Three reachable locations do not open the next page; four do.
- Deferred locations remain reachable later when their machines arrive.
- World Access and recipe requirements remain independent of the page threshold.
- Core and Discovery layouts reach victory under full inventory.

### Client and reconciliation tests

- A native slot completion reports the canonical location assigned by the room layout.
- Two layouts map the same native slot to different stable checks without changing AP IDs.
- Duplicate save observations and reconnects do not duplicate checks.
- A layout mismatch blocks mod rewriting and check submission.
- `levels.json` order, campaign identity, and slot data remain consistent.
- Legacy 1.2.x slot data retains canonical mapping.

### Generation tests

- Generate a broad deterministic sample of shuffled rooms for both level sets and both goals under Archipelago 0.6.7.
- Require zero fill failures and zero self-locks.
- Record progression spheres and enforce that sampled shuffled seeds contain multiple simultaneously reachable choices at several pre-goal points.
- Verify that layouts vary across the sample while remaining deterministic when regenerated.

### Live acceptance

On the supported Windows test path:

1. Generate and install a shuffled 40-location room.
2. Confirm that the first page differs from the canonical order while retaining the bootstrap anchors.
3. Complete four of six levels in a noncanonical order.
4. Confirm that the next-page arrow enables after the fourth completion.
5. Leave two levels unfinished, advance, then return and complete one after receiving its missing machine.
6. Confirm that every completion is reported under the correct canonical AP location name.
7. Restart and reconnect; confirm that the same layout and check mapping are restored without duplicate checks.
8. Complete the configured victory condition.

## Documentation and release

The README and tutorial will explain:

- that levels are curated but page composition is randomized;
- the four-of-six page rule;
- why a temporarily blocked level is safe to defer;
- the difference between shuffled and fixed page modes;
- that new shuffled rooms require the 1.3.0 APWorld/client;
- that the mod still uses supported JSON files and read-only save discovery.

The feature ships as version 1.3.0 because it materially changes progression and room slot data. Release notes will include upgrade guidance for active 1.2.x rooms.

## Implementation boundaries

The implementation should keep these responsibilities isolated:

- `campaign.py`: canonical content loading and validation.
- a focused layout module: deterministic layout generation, serialization, digesting, and validation.
- `data.py`: stable AP identity projection and layout-aware runtime entries.
- `requirements.py`: recipe rules and four-of-six page-frontier rules.
- APWorld generation: option handling, layout creation, regions, item pool, and slot data.
- client/mod bridge: slot-data reconstruction, native-index translation, rendering, identity checks, and legacy compatibility.

No unrelated overlay redesign, live-reload work, or proprietary game probing is included in this feature.
