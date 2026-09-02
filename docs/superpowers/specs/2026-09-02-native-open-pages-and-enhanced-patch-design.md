# Native Open Pages and Enhanced Patch Design

**Status:** Approved in chat; written specification pending user review

**Date:** 2026-09-02

**Target release:** Word Factori Archipelago 1.3.0 experimental beta

## Summary

Word Factori Archipelago will use the game's actual campaign behavior instead
of the incorrect assumption that all six first-page levels are immediately
selectable. The supported mode keeps a fixed six-level introduction in native
order, then provides deterministic shuffled pages with genuine four-of-six
route choice. An optional enhanced mode will be prototyped against a verified
player-owned `data.win` to remove the remaining first-page restriction and make
received machine permissions effective without restarting or reselecting the
mod.

The supported campaign must remain fully playable without modifying
proprietary binaries. Enhanced mode is optional, version-locked, reversible,
and fails closed. Type-a-Word remains a fallback research path rather than the
primary campaign.

## Evidence and corrected native behavior

Live testing established that only the first level was selectable when the
first page was shuffled into an unsafe order. Writing experimental unlock data
to a guessed save slot did not affect the selected slot and exposed that the
current active-slot assumption is not safe for writes.

Read-only inspection of an isolated copy of the installed game established:

- Word Factori is a GameMaker Studio 2 VM build, not YYC.
- The installed `data.win` uses bytecode version 17 and contains editable code
  entries.
- Page one is a sequential tutorial: each level depends on its predecessor.
- The second page requires all six first-page levels.
- Completing native slot six globally enables later numbered level buttons.
- After the tutorial, a later page opens after four levels on the preceding
  page.
- Level module limits are captured when a factory is entered.

The inspected Steam build's `data.win` SHA-256 is
`D40CE3C6A37281C0BCE46D8A631CD7DD7749334C7892F45669791D64E4E86978`.
This identifies evidence for the current build only; it is not a promise that
future builds share the same code.

No decompiled proprietary source, original binary, recipes, fonts, saves, or
other game assets may enter the repository or release artifacts.

## Player experience

### Supported mode

1. Page one is always `I`, `C`, `V`, `L`, `O`, `A`.
2. The player completes those six levels in order as a short introduction.
3. Page two and every later page have seed-specific curated level membership
   and order.
4. Every level on an unlocked later page is selectable.
5. Completing any four levels on a later full page opens the next page. The
   other two may be deferred and revisited.
6. Location identity follows the curated target, never its shuffled native
   slot.

Only the six-level introduction is shared across seeds. The remaining 24 Core
Campaign levels or 34 Discovery Labs levels are shuffled subject to balance
constraints.

### Optional enhanced mode

When the installed game hash is recognized and the player explicitly enables
enhanced mode, the installer applies a reversible patch to the player's own
copy. For the Word Factori Archipelago mod only, enhanced mode will:

- make all six visible levels selectable on the first page;
- use four first-page completions to open page two;
- keep all later visible page levels independently selectable;
- refresh AP-controlled machine limits when a factory is entered, so a newly
  received machine is usable on the next factory entry without restarting the
  game or reselecting a save.

The patch must not change vanilla saves or behavior when another mod or the
base campaign is selected.

If any enhanced capability cannot be implemented narrowly and reliably, that
capability is omitted from enhanced mode rather than emulated through hidden
save completion flags. The supported mode remains available.

## Progression and layout model

The corrected supported progression model is
`tutorial_six_then_four_v1`. The corrected shuffled layout algorithm is
`balanced_pages_v2`. These identifiers intentionally differ from the invalid
experimental `four_of_six_v1` and `balanced_pages_v1` contracts.

The first six stable keys are fixed in canonical order:

```text
complete-i
complete-c
complete-v
complete-l
complete-o
complete-a
```

The remaining selected records are deterministically shuffled with the
player-specific Archipelago random source. `PITCHFORK — Final Factory` remains
anchored to the last page in shuffled mode. Challenge levels remain out of the
first two pages. Later full pages retain machine-profile diversity and the
existing conservative repetition caps unless generation testing proves a
stricter order-aware constraint is needed.

Fixed-page mode uses the same corrected progression model but preserves the
canonical order throughout.

Enhanced rooms use the separate explicit progression model
`enhanced_four_of_six_v1`. A client must never infer enhanced rules solely from
the presence of a patched binary. The room contract, installed campaign
identity, client mode, and patch status must all agree.

## Archipelago rules

Supported-mode location access is the conjunction of world access, the native
page prerequisite, and deterministic recipe capability.

Page prerequisites are:

- slot 0: no predecessor;
- page-one slots 1 through 5: the immediately preceding native slot must be
  reachable;
- every slot on page two: all six page-one locations must be reachable;
- every slot on page three or later: at least four locations on the immediately
  preceding native page must be reachable.

There are no sibling prerequisites inside later pages. This mirrors the
game-wide release that occurs when native slot six is complete.

Enhanced-mode rules remove page-one sibling prerequisites and require four
reachable locations on every previous full page, including page one.

The APWorld must request early local placements sufficient to solve the fixed
tutorial. Real Archipelago generation—not a custom approximation—must prove
that Merger2, Rotation, and any other unavoidable tutorial capabilities cannot
self-lock.

## Slot data and compatibility

Slot data continues to include the deterministic stable-key order, page size,
base manifest digest, layout digest, algorithm, and progression model. It adds
an explicit integration mode and represents both native thresholds:

```json
{
  "integration_mode": "supported" | "enhanced",
  "progression_model": "tutorial_six_then_four_v1",
  "layout_algorithm": "balanced_pages_v2",
  "tutorial_page_unlock_count": 6,
  "later_page_unlock_count": 4
}
```

Enhanced rooms use `4` for both thresholds and their enhanced progression
model. The old single `page_unlock_count` field is accepted only when reading
the legacy room contracts that defined it.

The layout digest covers the integration mode and every layout-defining field.
The client rejects unknown progression models, mode mismatches, tampered order,
and digest mismatches before rendering files or sending checks.

Existing 1.2.x rooms retain legacy canonical behavior. Rooms generated with
the invalid unpublished `four_of_six_v1` beta contract are not upgraded in
place and must be regenerated.

## Save and check reconciliation

Supported and enhanced campaign modes continue to read completed native slot
indices and translate them through the authoritative room layout. Neither mode
writes fake `beaten_levels` entries or page completions.

The active-save parser must be corrected independently before any future
feature writes Word Factori save data. Multiple serialized slots can carry the
same active-looking flag, and the live experiments proved that selecting a slot
by that flag alone is unsafe. This design does not require save writes.

Completion submission, received-item reconciliation, reconnect behavior, and
victory remain idempotent. A native index outside the validated layout fails
closed.

## Enhanced patch architecture

Development uses UndertaleModTool only against an isolated copy. Release users
must not install the development tool.

The release contains only integration-authored patch metadata and a compact
binary delta or equivalent patch program. Installation follows this sequence:

1. Locate the player's installed Word Factori `data.win`.
2. Compute SHA-256 and require an explicitly supported original hash.
3. Refuse to patch a running game.
4. Create a byte-identical backup beside the original with a specific,
   integration-owned name.
5. Apply the patch to a staged file.
6. Verify the complete patched-file hash.
7. Atomically replace the original only after verification.
8. Record the original hash, patched hash, patch version, and backup path in an
   integration-owned manifest.

Uninstall restores only a backup whose hash matches the recorded original.
Steam verification remains an independent recovery route. An unknown,
partially patched, or manually changed file produces actionable instructions
and no mutation.

Enhanced machine refresh uses a small integration-owned JSON contract written
atomically by the client. The patched game reads it only while the AP mod is
selected and only when entering a factory. Invalid, missing, stale, or
wrong-room data falls back to the conservative limits already loaded from the
mod's `levels.json` and displays no false unlock. The contract includes a
schema version, room/layout identity, and machine permissions.

The patch must not connect to Archipelago directly. Networking and durable
reconciliation stay in the Python client.

## Failure handling

- Unknown game hash: install supported mode and explain that enhanced mode is
  unavailable for this build.
- Missing or corrupt enhanced state: keep the last valid machine limits and
  warn through the AP client.
- Patch/client/room mode mismatch: do not send checks or rewrite campaign data.
- Game update after patching: detect the new hash and require restore or a new
  supported patch; never guess offsets.
- Missing backup: do not attempt automatic binary restoration.
- Client unavailable: the patched game remains playable with its last valid
  AP machine state, while network actions wait for the client.

## Testing

### Supported campaign

- Assert the exact fixed tutorial order for both 30- and 40-level sets.
- Assert sequential rules inside page one.
- Assert page two requires all six tutorial locations.
- Assert every later page location shares the same four-of-six predecessor
  rule and has no sibling dependency.
- Assert different seeds vary later page membership and order.
- Assert stable AP IDs survive all permutations.
- Run the real Archipelago 0.6.7 generation matrix across both level sets,
  goals, layout options, and at least 200 deterministic shuffled seeds.
- Replay progression spheres with the corrected six-then-four model.

### Client and bridge

- Verify shuffled native completion mapping, duplicates, reconnects, invalid
  indices, room identity, victory, and legacy 1.2.x compatibility.
- Add fixtures reproducing multiple active-looking save slots and require safe,
  unambiguous binding.
- Ensure invalid unpublished beta rooms fail closed with regeneration guidance.

### Enhanced patch

- Test hash allowlisting, unknown-hash refusal, already-patched detection,
  staging failure, atomic replacement, backup verification, and restoration.
- Apply the patch to an isolated exact-hash copy and verify the expected
  patched hash.
- Reopen the patched copy with the GameMaker tooling as a structural smoke
  test; do not commit extracted proprietary output.
- Confirm enhanced JSON parsing fails closed on malformed, stale, and
  wrong-room contracts.

### Live acceptance

Supported mode must prove the fixed tutorial, randomized later page, all-six
later-page selection, four-completion page advance, deferred return, stable
check mapping, reconnect safety, and victory.

Enhanced mode must additionally prove independent first-page selection,
four-completion first-page advance, a received machine becoming available on
the next factory entry without restarting, vanilla behavior isolation,
uninstall restoration, and Steam-update refusal.

## Documentation and release boundary

The README and tutorial must distinguish supported and enhanced modes without
implying that enhanced mode is required. Installation remains one guided flow;
enhanced mode is an explicit opt-in with a clear backup and compatibility
notice.

Version 1.3.0 remains an experimental beta until both supported-mode and
enhanced-mode live rows pass. Publishing, tagging, pushing, or replacing the
public release is outside this implementation step and requires a separate user
request.
