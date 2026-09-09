# Native integration and playtest details

Version **[1.4.0 is a tester prerelease](https://github.com/Akamarus/word-factori-archipelago/releases/tag/v1.4.0)**, not a stable release. The integration always uses enhanced, shuffled, machine-only progression and requires the reversible native patch for the exact verified Steam Word Factori build 12616577. There is one player package and one installation route. This document records technical behavior and acceptance work for that integration.

## Runtime behavior

- First-page membership and positions change with the seed: I and C, two other early-solvable starter levels, and two later targets to revisit.
- All six buttons on an unlocked page are selectable. Some puzzles may need items you do not have yet. Complete any four to open the next page, including on page one.
- The two local-early machine items are Merger2 and Rotation. Together with your starting Bender, these make at least four first-page levels solvable.
- There are no World Access items. I stays available in every level; machine ownership, recipe requirements, lab restrictions, and page progress determine what is solvable.
- Received machines apply when you **return to Levels and enter a factory**. You do not need to restart the game, reload the mod, or reselect the save for each item. An already-open factory is not rebuilt.
- Check IDs, challenge limits, Discovery Lab route restrictions, and victory rules remain tied to the same targets even when their positions change.

This candidate uses the existing compiled native delta. The unified installation and progression contract do not add a new native hook or refresh machinery during an open factory.

## Install and start a playtest

1. Extract **word-factori-archipelago-1.4.0.zip** and close Word Factori and Archipelago.
2. Run the root **Install Word Factori Archipelago.cmd**. It installs the matching APWorld and mod and applies the required native delta patch after verifying and backing up the original game data.
3. If prompted, select `data.win` from the Word Factori installation (Steam → Manage → Browse local files).
4. Generate a **new room** using either bundled example YAML. There are no integration-mode or campaign-layout selectors. Old rooms are unsupported by this candidate, including earlier development contracts.
5. Start the updated Word Factori client and connect first so it prepares the shuffled campaign. Then start the game, select the AP mod, and choose a **fresh empty mod save**.

The first load of a new room needs a fresh campaign load. After that, items refresh on factory entry. Keep the AP client connected while playing. During acceptance, confirm I and C are both selectable regardless of their button positions, verify four completions open page two, and check a newly received machine after returning to Levels and entering another factory.

Only the exact verified original game is accepted. Unknown builds, other binary modifications, a running game, or a damaged patch are refused. The installer keeps `data.wf-ap-original.win` beside the game and never edits game saves. No original game binary, source, recipes, fonts, or music are in the package; the delta requires your own installed game.

## Restore or update

Close the game and run the root **Restore Original Game.cmd**, selecting the same `data.win` if prompted. The verified original is restored; saves and backup remain. This restores the game binary and **does not uninstall the integration**. The integration cannot be used without its required patch; run the main installer again before playing after restoration.

For integration updates, close the game and Archipelago and double-click the same main installer again as described in the [README](../README.md#simple-installation). Previous integration files are kept as backups. Steam verification can replace patched files; the client detects a missing or mismatched patch and pauses integration use. Updating does not convert old rooms or saves.

## Evidence and remaining acceptance

- Automated Python checks cover room logic, first-page variation, duplicate delivery, reconnects, runtime publication, and installed-game verification. Results must correspond to the candidate being evaluated.
- The previous tiered build passed 40 real AP 0.6.7 generations. Those results are historical evidence and do not establish generation or live acceptance of this machine-only candidate.
- Isolated native-engine tests execute the real button availability method, page threshold function, and factory module-count hook. They check all six first-page buttons, runtime refresh, wrong-room/stale data rejection, caps, and quiet handling of missing/malformed files.
- A **full visual playthrough with a live AP server and the normal game screens remains pending** and is a stable-release gate. The isolated harness substitutes startup and unrelated UI dependencies and uses a separate save directory.

If something fails, close the game and keep the client log. Do not delete your saves. Publication for testing does not establish completed live acceptance or stable-release readiness.
