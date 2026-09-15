# Word Factori Experimental Multiworld Setup

Version **[1.4.2 is a tester prerelease](https://github.com/Akamarus/word-factori-archipelago/releases/tag/v1.4.2)** with a full connected playthrough still pending. It uses one integration: enhanced, shuffled, machine-only progression. There is no integration-mode or fixed-layout selector. New rooms need a **fresh empty mod save**. The 1.4.0 campaign contract is unchanged, so updating a matching 1.4.0 room does not require resetting its bound save. Pre-1.4.0 rooms remain unsupported.

This checkout is **UNRELEASED 1.5.0 development**. Optional Recipe Journal checks, Type-a-Word orders, and Universal Tracker room reconstruction are not part of the published 1.4.2 package linked here. Enabled orders require a newly generated room, the matching development APWorld/client and native patch, and a fresh empty bound save. Connected game/client, native disk restart, live Universal Tracker, and Linux/Proton acceptance remain pending.

## Optional Type-a-Word orders (UNRELEASED)

```yaml
Word Factori:
  type_a_word_checks: true
  type_a_word_count: 3
  type_a_word_words: [JACK, FACTORY, PUZZLE, ISLAND]
```

Manufacture the selected targets in the native free-word factory and use `/wf_words` to inspect their status. Orders add checks and filler, not new machine items. They never count toward Campaign Count or Final Factory victory and never open page arrows. I is a starting source. Logic combines machine-family routes for the target's letters; it makes no machine-quantity guarantee.

Defaults: checks off, count 5, empty list. Count must be 1–20, with at most 200 list entries of 2–12 ASCII letters. Entries are trimmed, uppercased, deduplicated and sorted before seed-based selection; enough unique words must remain. Disabled orders create no locations and need no list. Compatible older rooms lacking order fields are disabled. Local YAML edits cannot change an existing room's orders, including in Universal Tracker: reconstruction uses authoritative room data.

The development ZIP uses the same Windows and Linux entry points below. Its `enhanced_v2` receipt requires `free_word_machine_enforcement_v1` and the exact patched hash. A recognized legacy installation upgrades through its verified original backup; missing or damaged required backups and unknown builds refuse without replacing the game. Close the game and Archipelago before upgrading. Restart Archipelago after installation. In play, return to Levels and re-enter a factory to receive new machine access without restarting the game.

Native custom-building production and previews are conservatively blocked in the AP mod. Saved layouts are retained; ordinary saved factories resume once their machine families unlock. Arbitrary Workshop import remains unsupported.

## Install on Windows

The same player ZIP supports Windows and experimental Linux/Proton setup.
Linux instructions follow the Windows section below.

1. Download and extract **[word-factori-archipelago-1.4.2.zip](https://github.com/Akamarus/word-factori-archipelago/releases/download/v1.4.2/word-factori-archipelago-1.4.2.zip)**, the single player package. Do not use GitHub's automatic source-code archives.
2. Close Word Factori and Archipelago.
3. Double-click the root **Install Word Factori Archipelago.cmd**. It installs the APWorld and mod, verifies the original game, preserves a backup, and applies the required native delta patch.
4. If prompted, select `data.win` from your Word Factori installation (Steam → Manage → Browse local files).
5. Restart Archipelago. Generate your new room, launch **Word Factori Client**, and connect before starting checks.
6. Start Word Factori, select **word factori archipelago**, and choose an empty save slot.

The required game is Steam build **12616577** with the exact original `data.win` accepted by the installer. Unsupported builds, other binary modifications, a running game, and damaged patch data are rejected. The original is preserved as `data.wf-ap-original.win` beside the game. The package contains a delta requiring your own installed game, not a full game binary.

For an update, close the game and Archipelago and double-click the same installer again; it keeps the previous integration files as backups. Advanced users can run `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force`. Use `-Uninstall` to restore the original game and remove the installed APWorld and mod, keeping saves and backups. To restore only the game binary, run the root **Restore Original Game.cmd** with the game closed. It is **not an integration uninstaller**. The integration requires its patch, so run the main installer again before playing after restoration.

## Install on Linux with Steam Proton (experimental)

1. Install native **Archipelago 0.6.7** and **Python 3.12 or newer**. Launch the supported Word Factori build through Steam Proton once, then close the game and Archipelago.
2. Extract the same player ZIP linked above and open a terminal in its folder.
3. Run `bash "Install Word Factori Archipelago.sh"`.
4. Choose the Steam/Proton installation if prompted, enter your existing native Archipelago user-world directory (`worlds` or `custom_worlds`), and confirm the displayed real destinations (directory shortcuts are resolved). Choices remain local.
5. Restart native Archipelago, launch Word Factori Client, and connect. Start the game through Steam and select the AP mod. Use a fresh empty mod save for a new room; preserve the bound save for an existing matching 1.4.0 room.

Use the regular native client for items, chat, hints, and connection status. The in-game overlay is Windows-only. Do not run the Windows installer through Wine or use sudo. To update, close the game and Archipelago and rerun the Linux command.

See the bundled `docs/linux-proton.md` or [full Linux guide](https://github.com/Akamarus/word-factori-archipelago/blob/v1.4.2/docs/linux-proton.md) for manual paths, verify, restore, uninstall, and recovery. Automated Ubuntu tests pass, but a **real Linux/Proton playthrough remains unverified**.

## Generate and play

Copy an example YAML to Archipelago's `Players` folder and change the player name. Choose `custom_level_set: core_campaign` for 30 levels or `discovery_labs` for 40. Choose Campaign Count or Final Factory as your goal. No World Access items are generated, and I stays available in every level. Machine ownership, recipe requirements, lab restrictions, and page progress determine what you can solve.

In the matching development version, enable the optional global journal locations under `Word Factori:`:

```yaml
Word Factori:
  recipe_checks: true
```

Use `false` to disable the extra checks. New rooms generated by the development APWorld default to enabled; a room whose slot data lacks the field is treated as disabled. Enabled seeds have 187 additional working letter-recipe locations (119 hidden alternatives): 217 total with Core Campaign or 227 with Discovery Labs. Disabled seeds retain 30 or 40 factory locations.

All six levels on an unlocked page are independently selectable, including the shuffled first page. Complete any four on a full page to open the next one; return for the other two whenever you want. The world requests local-early Merger2 Access and Rotation Access. With your starting Bender, these make at least four first-page levels solvable. Later pages retain machine-profile diversity but may be Merger2-heavy; at most one later Core Campaign page can have four Rotation-dependent checks. Labs keep their declared routes, and challenges keep their quantity limits.

Connect from the in-game panel (Windows only), regular client, or an `archipelago://` link. Native save slots map to stable AP location IDs. After a machine arrives, **return to Levels and enter a factory**. Machines refresh on factory entry, without restarting the game, reloading the mod, or reselecting the save for each item. An already-open factory is not rebuilt. Stickers and ordinary reconnects do not require a reload. The initial connection to a new room still needs a fresh campaign load.

The client reads completed level indices but never writes Word Factori saves. It binds each room to one empty save slot and refuses checks if existing progress is present or the active slot changes. It also refuses checks and mod regeneration if the connected room and installed campaign identities differ.

## Checks and tracker expectations

- `Discover C — Bending Lab` and the other “Discover” locations mean **finish that named lab**. Producing the letter in another factory or discovering a journal recipe does not send that lab's check.
- Recipe Journal locations are independent of factory and Discovery Lab wins. Each machine-and-input route is a distinct check, including alternate and hidden routes. They do not count toward page thresholds or victory, which continue to count factory completions only. Source I, symbol outputs, and the two unusable two-input Merger3 entries (`I N -> M` and `I Z1 -> M`) are excluded.
- Recipe identity normalizes and sorts inputs as native Letter code does. The journal is strictly bound to the room's fresh save and reporting is idempotent. Native isolated evidence shows a 60-step save-flush alarm, so newly discovered recipes may take time to reach the client rather than updating instantly.
- Universal Tracker's **in logic** means solvable after the required earlier puzzles, not necessarily unlocked on the game's current page. Four solvable preceding-page checks satisfy AP logic; four actual in-game completions open the next-page arrow. Visible factories may still require missing machines.
- This source checkout includes a tracker reconstruction fix that uses the room's saved layout and goal. It is not in the published 1.4.2 ZIP linked above; a connected tracker playthrough remains pending before publication. The tracker must load the fixed Word Factori APWorld to benefit.
- Manual check reports and `/send_location` affect the AP server, not the game save. They may count toward AP victory but do not unlock native pages. Use them for testing/recovery; complete four factories on the page in-game to advance normally.

On Windows, received items appear as blue popups on the left side of Word Factori. Click **AP MAIL** or press **F8** for the integrated **Items** and **Chat** panel. It supports connection, disconnect, connection status, chat, hints, commands, and masked password entry. Enter sends text, Shift+Enter inserts a line, and Escape closes the panel and returns focus to the game. The display works in windowed and borderless modes; use the regular Word Factori Client in exclusive fullscreen. If it does not appear, use `/wf_overlay status` and `/wf_overlay restart`. Item delivery and check reporting continue if the optional overlay renderer stops.

Only the bundled digest-verified `core_campaign` and `discovery_labs` manifests are selectable; arbitrary Workshop packs are not imported. An in-game missing-machine notice remains planned. Automated and isolated native-engine checks do not replace the pending connected in-game playthrough of this candidate. Recipe journal hooks pass isolated native evidence, but full live recipe-enabled game/client/Universal Tracker validation and Linux acceptance remain pending.
