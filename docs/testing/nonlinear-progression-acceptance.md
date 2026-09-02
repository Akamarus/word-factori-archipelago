# Nonlinear Progression Acceptance Matrix

This matrix separates repeatable automated evidence from live Word Factori acceptance. Automated success does not promote a live row. Every 1.3.0 live observation remains pending until the dedicated live pass records the environment, room, steps, and result.

| Behavior | Automated evidence | Live acceptance |
|---|---|---|
| Generate both 30-level `core_campaign` and 40-level `discovery_labs` shuffled layouts | Verified by layout/world generation tests | Pending live test |
| Repeating a seed produces the same complete layout digest and order | Verified by deterministic layout and slot-data tests | Pending live test |
| Different seeds vary the shuffled page order | Verified by seed-variation tests | Pending live test |
| Three completed checks keep the next-page frontier closed; four open it | Verified by access-rule boundary tests | Pending live test |
| Either remaining page check can be deferred and revisited after the next page opens | Four-of-six reachability is verified automatically; revisit behavior requires the game | Pending live test |
| A native save-slot completion maps to the canonical stable Archipelago location ID | Verified by layout projection, client-core, manual-check, and shuffled lifecycle tests | Pending live test |
| Reconnect reconciliation does not duplicate a shuffled check or received item | Verified by shuffled lifecycle and bridge idempotency tests | Pending live test |
| Campaign Count and Final Factory goals use canonical identities after shuffling | Verified by world and client-core goal tests | Pending live test |
| The 1.3.0 client connects to a legacy 1.2.x room and retains canonical order | Verified by legacy room resolution and client lifecycle tests | Pending live test |
| A layout digest or installed identity mismatch blocks rewrites and check submission | Verified by validation, compatibility, and client lifecycle tests | Pending live test |

## Feasibility boundary

The first shuffled page guarantees at least four checks whose valid routes are not unavoidably dependent on Merger2 Access. Each full page retains at least three distinct unavoidable machine profiles and prevents Rotation, Reflection, Merger3, or Merger4 from being unavoidable for four checks. Later pages may nevertheless be Merger2-heavy. Archipelago fill, not a stronger per-page Merger2 cap, is responsible for ensuring the four-check frontier is reachable.

## Live record

No 1.3.0 live acceptance is recorded yet. Do not replace `Pending live test` with a pass until the behavior has been observed in Word Factori and the evidence identifies the AP version, game build, generated room, display environment, exact steps, and outcome.
