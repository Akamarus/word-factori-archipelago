# Optional progressive machines

Status: written specification for review. The in-chat design was approved; implementation has not started.

## Player experience and scope

Add `progressive_machines`, a YAML toggle defaulting to `false`. This is an option within the existing integration, not a second edition or installer. Off preserves existing machine access, item pool, rules and native behavior.

```yaml
Word Factori:
  progressive_machines: true
```

When enabled, the six machine families each have five progressive tiers: one, two, three, four, then unlimited simultaneously placed machines. Zero tiers means unavailable. The families are Bender, Rotation, Reflection, Merger2, Merger3 and Merger4. Clockwise/counterclockwise rotation share one Rotation allowance, and horizontal/vertical reflection share one Reflection allowance.

Start with the first Bender tier and unlimited I sources. I sources, pipes and target receivers do not consume a progressive allowance. Upgrades are permanent, not consumables. A fifth tier removes the AP family limit but does not remove the level's own challenge restrictions. A first-tier Bender is not equivalent to the old unlimited Bender Access item.

New items are named Progressive Bender Access, Progressive Rotation Access, Progressive Reflection Access, Progressive Merger2 Access, Progressive Merger3 Access and Progressive Merger4 Access. Allocate new stable IDs without renumbering existing items or locations. Five copies of each family are required in the total inventory, including one precollected Bender: 29 items in the random pool. Fill remaining locations with existing filler. Optional checks add room for filler, not additional mandatory machine tiers. Reject insufficient-capacity configurations with an actionable generation error rather than dropping progression items.

Player-provided starting inventory is accounted for by the normal AP pool removal/precollection mechanisms; the mandatory first Bender is granted exactly once. Counts saturate at five for entitlement purposes. Additional copies do not increase unlimited access or overflow counters.

No page-order, page-unlock, location identity, victory, recipe-discovery or Type-a-Word selection changes are included. Enabling the option must work with either campaign, recipe checks on/off, and Type-a-Word orders on/off. It must not require recipe checks merely to avoid a dead start.

## Architecture

Introduce a small pure quantity module and a versioned, derived budget catalog. They provide one representation for family counts, item-to-tier conversion, whole-route affordability and missing-upgrade explanations. World generation, regular client and Universal Tracker use this same implementation; no copied threshold tables.

Integration points are `options.py`, world construction, item data, requirements/capabilities, word orders, bridge/client inventory, room resolution, native runtime publication and the authored native enforcement helper. Keep legacy/off paths intact. Use separate quantity functions instead of making existing boolean capability sets secretly represent counts.

The slot contract contains the enabled flag and, when enabled, the quantity-model version and catalog digest. Bind the option, model and selected per-check budgets into the existing room/check identity. Validate them before any progression/check scanning or native publication. A client must not silently ignore an enabled option, reinterpret a corrupt value as off, or derive a different catalog than the generator.

Absent flags in older contracts retain their existing off semantics. Unknown quantity versions fail with a clear matching-release message. Universal Tracker reconstruction takes the room's authoritative option, campaign layout, selected words and budget identity rather than local YAML defaults.

## Quantity-aware logic

Use verified constructive factory graphs as witnesses. A location is machine-reachable when at least one complete budget vector fits the received family allowances and that level's restrictions. Keep the existing page access conditions as an additional requirement for campaign locations. Recipe journal and free-word locations keep their existing independent access semantics.

Never combine the smallest component from different budget vectors. Never replace quantity checks with possession of one item. Recipe discovery requires the exact final operation and its upstream producers, not merely a route to the output letter.

The research covers all 187 AP recipes and A–Z. Import only the needed derived graph data and metadata, with validation of acyclic references, arities, native transitions, counts and exact recipe identity. Retain provenance/digests and an authored regeneration/verification path. Do not copy native binaries, extracted game source, private test logs or saves into the repository.

For campaign words and user-supplied Type-a-Word orders, construct complete multi-output factories: combine candidate letter graphs, share genuinely identical producers, connect the actual native word receiver/assembly path, and count each distinct machine once. Repeated letters may share a producer when native fan-out allows it. Neither the sum nor the maximum of independent letter minima is treated as the exact word budget. An unshared union is an acceptable conservative witness only when the resulting complete graph is valid, including target delivery.

Use deterministic, bounded candidate generation with stable ordering and caching by word, level restrictions and catalog version. Retaining a limited set of verified alternatives is acceptable; returning an optimistic budget is not. Include a known valid fallback witness so pruning cannot remove all ways to complete a supported target at full inventory. If no graph fits a campaign's native restrictions, treat that as a verification/generation failure, not an unreachable location to ship silently.

Challenge and discovery-lab restrictions still apply. Filter/construct graphs under their native per-module caps and allowed families as well as AP family limits. Challenges must retain their existing completion semantics. A graph that merely produces the letters does not certify efficiency/no-waste conditions; require separately verified challenge witnesses where those conditions affect the check.

Document that this is conservative logic: some clever factories involving other trade-offs, mixed streams or rewiring may complete checks out of logic. Do not block legitimate completion simply because its graph is absent from the catalog. Native limits enforce actual entitlements, not catalog membership. Do not claim exhaustive optimality.

## Native enforcement and live updates

Version the quantity-capable native runtime protocol and capability acknowledgment. Old clients/patches cannot authorize quantity-mode completion by presenting a boolean-access acknowledgment. Keep the exact build verification and platform-safe installer conventions already used by the project.

Publish room-bound, monotonically revised full entitlement snapshots atomically. Treat item deliveries as indexed AP events: two distinct copies count twice; replaying the same delivery does not. Reconnection rebuilds the same tier counts from authoritative received items and precollection. Do not increment tiers merely because a snapshot was republished or a check was repeated.

While the game is running, validated upgrades refresh placement availability and existing-factory eligibility without a game/mod reload or reentering the level. Ignore older revisions and reject conflicting payloads with the same revision. A same-room disconnect retains last validated entitlements; a room change cannot reuse them. A fresh quantity context with no valid snapshot permits only the bootstrap inventory. Malformed updates never grant unlimited machines.

Finite family limits require aggregate placement accounting, not just separate per-direction native counts. All placed machines count, even disconnected ones. Level-specific directional caps and the shared AP family cap are both enforced. Native custom-building paths stay blocked until their internal quantities can be verified; this feature does not introduce an uncounted shortcut.

Cover normal placement, duplication, undo/redo, saved/imported factories, resumed simulations, campaign levels, recipe farming and free-word modes. Keep removal and editing possible while over budget. Never delete a saved layout to enforce a limit.

If an imported/restored factory is over a family or level limit, preserve it, stop/refuse simulation, and show the affected family with used/allowed counts. Check legality before production or delivery can award a recipe/word/campaign check, including buffered outputs. Do not selectively disable arbitrary machines and let the rest earn checks. An upgrade that makes the whole factory legal restores eligibility; starting the simulation remains under player control.

The player-facing client lists each family's current allowance and, for missing requirements, one or more whole-route upgrade alternatives. Distinguish missing machine quantities from a locked page or native challenge restriction. Reuse existing presentation; no separate overlay redesign is included.

## Verification and acceptance

The existing suite must pass unchanged with the option off. Add focused tests before implementation for:

- All tier boundaries, unlimited behavior, shared direction budgets and one starting Bender.
- Correct 29-item progression pool, item IDs/classifications, filler counts and configured starting inventory.
- Exact recipe budgets, alternative routes, genuine sharing and repeated-letter words; avoid sum/max shortcuts.
- Positive/negative native restrictions for discovery labs and challenges.
- Deterministic generation, page-aware spheres and victory for both campaigns with optional check combinations, including core-only 30 checks.
- Native placement/duplication/import/undo limits, blocked production and buffered completion from illegal factories, preservation of layouts, and removal restoring eligibility.
- Live upgrades without reload, duplicate received packets, distinct repeated items, reconnect, room change, stale/conflicting revisions and malformed snapshots.
- Exact Universal Tracker reconstruction and matching world/client reachability for representative quantity inventories and page states.
- Budget generation and AP generation timings, cached repeated evaluation, and a documented before/after comparison; do not reintroduce a large generation delay unnoticed.
- Windows and Linux installer packaging/receipt validation for the new runtime contract, with no claim of a live Proton test without one.

Use isolated native test copies first. Prove representative full-word/challenge witnesses and every newly admitted native operation behavior; unit tests of Python counts alone are insufficient. Follow with a connected AP/client/tracker acceptance playthrough showing a finite limit, a live upgrade and a restored over-limit layout. Clearly separate automated evidence from live user testing.

## Delivery boundaries

Implement and verify in the existing isolated development checkout based on the unpublished Type-a-Word work. Do not push, publish, modify the live installation, replace an active seed or alter user saves under this approval. Provide a tested development artifact and list remaining live acceptance gates before a release is proposed.

Success means a complete optional feature, not merely a YAML flag or a different item pool. If a required native enforcement path or conservative whole-word witness cannot be made reliable, report the concrete blocker and keep the feature unreleased rather than silently weakening enforcement or disabling another option.

## Spec self-review

Reviewed against the approved in-chat design and current boolean-access implementation. Defaults, tier meaning, item count, shared-direction accounting, off-mode compatibility, conservative logic, live updates, save preservation and release boundaries are explicit. Research minima are not mislabeled as a complete frontier. Whole-word and challenge validation remain mandatory implementation acceptance work, not assumed research results.
