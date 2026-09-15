# Type-a-Word orders — design for approval

Status: design only; no feature code or game patch changed. Progressive machine quantities are a separate, deferred feature.

## Player experience

Add optional, seed-selected word orders alongside the existing campaign and recipe journal checks. The player supplies a word list and how many entries the seed should select. All selected orders are available independently of campaign pages. Produce a selected word using received AP machinery to earn one check. Merely typing, opening, or saving an unfinished factory earns nothing.

Use native Type-a-Word rather than another paged campaign when possible. An order is a word-production goal, not a requirement to launch it through a particular menu: legitimate production of the same target in another factory can also satisfy it. If a target overlaps a campaign factory, completing it may award both checks, but only the campaign check advances its existing goal/page rules.

Proposed YAML:

```yaml
Word Factori:
  type_a_word_checks: true
  type_a_word_count: 3
  type_a_word_words:
    - JACK
    - FACTORY
    - PUZZLE
    - ISLAND
```

Defaults: checks off; count 5; word list empty. Enabling checks requires a supplied list containing at least the requested number of distinct valid words. Count range 1–20; at most 200 list entries; each word 2–12 ASCII letters. Trim surrounding whitespace, uppercase ASCII, remove duplicates, then sort before seed-based sampling. Reject embedded whitespace, punctuation, digits, non-ASCII characters and impossible words with actionable generation errors. Do not silently reduce the requested count or substitute different words. Disabled settings create no order locations and do not require a word list.

Orders add checks and filler, not new machine items. Existing factory names, IDs, page thresholds, recipe checks and victory goals stay unchanged. Type-a-Word checks do not count toward campaign victory or unlock page arrows.

The regular client lists selected targets, completion state, and missing-machine alternatives through `/wf_words`. The list is available on Windows and Linux. Universal Tracker uses the same room-selected targets and requirements. No new in-game overlay tab is required for this first version; use the existing chat/command panel on Windows and native Type-a-Word entry to play.

## Why the native route is preferred

1. Native Type-a-Word plus AP restrictions is the preferred approach: it preserves the existing game interface and provides an independent path through the seed.
2. Seed-generated custom factories are the fallback if native restrictions or completion detection cannot be verified. This would need a separate, always-accessible entry path; appending them behind campaign pages is not equivalent and is not approved as a silent fallback.
3. Unrestricted Type-a-Word with client-side reporting alone is rejected. It permits checks before the required machinery arrives and makes tracker logic misleading.

## Evidence currently available

Read-only inspection of locally extracted code for the verified native build found:

- `EnterInputBoxGame` calls `setLevel` with index -1 and native mode 3.
- `get_level_module_counts(-1)` returns an empty limit structure in the original game. The current AP helper explicitly ignores negative indices, and its acceptance fixture tests this behavior.
- `get_current_module_count` bypasses restrictions outside native mode 1. Supplying a limit structure alone is therefore insufficient for Type-a-Word.
- `beatLevel` records successful target words in the selected save slot's `words` mapping. Entries carry building, cycle and extra-letter scores. A free word with index -1 does not create a campaign `beaten_levels` entry.
- The same word journal is used by multiple modes. It cannot establish that a word was completed specifically through Type-a-Word, hence the word-production semantics above.

These are code-inspection findings, not a live Type-a-Word acceptance result. Exact serialized values, fresh defaults, duplicate behavior, input normalization and alternate launch paths must be exercised in an isolated native test before the production reader is enabled. Do not distribute the extracted native code or copy any user's save into the repository.

The unrestricted free-word path also matters to global recipe discoveries. New AP-native enforcement must cover that path even when Type-a-Word order checks are disabled; turning off orders must not turn on unrestricted recipe farming.

## World and logic

Use twenty reserved, static location identities (`Word Order 01` through `Word Order 20`) with a reviewed, collision-free numeric range. The seed's authoritative slot data maps each included order ID to its selected word. Do not create an unbounded global AP data package from arbitrary player text. Expose the target in the order's tracker region and client listing.

Bundle alphabet-production requirements derived from the verified native recipe graph with unusable machine-arity definitions excluded. Word access requires a valid route for every letter, including alternate routes. I is a starting source. With unlimited per-family machinery, repeated letters do not imply additional AP item copies. No quantity-aware claims are made.

Generate a separate order region without campaign-page prerequisites. Validate reachability from the starting I source rather than requiring a campaign completion. Reject targets that remain unreachable with all available machines. Cache the alphabet capability table; do not rerun recipe graph exploration separately for each word or every tracker query.

Include ordered target mapping, option state, alphabet-logic version/digest and recipe option state in the room contract. A new progression model must make older clients reject enabled order rooms explicitly. Missing order fields in older room contracts mean orders disabled. Universal Tracker reconstructs orders from authoritative room data, never the current local YAML. Preserve existing state identities for existing contracts unless a separately documented migration is required.

## Native integration and item refresh

Extend the existing verified-build patch and runtime snapshot rather than introducing an injector or another installer. Never change the installed game during development; use an isolated copy and fresh test save namespace.

In the AP mod, non-campaign word production must obey AP-owned machine families. Keep I available. Apply current inventory when entering a factory, as the campaign already does. Receipt of a machine does not require restarting the game; an already-open factory need not be rebuilt automatically.

The extension must address both native limit lookup and the mode-dependent restriction bypass. Validate room, layout, runtime revision and the new word contract before consuming external state. Missing, corrupt, stale or wrong-room state must never yield unrestricted machines: retain an appropriate validated snapshot for that same room or fail closed to safe starting limits. Do not apply AP rules to vanilla play or another mod.

Check other launch paths that write the same word/recipe journals: replaying a word, daily/shared words if reachable in the AP mod, and saved layouts or custom factories. A blueprint/import must not provide production with locked machines. Block an unsupported bypass without deleting the user's saved layout. If these paths cannot be constrained reliably, the native feasibility gate has failed.

Update patch receipts and native acknowledgment capabilities so a client requiring this enforcement refuses the older patch. A generic old enhanced acknowledgment is insufficient. Recipe-only sessions using the new client also require verified free-word enforcement before recipe reporting. Exact-build verification, original backup, Windows/Linux installer simplicity, quiet missing-file handling and rollback remain mandatory.

## Completion bridge and safety

Read the selected slot's native completed-word journal in the same snapshot as campaign and recipe progress. Match only selected normalized targets and validated successful entries. Do not infer completion from layout names, text entry, recipe availability or an unfinished saved factory.

Fresh enabled binding rejects pre-existing word completions as well as existing campaign/recipe progress. Once bound, offline discoveries can be reconciled after reconnect. Use the existing observed/pending/server-acknowledged path for idempotence. Wrong active slot, mismatched room contract or invalid native enforcement acknowledgment pauses reporting.

Unknown valid word entries are ignored for AP orders. Malformed selected completion data must not create guessed checks. Disabled orders add no word checks. Word IDs must never enter native page-slot conversion or factory-only victory calculations. `/send_location` is a server-side operation and must not write the game save or manufacture native completions.

## Verification gates

1. Native isolated probe: type/open is not completion; real success records a word without campaign credit; repeat wins are idempotent; fresh slot is empty; exact normalization and serialized score forms are observed. Stub only unrelated network/UI effects and label simulated versus genuine production evidence separately.
2. Native enforcement probe: missing machines cannot be used in free-word modes; new item applies on re-entry; stale/missing/wrong-room snapshots fail safely; vanilla remains unchanged; replay/import paths cannot bypass progression. Compile and reopen the patched test copy before accepting it.
3. Unit/integration tests: option boundaries, deduplication, deterministic selection, fixed identities, impossible inputs, alternate letter routes, contracts/digests, native snapshot validation, slot binding, duplicate checks, offline replay, server acknowledgments, and factory-only goals/pages.
4. Real AP generation: orders on/off crossed with recipes on/off, both campaign sets and both goals. Balanced fill, progression spheres and tracker reconstruction evidence must be reported separately from a connected tracker playthrough.
5. Package verification: original/patch hashes, patch receipt transitions, catalog inclusion, no proprietary source/full binaries/user saves, Windows and Linux installer tests and unchanged simple installation flow.
6. Connected acceptance before release: fresh seed with at least three selected words; locked machinery, item arrival/re-entry, real production, one check per word, restart/reconnect, tracker target and logic display. Linux/Proton acceptance remains separately identified.

If either native gate fails, stop before enabling this feature and report the evidence and revised fallback. Do not hide the failure behind client-only check filtering.

## Delivery boundary

This design authorizes neither a live installation update nor a public release. Implementation stays on a feature branch. A new word-enabled seed and matching updated client/APWorld/native patch are required for acceptance. Do not label new functionality as the already-published 1.4.2. Progressive machine quantities, new victory options, an overlay redesign and arbitrary Workshop import remain out of scope.
