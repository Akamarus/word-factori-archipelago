# Word Factori Archipelago

An experimental but playable [Archipelago](https://archipelago.gg/) integration for **Word Factori**. It adds a curated 40-level campaign, turns completed levels into Archipelago checks, and unlocks factory machinery as items arrive from the multiworld.

This project uses Word Factori's supported JSON mod format. It does **not** patch `data.win`, redistribute encoded game recipes, or write to Word Factori save files.

## What the randomizer does

The integration separates **what you build** from **what Archipelago gives you**:

1. Word Factori presents a fixed, curated sequence of word factories.
2. Completing a level reports that level as an Archipelago location check.
3. Archipelago sends the item placed at that location to its recipient.
4. Received Word Factori items unlock machines or later campaign tiers.
5. The client rewrites only this mod's `levels.json`, using zero machine/input limits for things you have not received.

Letters are always manufactured inside Word Factori. Archipelago never sends individual letters, puzzle layouts, or unverified save values.

## Requirements

- Word Factori on Steam
- Archipelago **0.6.7**
- Windows

The currently tested Word Factori depot is Steam build **12616577**.

## Simple installation

1. Download `word-factori-archipelago-hybrid-1.1.0.zip` from the [latest release](https://github.com/Akamarus/word-factori-archipelago/releases/latest).
2. Extract the ZIP to a normal folder.
3. Close Word Factori and Archipelago.
4. Double-click **Install Word Factori Archipelago.cmd**.
5. Restart Archipelago and Word Factori.
6. In Word Factori, select the **word factori archipelago** mod and use an **empty save slot**.

For an update, run the installer with `-Force`:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force
```

To remove only the files owned by this integration, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall
```

The installer replaces only these integration-owned paths:

- `%ProgramData%\Archipelago\custom_worlds\word_factori.apworld`
- `%LOCALAPPDATA%\factori\mods\word factori archipelago`

## Starting a randomized game

1. Copy one of the example player files into your Archipelago `Players` folder:
   - `tests/players/WordFactori.yaml` for the normal Campaign Count goal.
   - `tests/players/WordFactoriTarget.yaml` for the Final Factory goal.
2. Change the player `name` and any Word Factori options you want.
3. Generate and host the room normally with Archipelago.
4. Launch **Word Factori Client** from the Archipelago Launcher and connect it to the room.
5. Start Word Factori, select the Archipelago mod, and enter a new empty mod save slot.
6. Complete available levels. When an unlock arrives, return to save select and reload the mod slot, or restart Word Factori.

Connect the Archipelago client **before** completing checks. An existing progressed slot is deliberately rejected until it has already been bound to that room.

## Checks and locations

There are 40 stable locations:

| Group | Count | What counts as a check |
|---|---:|---|
| Standard factories | 26 | Complete the target word |
| Challenge factories | 3 | Complete CAT, BOOK, or PHONE with curated machine limits |
| Final factory | 1 | Complete PITCHFORK |
| Discovery Labs | 10 | Produce C, V, M, W, U, J, X, E, H, or R using the lab's declared machine route |

The first 30 locations form the main campaign. Discovery Labs are optional post-campaign checks because Word Factori natively unlocks custom levels in order.

Location indices never shift when something is locked. A locked level stays in place with its input or unavailable machines set to zero, which keeps save indices and Archipelago location IDs stable.

## Items and unlocks

| Item | Effect |
|---|---|
| Bender Access | Available from the start; enables bending |
| Rotation Access | Enables clockwise and counterclockwise rotation |
| Reflection Access | Enables horizontal and vertical reflection |
| Merger2 Access | Enables the two-input merger |
| Merger3 Access | Enables the three-input merger |
| Merger4 Access | Enables the four-input merger |
| Progressive World Access | Five copies progressively enable later campaign tiers |
| Sticker items | Filler messages; they do not write to Word Factori's sticker save state |

Received packets are keyed by Archipelago receive-sequence number. Replayed packets do not grant extra copies, and a reconnect rebuilds the current unlock state from authoritative server data.

## Goals

Two goal modes are available:

- **Campaign Count**: complete a configurable number of the first 30 campaign levels. The default is 25; the supported range is 20–30.
- **Final Factory**: complete `PITCHFORK — Final Factory`.

Discovery Labs do not count toward Campaign Count.

## How the logic stays solvable

Word Factori recipes form a deterministic graph. The project reads the locally installed `recipes.data` only during development verification, then calculates which combinations of machine capabilities can produce every required letter. Only the resulting capability names are stored in this repository.

Archipelago reachability combines three rules:

1. The player must own at least one valid machine set for the target.
2. The required Progressive World Access tier must be available.
3. The previous Word Factori level must be logically reachable, matching the game's native sequential unlocking.

This lets Archipelago's fill algorithm place progression in valid spheres. For example, if V needs Merger2, Merger2 must be obtainable from an earlier reachable check rather than being hidden behind V.

Discovery Labs use stricter rules: only their declared route is permitted in the generated level. Challenge levels keep their curated quantity limits even after all relevant machine families are unlocked.

## Save safety

Word Factori stores custom-campaign progress separately from its base campaign. The client reads:

- `%LOCALAPPDATA%\factori\user_ref.json`
- `%LOCALAPPDATA%\factori\mods.json`
- the active account's `mods\word factori archipelago\save.json`

These files are read-only to the integration. The client writes only:

- the installed mod's `levels.json`; and
- an idempotency sidecar under `%LOCALAPPDATA%\factori\archipelago`.

Each Archipelago room binds to the active empty Word Factori slot using that slot's stable `random_id`. A slot with previous completions is not auto-bound, and switching slots pauses check submission. This prevents unrelated progress from becoming false checks.

The campaign also has an ID, version, and content digest. If the room and installed mod do not match, both automatic and manual reporting stop until the matching release is installed.

## Client commands

| Command | Purpose |
|---|---|
| `/wf_status` | Show mod selection, campaign compatibility, save binding, deliveries, and bridge status |
| `/wf_scan` | Explicitly scan the active save once when automatic mod-selection detection is unavailable |
| `/wf_complete 31` | Manually report location 31 by one-based number |
| `/wf_complete "Discover C — Bending Lab"` | Manually report a uniquely named location |
| `/wf_overlay status` | Show the item overlay's availability and state |
| `/wf_overlay show` | Open the item ledger |
| `/wf_overlay hide` | Close the item ledger |
| `/wf_overlay restart` | Restart the optional renderer if it stopped |

Manual reporting cannot bypass campaign-digest or save-slot safety checks.

## In-game item display

While Word Factori is focused, received Archipelago items appear as blue popups on the left side of the game. The small **AP MAIL** button shows unread deliveries; click it or press **F8** to open the item ledger. The ledger currently shows items only. Full chat, connection controls, and manual location reporting remain in the regular Word Factori Client until the full in-game client is complete.

The overlay is cosmetic and failure-isolated: if it cannot start, the regular client continues working and retains the complete item history. Windowed and borderless modes are supported. Exclusive fullscreen may hide the overlay; use borderless mode or the regular client in that case.

## Troubleshooting

### A machine item arrived but is not visible

Return to Word Factori's save selection and reselect the mod slot. If that does not reload the palette, restart Word Factori. The current game build does not expose a verified live-reload hook.

### A level is visible but cannot be completed

Run `/wf_status`. The target may require a machine or World Access item that has not arrived yet. This is an Archipelago progression gate, not a missing recipe.

### The client refuses to bind the save

Use a new empty save slot for that Archipelago room. The safety system intentionally rejects an unbound slot that already contains completions.

### The in-game item display is missing

Use `/wf_overlay status` in the Word Factori Client. Then try `/wf_overlay restart`. Keep Word Factori in windowed or borderless mode; exclusive fullscreen is not supported. Item delivery and check reporting continue in the regular client even when the display is unavailable.

### The next-page arrow is gray

That is Word Factori's native progression. Finish the current page's levels; the APWorld models the same sequence.

## Current limitations

- This is a hybrid prototype, not an upstream Archipelago release.
- Arbitrary Workshop packs are not imported into generated seeds.
- Discovery Labs are post-campaign because the game sequentially gates custom levels.
- Progressive machine quantities are deferred until a quantity-aware layout solver exists.
- Sticker items are AP filler rather than in-game sticker grants.
- There is no DeathLink, traps, or randomized factory layouts.
- The in-game display is item-only in this release; a complete in-game client is required before the experimental label is removed.
- A complete GUI-driven server/client playthrough remains a production acceptance task.

## Development and verification

Run the tests with Python 3.12 or newer:

```powershell
python -m unittest discover -s tests -v
```

Build the APWorld and release ZIP:

```powershell
python tools\build_release.py
```

Verify archive parity, JSON indices, installed recipe derivation, and proprietary-data exclusions:

```powershell
python tools\verify_release.py
```

The test suite covers deterministic recipe reachability, progression requirements, goals, duplicate deliveries and checks, reconnect reconciliation, campaign identity, custom-save discovery, save-slot binding, and release hygiene.

## License and attribution

Code in this repository is available under the [MIT License](LICENSE).

Word Factori is created by Star Garden Games. Archipelago is maintained by the Archipelago community. This is an independent fan integration and is not affiliated with or endorsed by either project.
