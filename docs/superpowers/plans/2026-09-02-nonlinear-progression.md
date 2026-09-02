# Nonlinear Progression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Word Factori Archipelago 1.3.0 with deterministic seed-specific page composition, Word Factori's native four-of-six progression, stable AP location identities, and safe layout-aware save reconciliation.

**Architecture:** A pure `CampaignLayout` layer owns ordered stable keys, validation, deterministic shuffling, and the layout digest. The APWorld and client both project canonical campaign records through that immutable layout, so AP rules, generated `levels.json`, native save indices, and submitted checks share one mapping. Legacy 1.2.x rooms use a separate canonical compatibility path and never enter shuffled-layout handling.

**Tech Stack:** Python 3.12, Archipelago 0.6.7 world APIs, Python `unittest`, JSON, PowerShell, and Word Factori's supported JSON mod format.

**Spec:** `docs/superpowers/specs/2026-09-02-nonlinear-progression-design.md`

## Global Constraints

- Do not patch or redistribute `data.win`, `recipes.data`, `save.json`, game fonts, or another proprietary/user file.
- Read Word Factori completion state only through the verified active-slot `beaten_levels` object.
- Write only the integration-owned mod directory and the idempotency sidecar.
- Keep every canonical stable key, AP location name, numeric location ID, item name, and numeric item ID unchanged.
- Use six native slots per full page and require any four reachable locations on the immediately preceding page.
- In `shuffled_pages`, keep `Complete I` and `Complete C` on page one, challenges on page three or later, Discovery Labs after page one, and PITCHFORK on the last page.
- In `fixed_pages`, preserve historical canonical order, including PITCHFORK before the appended Discovery Labs in the 40-location set.
- Generate layouts only from the bundled 30- or 40-level manifest selected by the room.
- New rooms use `progression_model: four_of_six_v1`; rooms without that field retain legacy canonical mapping and rules.
- Fail closed on unknown algorithms, malformed orders, or digest mismatches; do not rewrite the mod or submit checks.
- Preserve the single-mod installer workflow and Archipelago 0.6.7 compatibility.
- Target implementation and player-package version 1.3.0.

## File structure

- Create `word_factori/capabilities.py` for canonical machine requirements independent of AP and layout code.
- Create `word_factori/layout.py` for immutable layouts, hashing, validation, fixed order, constrained shuffling, and slot-data parsing.
- Create `tests/test_layout.py` for determinism, constraints, digest validation, variation, and projection.
- Modify `word_factori/data.py` to separate canonical AP identity from native slot position.
- Modify `word_factori/requirements.py` to model recipe capability plus the four-of-six page frontier.
- Modify `word_factori/options.py` and `word_factori/__init__.py` to generate and publish one player-specific layout.
- Modify `word_factori/mod.py`, `word_factori/client_core.py`, and `word_factori/client.py` to render, verify, and reconcile the same layout.
- Modify build, verification, tests, examples, README, tutorial, version metadata, and release evidence for 1.3.0.

---

### Task 1: Canonical capability lookup

**Files:**
- Create: `word_factori/capabilities.py`
- Modify: `word_factori/requirements.py`
- Modify: `tests/test_core.py`

**Interfaces:**
- Consumes: `CampaignRecord` from `word_factori.campaign`.
- Produces: a structural `CapabilityRecord` protocol implemented by both `CampaignRecord` and `LocationData`.
- Produces: `requirements_for_record(record: CapabilityRecord) -> tuple[frozenset[str], ...]`.
- Produces: `unavoidable_nonbootstrap_machines(record: CapabilityRecord) -> frozenset[str]`.
- Preserves: `requirements_for(location: LocationData)` as a wrapper until Task 5 changes the AP rule signature.

- [ ] **Step 1: Write the failing capability tests**

Add to `tests/test_core.py`:

```python
from word_factori.capabilities import (
    requirements_for_record,
    unavoidable_nonbootstrap_machines,
)
from word_factori.campaign import load_campaign


class CapabilityTests(unittest.TestCase):
    def test_challenges_are_keyed_by_stable_identity(self):
        records = {record.stable_key: record for record in load_campaign().levels}
        cat = requirements_for_record(records["challenge-cat-compact"])
        phone = requirements_for_record(records["challenge-phone-no-waste"])
        self.assertEqual(4, len(cat[0]))
        self.assertIn("Merger4 Access", phone[0])

    def test_unavoidable_profile_intersects_every_valid_route(self):
        record = next(x for x in load_campaign().levels if x.stable_key == "complete-v")
        expected = set.intersection(*map(set, requirements_for_record(record)))
        expected.discard("Bender Access")
        self.assertEqual(
            frozenset(expected), unavoidable_nonbootstrap_machines(record),
        )
```

- [ ] **Step 2: Run the test and confirm the missing-module failure**

Run: `py -3 -m unittest tests.test_core.CapabilityTests -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'word_factori.capabilities'`.

- [ ] **Step 3: Implement the dependency-free capability module**

Create `word_factori/capabilities.py`:

```python
from __future__ import annotations

from typing import Protocol

class CapabilityRecord(Protocol):
    stable_key: str
    kind: str
    required_route: frozenset[str]
    requirement_options: tuple[frozenset[str], ...]

FULL = frozenset({
    "Bender Access", "Rotation Access", "Reflection Access",
    "Merger2 Access", "Merger3 Access", "Merger4 Access",
})
CHALLENGE_REQUIREMENTS = {
    "challenge-cat-compact": (
        frozenset({"Bender Access", "Rotation Access", "Reflection Access", "Merger2 Access"}),
    ),
    "challenge-book-low-cycles": (
        frozenset({"Bender Access", "Rotation Access", "Reflection Access", "Merger2 Access", "Merger3 Access"}),
    ),
    "challenge-phone-no-waste": (FULL,),
}

def requirements_for_record(record: CapabilityRecord) -> tuple[frozenset[str], ...]:
    if record.kind == "discovery":
        return (record.required_route,)
    if record.kind == "challenge":
        try:
            return CHALLENGE_REQUIREMENTS[record.stable_key]
        except KeyError as error:
            raise ValueError(f"unknown challenge requirements: {record.stable_key}") from error
    return record.requirement_options

def unavoidable_nonbootstrap_machines(record: CapabilityRecord) -> frozenset[str]:
    routes = requirements_for_record(record)
    if not routes:
        raise ValueError(f"campaign requirements are empty for {record.stable_key}")
    unavoidable = set(routes[0])
    for route in routes[1:]:
        unavoidable.intersection_update(route)
    unavoidable.discard("Bender Access")
    return frozenset(unavoidable)
```

Change `requirements_for()` in `requirements.py` to pass its `LocationData` directly to `requirements_for_record`; remove the index-keyed challenge table there.

- [ ] **Step 4: Run capability and current rule tests**

Run: `py -3 -m unittest tests.test_core.CapabilityTests tests.test_core.DataTests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add word_factori/capabilities.py word_factori/requirements.py tests/test_core.py
git commit -m "refactor: centralize campaign capability requirements"
```

---

### Task 2: Immutable layout model, hashing, and fixed layouts

**Files:**
- Create: `word_factori/layout.py`
- Create: `tests/test_layout.py`

**Interfaces:**
- Consumes: `CampaignManifest`, `CampaignRecord`, and `campaign_digest`.
- Produces: `CampaignLayout`, `LayoutEntry`, `fixed_layout()`, `layout_entries()`, `layout_slot_data()`, `layout_from_slot_data()`, and `validate_layout()`.
- Constants: `PAGE_SIZE = 6`, `PAGE_UNLOCK_COUNT = 4`, `PROGRESSION_MODEL = "four_of_six_v1"`, `FIXED_ALGORITHM = "fixed_pages_v1"`, and `SHUFFLED_ALGORITHM = "balanced_pages_v1"`.

- [ ] **Step 1: Write failing fixed-layout and digest tests**

Create `tests/test_layout.py`:

```python
from dataclasses import replace
import unittest

from word_factori.campaign import campaign_digest, campaign_for_level_set
from word_factori.layout import (
    FIXED_ALGORITHM, PROGRESSION_MODEL, fixed_layout, layout_entries,
    layout_from_slot_data, layout_slot_data, validate_layout,
)

class FixedLayoutTests(unittest.TestCase):
    def test_fixed_layout_preserves_canonical_order_but_has_layout_identity(self):
        manifest = campaign_for_level_set("discovery_labs")
        layout = fixed_layout(manifest, "discovery_labs")
        entries = layout_entries(manifest, layout)
        self.assertEqual(FIXED_ALGORITHM, layout.algorithm)
        self.assertEqual(PROGRESSION_MODEL, layout.progression_model)
        self.assertEqual(tuple(x.stable_key for x in manifest.levels), layout.ordered_stable_keys)
        self.assertEqual(list(range(40)), [entry.slot_index for entry in entries])
        self.assertEqual(list(range(40)), [entry.record.index for entry in entries])
        self.assertNotEqual(campaign_digest(manifest), layout.digest)

    def test_slot_data_round_trip_recalculates_digest(self):
        manifest = campaign_for_level_set("core_campaign")
        original = fixed_layout(manifest, "core_campaign")
        restored = layout_from_slot_data(manifest, "core_campaign", layout_slot_data(original))
        self.assertEqual(original, restored)

    def test_duplicate_order_and_tampered_digest_are_rejected(self):
        manifest = campaign_for_level_set("core_campaign")
        layout = fixed_layout(manifest, "core_campaign")
        duplicate = replace(layout, ordered_stable_keys=(layout.ordered_stable_keys[0],) * 30)
        with self.assertRaisesRegex(ValueError, "stable keys"):
            validate_layout(manifest, duplicate)
        payload = layout_slot_data(layout)
        payload["layout_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest"):
            layout_from_slot_data(manifest, "core_campaign", payload)
```

- [ ] **Step 2: Run the test and confirm the missing-module failure**

Run: `py -3 -m unittest tests.test_layout.FixedLayoutTests -v`

Expected: FAIL because `word_factori.layout` does not exist.

- [ ] **Step 3: Implement canonical layout serialization**

Create immutable types in `layout.py`:

```python
@dataclass(frozen=True)
class CampaignLayout:
    algorithm: str
    level_set: str
    progression_model: str
    base_manifest_digest: str
    ordered_stable_keys: tuple[str, ...]
    digest: str
    page_size: int = PAGE_SIZE
    page_unlock_count: int = PAGE_UNLOCK_COUNT

@dataclass(frozen=True)
class LayoutEntry:
    slot_index: int
    page_index: int
    record: CampaignRecord
```

Hash sorted compact JSON containing exactly `algorithm`, `base_manifest_digest`, `level_set`, `ordered_stable_keys`, `page_size`, `page_unlock_count`, and `progression_model`. `fixed_layout()` creates canonical order, calculates the hash, inserts it with `dataclasses.replace`, and validates.

`validate_layout()` must reject unknown algorithms/models, non-six/four page parameters, base-manifest mismatch, missing/duplicate/unknown keys, noncanonical fixed order, invalid algorithm-specific anchors, and digest mismatch. `layout_slot_data()` returns the exact wire keys below; `layout_from_slot_data()` type-checks those fields, rebuilds the object, and invokes validation. There is no fallback.

```python
return {
    "progression_model": layout.progression_model,
    "layout_algorithm": layout.algorithm,
    "page_size": layout.page_size,
    "page_unlock_count": layout.page_unlock_count,
    "base_manifest_digest": layout.base_manifest_digest,
    "layout_digest": layout.digest,
    "level_order": list(layout.ordered_stable_keys),
}
```

- [ ] **Step 4: Run fixed-layout tests**

Run: `py -3 -m unittest tests.test_layout.FixedLayoutTests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add word_factori/layout.py tests/test_layout.py
git commit -m "feat: add validated campaign layout model"
```

---

### Task 3: Deterministic constrained page shuffling

**Files:**
- Modify: `word_factori/layout.py`
- Modify: `tests/test_layout.py`

**Interfaces:**
- Consumes: a `random.Random`-compatible source.
- Produces: `shuffled_layout(manifest, level_set, random_source) -> CampaignLayout`.
- Produces: `build_layout(manifest, level_set, mode, random_source) -> CampaignLayout`.
- Guarantee: bounded deterministic search returns a validated exact permutation or raises a constraint-naming `ValueError`.

- [ ] **Step 1: Write failing shuffled-layout tests**

Add to `tests/test_layout.py`:

```python
import random
from word_factori.capabilities import FULL, unavoidable_nonbootstrap_machines
from word_factori.layout import build_layout, shuffled_layout

class ShuffledLayoutTests(unittest.TestCase):
    def test_same_seed_is_identical_and_different_seeds_vary(self):
        manifest = campaign_for_level_set("discovery_labs")
        first = shuffled_layout(manifest, "discovery_labs", random.Random(1408))
        repeat = shuffled_layout(manifest, "discovery_labs", random.Random(1408))
        other = shuffled_layout(manifest, "discovery_labs", random.Random(1409))
        self.assertEqual(first, repeat)
        self.assertNotEqual(first.ordered_stable_keys, other.ordered_stable_keys)

    def test_constraints_hold_for_both_sets_across_200_seeds(self):
        for level_set in ("core_campaign", "discovery_labs"):
            manifest = campaign_for_level_set(level_set)
            records = {record.stable_key: record for record in manifest.levels}
            for seed in range(200):
                layout = shuffled_layout(manifest, level_set, random.Random(seed))
                pages = [layout.ordered_stable_keys[i:i + 6] for i in range(0, len(layout.ordered_stable_keys), 6)]
                self.assertTrue({"complete-i", "complete-c"} <= set(pages[0]))
                self.assertIn("pitchfork-final", pages[-1])
                self.assertFalse(any(records[key].kind in {"challenge", "discovery", "final"} for key in pages[0]))
                for page_index, page in enumerate(pages):
                    self.assertFalse(page_index < 2 and any(records[key].kind == "challenge" for key in page))
                    if len(page) == 6:
                        profiles = {unavoidable_nonbootstrap_machines(records[key]) for key in page}
                        self.assertGreaterEqual(len(profiles), 3)
                        for machine in FULL - {"Bender Access"}:
                            count = sum(machine in unavoidable_nonbootstrap_machines(records[key]) for key in page)
                            self.assertLess(count, 4)
```

- [ ] **Step 2: Run the test and confirm missing symbols**

Run: `py -3 -m unittest tests.test_layout.ShuffledLayoutTests -v`

Expected: FAIL because the shuffled builders do not exist.

- [ ] **Step 3: Implement bounded deterministic page construction**

Assign one priority per record from `random_source.random()` and order candidates by `(priority, stable_key)`. Build pages with recursive backtracking and a 100,000-attempt budget. Reserve I and C for page zero and require PITCHFORK somewhere on the final page. Reject a candidate when its kind violates page restrictions. Accept each complete page only when:

```python
len({unavoidable_nonbootstrap_machines(records[key]) for key in page}) >= 3
and all(
    sum(machine in unavoidable_nonbootstrap_machines(records[key]) for key in page) < 4
    for machine in FULL - {"Bender Access"}
)
```

Use deterministic candidate order at every search node. Shuffle the completed first page once with the supplied source so I and C do not always occupy the same buttons. On budget exhaustion raise `ValueError("balanced_pages_v1 could not satisfy page constraints")`; never weaken constraints. Calculate the digest and call `validate_layout()` before returning.

`build_layout()` accepts only `fixed_pages` and `shuffled_pages` and dispatches to the matching builder.

- [ ] **Step 4: Run the layout suite twice**

```powershell
py -3 -m unittest tests.test_layout -v
py -3 -m unittest tests.test_layout -v
```

Expected: both runs PASS with identical counts.

- [ ] **Step 5: Commit**

```powershell
git add word_factori/layout.py tests/test_layout.py
git commit -m "feat: generate deterministic balanced pages"
```

---

### Task 4: Layout-aware location projection and mod rendering

**Files:**
- Modify: `word_factori/data.py`
- Modify: `word_factori/mod.py`
- Modify: `tools/build_game_mod.py`
- Modify: `tests/test_core.py`
- Modify: `tests/test_layout.py`

**Interfaces:**
- Produces: `LocationData.canonical_index`, `.slot_index`, `.page_index`, and unchanged `.code` based on canonical index.
- Produces: `locations_for_layout(manifest, layout) -> tuple[LocationData, ...]` in native slot order.
- Changes: `write_campaign_identity(path, manifest, layout: CampaignLayout | None)` writes layout-aware identity when layout is present and canonical legacy identity when it is absent.

- [ ] **Step 1: Write failing projection tests**

Add to `tests/test_layout.py`:

```python
from word_factori.data import BASE_ID, locations_for_layout
from word_factori.mod import render_levels

class LayoutProjectionTests(unittest.TestCase):
    def test_shuffling_changes_slots_without_changing_ap_codes(self):
        manifest = campaign_for_level_set("core_campaign")
        layout = shuffled_layout(manifest, "core_campaign", random.Random(72))
        locations = locations_for_layout(manifest, layout)
        by_key = {location.stable_key: location for location in locations}
        self.assertEqual(BASE_ID + 1000, by_key["complete-i"].code)
        self.assertEqual(BASE_ID + 1029, by_key["pitchfork-final"].code)
        self.assertEqual(list(range(30)), [location.slot_index for location in locations])
        rendered = render_levels({"Bender Access"}, 0, locations=locations)
        self.assertEqual([x.target for x in locations], [level["text"] for level in rendered])
```

Update `tests/test_core.py` to assert canonical and slot indices explicitly. Add an identity test expecting `manifest_digest == layout.digest`, `base_manifest_digest == campaign_digest(manifest)`, and all progression fields.

- [ ] **Step 2: Run projection and mod tests**

Run: `py -3 -m unittest tests.test_layout.LayoutProjectionTests tests.test_core.ModTests -v`

Expected: FAIL because `LocationData` does not separate canonical and slot positions.

- [ ] **Step 3: Split stable identity from native position**

Change `LocationData` to include:

```python
canonical_index: int
slot_index: int
page_index: int

@property
def code(self) -> int:
    return BASE_ID + 1000 + self.canonical_index
```

Implement `locations_for_layout()` from `layout_entries()`. Keep `locations_for_manifest()` as legacy canonical projection with equal canonical/slot indices. Run `rg -n "location\.index|\.index for location|x\.index" word_factori tests tools` and update every result to choose `canonical_index` or `slot_index` explicitly.

- [ ] **Step 4: Write complete layout identity and bootstrap mod**

Make `write_campaign_identity()` write campaign ID/version, layout digest in both `manifest_digest` and `layout_digest`, base manifest digest, progression model, algorithm, page size, unlock count, and level count when layout is present. With `layout=None`, write the canonical manifest digest/count only for legacy-room support. Update `tools/build_game_mod.py` to build the 40-level fixed layout, project its locations, render them, and write its identity. Run `py -3 tools/build_game_mod.py` so the tracked bootstrap `levels.json` and `archipelago_campaign.json` match 1.3.0 behavior.

- [ ] **Step 5: Run projection, mod, campaign, and recipe tests**

Run: `py -3 -m unittest tests.test_layout tests.test_core.ModTests tests.test_campaign tests.test_recipe_graph -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add word_factori/data.py word_factori/mod.py tools/build_game_mod.py tests/test_core.py tests/test_layout.py "game_mod/word factori archipelago/levels.json" "game_mod/word factori archipelago/archipelago_campaign.json"
git commit -m "feat: render stable locations in shuffled slots"
```

---

### Task 5: APWorld option, four-of-six rules, goals, and slot data

**Files:**
- Modify: `word_factori/options.py`
- Modify: `word_factori/requirements.py`
- Modify: `word_factori/__init__.py`
- Modify: `examples/WordFactori.yaml`
- Modify: `examples/WordFactoriTarget.yaml`
- Modify: `tests/test_core.py`
- Create: `tests/test_world_layout.py`

**Interfaces:**
- Produces: `CampaignLayoutOption` values `fixed_pages = 0`, `shuffled_pages = 1`, default shuffled.
- Produces: `access_rule_for(location, locations, player)` using the selected slot-ordered tuple.
- Produces: authoritative new-room layout slot data.

- [ ] **Step 1: Replace sequential tests with failing four-of-six tests**

Use this state in `tests/test_core.py`:

```python
class State:
    def __init__(self, items, reachable):
        self.items = set(items)
        self.reachable = set(reachable)
    def has_all(self, names, player):
        return set(names) <= self.items
    def can_reach_location(self, name, player):
        return name in self.reachable
```

Assert a first-page location requires no sibling, a slot-six location fails with three reachable page-one names and passes with four, and recipe requirements still fail when the frontier is open but machines are absent. Assert a page-three location's direct predecessor set is exactly slots 6–11.

- [ ] **Step 2: Run rule tests and confirm the old signature fails**

Run: `py -3 -m unittest tests.test_core.DataTests -v`

Expected: FAIL because `access_rule_for` still models one predecessor.

- [ ] **Step 3: Implement the native page frontier**

```python
def previous_page_names(location, locations):
    if location.slot_index < PAGE_SIZE:
        return ()
    start = ((location.slot_index // PAGE_SIZE) - 1) * PAGE_SIZE
    return tuple(entry.name for entry in locations[start:start + PAGE_SIZE])

def access_rule_for(location, locations, player):
    needs = requirements_for(location)
    predecessors = previous_page_names(location, locations)
    def rule(state):
        if predecessors and sum(state.can_reach_location(name, player) for name in predecessors) < PAGE_UNLOCK_COUNT:
            return False
        return any(state.has_all(route, player) for route in needs)
    return rule
```

Import both page constants from `layout.py`; never consult global `LOCATIONS` in the rule builder.

- [ ] **Step 4: Add the option and cache one player layout**

Add `CampaignLayoutOption(Choice)` with fixed value 0, shuffled value 1, and default 1. Add it to `WordFactoriOptions`.

In `WordFactoriWorld.generate_early()`, select and cache the manifest, call `build_layout(..., self.random)`, cache projected locations, then precollect Bender Access. All later lifecycle methods consume these cached objects.

In `create_regions()`, pass the selected locations to every rule. Campaign Count uses all non-discovery canonical names; Final Factory uses the stable PITCHFORK name. `fill_slot_data()` merges `layout_slot_data()` and includes `manifest_digest` equal to layout digest plus ordered rows containing `slot_index`, `stable_key`, `name`, `id`, and `kind`.

- [ ] **Step 5: Add headless world slot-data tests**

Create `tests/test_world_layout.py` using the repository's existing module-stub pattern and assert:

```python
self.assertEqual("four_of_six_v1", slot_data["progression_model"])
self.assertEqual(6, slot_data["page_size"])
self.assertEqual(4, slot_data["page_unlock_count"])
self.assertEqual(slot_data["manifest_digest"], slot_data["layout_digest"])
self.assertEqual(list(range(len(slot_data["locations"]))), [x["slot_index"] for x in slot_data["locations"]])
self.assertEqual(
    {BASE_ID + 1000 + i for i in range(len(slot_data["locations"]))},
    {x["id"] for x in slot_data["locations"]},
)
```

Two same-seed instances must emit identical slot data; another seed must change `level_order`.

- [ ] **Step 6: Update examples and run world-facing tests**

Add `campaign_layout: shuffled_pages` to both YAMLs. Run:

`py -3 -m unittest tests.test_core tests.test_world_layout tests.test_apworld_namespace -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add word_factori/options.py word_factori/requirements.py word_factori/__init__.py examples/WordFactori.yaml examples/WordFactoriTarget.yaml tests/test_core.py tests/test_world_layout.py
git commit -m "feat: model native four-of-six progression"
```

---

### Task 6: Client reconstruction, save translation, and legacy rooms

**Files:**
- Modify: `word_factori/client_core.py`
- Modify: `word_factori/client.py`
- Modify: `tests/test_core.py`
- Modify: `tests/test_client_lifecycle.py`

**Interfaces:**
- Produces: `ResolvedCampaign(manifest, layout, locations, legacy)`.
- Produces: `resolve_room_campaign(slot_data) -> ResolvedCampaign`.
- Produces: `location_codes_for_native_slots()` and `native_slots_for_location_codes()`.
- Changes: bridge reconciliation operates on stable AP location codes; native indices exist only at the save boundary.

- [ ] **Step 1: Write failing pure resolver and mapping tests**

In `tests/test_core.py`, create a shuffled layout/slot payload and assert:

```python
resolved = resolve_room_campaign(slot_data)
expected = frozenset({resolved.locations[0].code, resolved.locations[7].code})
self.assertEqual(expected, location_codes_for_native_slots({0, 7}, resolved.locations))
self.assertEqual(frozenset({0, 7}), native_slots_for_location_codes(expected, resolved.locations))
```

Assert Campaign Count uses 20 canonical non-discovery codes and Final Factory detects the code whose stable key is `pitchfork-final`, regardless of native slot. Add cases for an ignored out-of-range native index, duplicated key rejection, digest mismatch rejection, and a 1.2.x payload without `progression_model` resolving canonical order with `legacy is True`.

- [ ] **Step 2: Run pure client tests and confirm missing APIs**

Run: `py -3 -m unittest tests.test_core.ClientCoreTests -v`

Expected: FAIL because room resolution and translation functions do not exist.

- [ ] **Step 3: Implement strict new/legacy room resolution**

Add:

```python
@dataclass(frozen=True)
class ResolvedCampaign:
    manifest: CampaignManifest
    layout: CampaignLayout | None
    locations: tuple[LocationData, ...]
    legacy: bool
```

`resolve_room_campaign()` loads only the bundled selected level set and verifies ID, manifest version, and count. Without `progression_model`, require the canonical manifest digest and return canonical locations. With it, require `four_of_six_v1`, rebuild via `layout_from_slot_data()`, require `manifest_digest == layout.digest`, and project through `locations_for_layout()`.

Translation functions use validated `slot_index`/`code` dictionaries, reject duplicate mapping keys, and exclude only native indices outside the layout. Extend `campaign_compatible()` to compare every new identity field when present.

- [ ] **Step 4: Write failing lifecycle reconciliation cases**

Add helpers in `tests/test_client_lifecycle.py` that install a seeded shuffled room. Test that native slot 7 submits the canonical code assigned to slot 7 exactly once across duplicate scans and reconnect. Test mismatched layout digest blocks both `levels.json` rewriting and checks, legacy rooms remain canonical, manual completion by canonical name resolves its shuffled native slot, and diagnostics show canonical name plus page/slot.

- [ ] **Step 5: Make the client consume one validated room mapping**

Replace `selected_campaign()` with a resolver-backed method and make `active_locations()` return slot order. `prepare_selected_campaign()` renders that order and writes either new layout identity or legacy canonical identity.

Change `report_indices()` to:

```python
observed_codes = location_codes_for_native_slots(indices, locations)
server_codes = frozenset(self.checked_locations) & {location.code for location in locations}
result = reconcile(self.bridge_state, [], observed_codes, server_codes)
location_ids = set(result.new_checks) - self.bridge_state.pending_checks
```

Queue/submit those codes directly and evaluate victory against `server_codes | observed_codes`. `resolve_location()` returns native `slot_index`; numeric input remains displayed one-based slot, while target/name matching remains canonical. Include `page_index + 1` and `(slot_index % 6) + 1` in diagnostics.

- [ ] **Step 6: Run client, bridge, dispatch, and overlay tests**

Run:

`py -3 -m unittest tests.test_core tests.test_client_lifecycle tests.test_dispatch tests.test_overlay_model tests.test_overlay_supervisor -v`

Expected: PASS, including duplicate check, reconnect, mismatch, reload, and overlay isolation coverage.

- [ ] **Step 7: Commit**

```powershell
git add word_factori/client_core.py word_factori/client.py tests/test_core.py tests/test_client_lifecycle.py
git commit -m "feat: reconcile shuffled save slots safely"
```

---

### Task 7: Version, documentation, packaging, and verification

**Files:**
- Modify: `word_factori/version.py`
- Modify: `word_factori/archipelago.json`
- Modify: `tools/build_release.py`
- Modify: `tools/verify_release.py`
- Modify: `tests/test_publication.py`
- Modify: `README.md`
- Modify: `word_factori/docs/setup_en.md`
- Create: `docs/release-notes-v1.3.0.md`
- Create: `docs/testing/nonlinear-progression-acceptance.md`

**Interfaces:**
- Produces: `word-factori-archipelago-1.3.0.zip` and an APWorld containing `capabilities.py` and `layout.py`.
- Preserves: AP range 0.6.7, metadata compatibility floor 7, author `Akamarus`, and the approved AI-assistance disclosure.

- [ ] **Step 1: Write failing publication assertions**

Assert in `tests/test_publication.py` that world version is 1.3.0, AP minimum/maximum stay 0.6.7, metadata `version` is 9 and `compatible_version` remains 7, both new runtime modules are in the APWorld, examples select `shuffled_pages`, README explains “four of the six,” and attribution still begins `Created and maintained by Jack (@Akamarus)`.

- [ ] **Step 2: Run publication tests and confirm version/content failures**

Run: `py -3 -m unittest tests.test_publication -v`

Expected: FAIL because metadata is 1.2.2 and packaging/docs do not include the feature.

- [ ] **Step 3: Update version and build inputs**

Set `VERSION = "1.3.0"`, `world_version` to `1.3.0`, metadata `version` to 9, and keep `compatible_version` at 7 without changing AP bounds. Add `word_factori/capabilities.py` and `word_factori/layout.py` to `WORLD_SOURCE_NAMES`.

Update `tools/verify_release.py` to construct the default 40-level fixed layout, project it, verify `levels.json` in native slot order, and compare the full installed layout identity. Retain archive parity and proprietary-data exclusions.

- [ ] **Step 4: Rewrite player-facing progression documentation**

README/tutorial must explain seed-specific six-level pages, any-four unlocking, safe deferral/revisit, the `fixed_pages` option, stable AP identities despite moved slots, 1.3.0 requirement for new rooms, legacy 1.2.x room support, read-only saves, and supported JSON writes. Remove claims that progression is one level at a time, Labs are always post-campaign, or every visible level is required.

Create release notes saying existing rooms keep their generated server logic and only newly generated 1.3.0 rooms use shuffled pages.

- [ ] **Step 5: Create an honest acceptance matrix**

The acceptance document must list 30/40 generation, deterministic digest, seed variation, three-versus-four arrow behavior, deferral, native-to-canonical mapping, reconnect idempotency, both goals, legacy room connection, and mismatch blocking. Mark live-only rows `Pending live test` until observed.

- [ ] **Step 6: Run the complete automated pipeline**

Run: `powershell -ExecutionPolicy Bypass -File .\tools\verify.ps1`

Expected: build succeeds, all tests pass, and release verification reports parity plus data exclusions.

- [ ] **Step 7: Commit**

```powershell
git add word_factori/version.py word_factori/archipelago.json tools/build_release.py tools/verify_release.py tests/test_publication.py README.md word_factori/docs/setup_en.md docs/release-notes-v1.3.0.md docs/testing/nonlinear-progression-acceptance.md
git commit -m "docs: prepare nonlinear progression release"
```

---

### Task 8: AP 0.6.7 generation matrix and live acceptance

**Files:**
- Create: `tools/verify_generation_matrix.py`
- Modify: `docs/testing/nonlinear-progression-acceptance.md`
- Generated but not committed: APWorld, player ZIP, temporary AP outputs, and temporary YAML copies.

**Interfaces:**
- Consumes: built 1.3.0 artifacts, Archipelago 0.6.7, both goals/level sets, and a clean Word Factori mod save.
- Produces: truthful recorded evidence and defects that must be resolved before merge.

- [ ] **Step 1: Install the local build after explicit approval**

Run: `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force`

Create temporary player directories outside the repository for Core/Discovery crossed with Campaign Count/Final Factory, all with shuffled pages.

- [ ] **Step 2: Generate the option matrix across 50 seeds**

Create `tools/verify_generation_matrix.py` as a local verification driver. It must invoke the installed 0.6.7 generator for seeds 13000–13049 and each of the four player files, request spoiler level 3, fail on any nonzero exit, and parse the resulting spoiler logs. For every room, record the number of pre-goal progression spheres containing at least two reachable Word Factori locations and require at least three such spheres.

The subprocess command for every case is:

```powershell
& 'C:\ProgramData\Archipelago\ArchipelagoGenerate.exe' --player_files_path $MatrixDirectory --seed $Seed --outputpath $OutputDirectory --spoiler 3 --skip_prog_balancing
```

Expected: all 200 generations exit 0 without fill failure, self-lock, invalid layout, or unknown option, and every sampled spoiler contains at least three pre-goal spheres with multiple Word Factori choices. Remove only the explicitly created temporary directories after recording results.

- [ ] **Step 3: Verify deterministic identity**

Regenerate seed 13000 twice from one YAML into separate empty directories and compare the extracted `level_order` and `layout_digest`. Generate 13001 and assert at least one page differs while stable-key and AP-ID sets remain equal.

- [ ] **Step 4: Perform live four-of-six acceptance**

With a clean bound save, record six page-one targets, arrow disabled after three completions, arrow enabled after four, page two opening with two unfinished checks, a deferred level completed after its machine arrives, correct canonical AP names for native slots, identical mapping after reconnect/restart, no duplicated checks, and one goal update.

- [ ] **Step 5: Record exact evidence**

For every exercised row, record date, Word Factori build, AP version, seed, layout-digest prefix, and Pass/Fail. Leave unexercised environments visibly pending.

- [ ] **Step 6: Run final verification and diff hygiene**

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\verify.ps1
git diff --check
git status --short
```

Expected: verification passes, diff check is silent, and only intentional evidence or ignored build artifacts remain.

- [ ] **Step 7: Commit observed evidence**

```powershell
git add tools/verify_generation_matrix.py docs/testing/nonlinear-progression-acceptance.md
git commit -m "test: record nonlinear progression acceptance"
```

Do not merge, tag, push, or publish 1.3.0 in this task. First run the requesting-code-review and verification-before-completion workflows, then present the verified branch for the maintainer's release decision.
