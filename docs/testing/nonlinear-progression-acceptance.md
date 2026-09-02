# Nonlinear Progression Acceptance Matrix

This matrix separates repeatable automated evidence from live Word Factori acceptance. Automated success does not promote a live row. Every 1.3.0 live observation remains pending until the dedicated live pass records the environment, room, steps, and result.

| Behavior | Automated evidence | Live acceptance |
|---|---|---|
| Generate both 30-level `core_campaign` and 40-level `discovery_labs` shuffled layouts with the canonical Starter Workshop on page one | Unit coverage plus 200/200 real AP 0.6.7 solo generations passed on 2026-09-02 | Pending live test |
| Repeating a seed produces the same complete layout digest and order | Unit coverage plus real AP seed 13000 repeat / 13001 variation passed | Pending live test |
| Different seeds vary the shuffled page order | Verified by seed-variation tests | Pending live test |
| Three completed checks keep the next-page frontier closed; four open it | Verified by access-rule boundary tests | Pending live test |
| Either remaining page check can be deferred and revisited after the next page opens | Four-of-six reachability is verified automatically; revisit behavior requires the game | Pending live test |
| A native save-slot completion maps to the canonical stable Archipelago location ID | Verified by layout projection, client-core, manual-check, and shuffled lifecycle tests | Pending live test |
| Reconnect reconciliation does not duplicate a shuffled check or received item | Verified by shuffled lifecycle and bridge idempotency tests | Pending live test |
| Campaign Count and Final Factory goals use canonical identities after shuffling | Verified by world and client-core goal tests | Pending live test |
| The 1.3.0 client connects to a legacy 1.2.x room and retains canonical order | Verified by legacy room resolution and client lifecycle tests | Pending live test |
| A layout digest or installed identity mismatch blocks rewrites and check submission | Verified by validation, compatibility, and client lifecycle tests | Pending live test |

## Feasibility boundary

The first shuffled page contains exactly the six canonical Starter Workshop records. Their slot order is shuffled, while later page membership remains seed-specific. The APWorld requests one local-early `Merger2 Access` and one local-early `Rotation Access`. Merger2 is required because only Complete I and Complete C are reachable at bootstrap; Rotation is also local-early because a Merger2 plus Progressive World Access placement can otherwise leave only Complete V as the next unused reachable check.

Each full page retains at least three distinct unavoidable machine profiles. Reflection, Merger3, and Merger4 are unavoidable for at most three checks per full page. Rotation uses the same limit except that at most one later complete Core Campaign page may contain four Rotation-unavoidable checks; no page may exceed four. This narrow exception is necessary because fixing the canonical starter membership leaves 13 Rotation-unavoidable records for four later Core pages, whose capacity would otherwise be only 12. The four-of-six unlock rule and all canonical region tiers remain unchanged.

AP 0.6.7 spoiler `Playthrough` lines identify the advancement checks retained by spoiler pruning; they do not enumerate every reachable location. Automated acceptance therefore parses each sphere's progression items and replays them over the generated `level_order` using the production recipe requirements, Progressive World Access tiers, and four-of-six page frontier. Already-used playthrough checks are removed from each reconstructed choice set. A room must have at least one pre-goal replay state, and the required number of states with at least two reachable unused locations is `min(3, total pre-goal replay states)`. Evidence records the observed numerator, required denominator, total states, and per-state counts explicitly.

## Automated AP 0.6.7 record

On 2026-09-02, seeds 13000–13049 were generated with `C:\ProgramData\Archipelago\ArchipelagoGenerate.exe` as 200 independent one-player rooms: Core Campaign / Campaign Count, Core Campaign / Final Factory, Discovery Labs / Campaign Count, and Discovery Labs / Final Factory. The definitive audited-identity run from 15:16:46 through 15:35:38 EDT took 18 minutes 52 seconds. All 200 exited successfully, matched their requested level set, numeric goal, campaign count, level count and actual order length, layout algorithm, and implementation version, and passed proportional replay acceptance. Every evidence row stores those requested and generated values separately with `identity_validation: Pass`. Same-seed Discovery Count generation reproduced digest `b3cd5448ff934026163258f8a2087c88863ae3f8a414493e30413f82466210db`; seed 13001 changed it to `c5b48378ad56b76ed01c8f17f9e291d58421879d02745f69329c517e2fbe0d5d` while preserving all 40 stable keys and AP IDs.

## Live record

No 1.3.0 live acceptance is recorded yet. Do not replace `Pending live test` with a pass until the behavior has been observed in Word Factori and the evidence identifies the AP version, game build, generated room, display environment, exact steps, and outcome.

The prepared 40-level shuffled Campaign Count room is:

- AP: 0.6.7; seed: 13050; player: `WF_Live_Discovery_Count_13050`
- archive: `C:\Users\Jack\AppData\Local\Temp\word-factori-ap067-live-x8e71mum\output\AP_87260292545628931117.zip`
- YAML: `C:\Users\Jack\AppData\Local\Temp\word-factori-ap067-live-x8e71mum\players\player.yaml`
- layout digest: `d07d55295bd9bb46d44822872e8482f675a465d5bc167869b02f003ff3889dbe`
- page one, in native slot order: Complete A, Complete C, Complete L, Complete I, Complete O, Complete V

The controller-authorized final install was completed on 2026-09-02 without touching saves. The installed APWorld and the build that produced this room both have SHA-256 `8A1AC5102B841CEDE7575BEC432D253B4E79BFA847C58F7B261F12697E1A1F2E`.

The user must host the prepared archive, launch Word Factori Client, connect as `WF_Live_Discovery_Count_13050`, select the integration mod in Word Factori, and use a clean empty mod save. Record the six page-one targets; confirm the arrow is disabled after three completions and enabled after four; open page two with two unfinished checks; later complete one deferred check after its needed machine arrives; verify native slots report the canonical AP names; reconnect/restart and verify the mapping is unchanged with no duplicate check or item; and record one Campaign Count goal update. Do not mark any live row passed without those observations.

To extract the room identity again without launching the game, run:

```powershell
C:\Users\Jack\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools\verify_generation_matrix.py --inspect-archive 'C:\Users\Jack\AppData\Local\Temp\word-factori-ap067-live-x8e71mum\output\AP_87260292545628931117.zip'
```
