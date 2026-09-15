# Optional Recipe Journal checks (development)

Optional Recipe Journal checks are implemented in the current development source. They are **not included in the published 1.4.2 player package**. A recipe-enabled room requires the matching development APWorld and client, a newly generated seed, and a fresh empty Word Factori mod save bound to that room. Nothing in this workflow changes the user's current room, installed APWorld, game, or save.

## Enable or disable

Place the option under the `Word Factori:` key in the player YAML:

```yaml
Word Factori:
  recipe_checks: true
```

`true` adds Recipe Journal locations. `false` disables the extra checks. The development APWorld defaults newly generated rooms to enabled; missing slot data means disabled so older rooms retain their original contract.

Changing a YAML file does not retrofit an existing seed. Generate a new seed with the desired value and use a fresh empty save with the matching development client and APWorld.

## What is a recipe check?

A factory check is earned by completing its target level. The existing “Discover” checks are also level wins: `Discover C — Bending Lab`, for example, means completing that named lab.

A Recipe Journal check is different. It is earned when the bound save records one exact machine-and-input route in the global journal. Alternate ways to produce the same letter are separate locations, and hidden alternatives count separately. Recipe Journal checks do not complete a factory, open a page, or count toward either victory goal. Page thresholds and Campaign Count continue to count factory completions only.

Enabled seeds add 187 working A-Z-producing recipes, 119 of them hidden alternatives:

| Level set | Factory checks | Recipe checks | Total |
|---|---:|---:|---:|
| `core_campaign` | 30 | 187 | 217 |
| `discovery_labs` | 40 | 187 | 227 |

With the option off, those totals remain 30 and 40.

## Location notation and identity

Recipe locations identify the output letter, machine, and normalized inputs. Inputs are normalized and sorted using the same identity rule as Word Factori's native Letter code. This makes journal matching insensitive to input ordering where the native game is insensitive, while preserving different machines and alternate routes as distinct locations.

Only working letter-output routes are included. The catalog excludes:

- source I, because it is available rather than produced by a recipe;
- symbol outputs; and
- the native Merger3 entries `I N -> M` and `I Z1 -> M`, which declare only two inputs and cannot be processed by a real Building/Letter Pipe.

The repository contains only mechanics-derived normalized identities and minimal machine capability requirements. It does not contain or distribute the proprietary `recipes.data` file or complete raw recipe records.

## Save and reporting behavior

Recipe scanning uses the same strict room-to-save binding as factory checks. The client accepts journal progress only from the fresh save bound to the connected room, pauses if the active slot changes or identity validation fails, and reports each location idempotently. Repeated scans and reconnects cannot award the same location twice.

Updates are not necessarily instant. Isolated native probing found that Word Factori flushes Recipe Journal state to the save on a 60-step alarm. The client can report a discovery only after that saved state becomes visible, so allow for save-flush latency.

## Verification status and limitations

An isolated native fixture verified journal recording and the 60-step flush behavior without modifying the live installation or save. Automated generation exercised 12 real Archipelago 0.6.7 cases covering `true`, `false`, and omitted values across both level sets and both goals. Exact location contracts, balanced fill, and replayed progression spheres passed. Separate unit tests exercise Universal Tracker reconstruction; the generation matrix does not establish a connected tracker playthrough. Generation time varies with the host and is recorded with the raw verification evidence rather than promised as a player-facing performance target.

This is development evidence, not a published release claim. A full live recipe-enabled Word Factori/client/Universal Tracker session and Linux acceptance have not been performed. Do not install or publish this development package as 1.4.2, and do not use it with an existing room or progressed save.
