# Enhanced first-page playtest

This is a **local development build**, not a new public release. It includes an
optional, reversible patch for Steam Word Factori build 12616577. The normal
supported mode still works without modifying the game.

## What changes

- First-page membership and positions change with the seed: I and C, two
  other early-solvable starter levels, and two later targets to revisit.
- All six buttons on an unlocked page are selectable. Some puzzles may need
  items you do not have yet. Complete any four to open the next page.
- The first two local early machine items are Merger2 and Rotation. Together
  with your starting Bender, these make at least four first-page levels solvable.
- New 1.4.0 rooms have no World Access items. I stays available in every level;
  machine ownership, recipe requirements, lab restrictions, and page progress
  determine what is solvable. Old rooms keep their original tier locks.
- Received machines apply when you **return to Levels and
  enter a factory**. You do not need to restart the game, reload the mod, or
  reselect the save for each item. An already-open factory is not rebuilt.
- Check IDs, challenge limits, Discovery Lab route restrictions, and victory
  rules remain tied to the same targets even when their positions change.

## Install for testing

1. Close Word Factori and the Archipelago client. Extract the playtest ZIP.
2. Run **Install or Update Playtest.cmd** to install this build's APWorld and mod.
3. In the `enhanced` folder, run **Install Enhanced Patch.cmd**. Select
   `data.win` from your Word Factori installation (Steam → Manage → Browse local files).
4. Generate a **new** Archipelago room using `Enhanced Player.yaml`, or set
   `integration_mode: enhanced` and `campaign_layout: shuffled_pages` in your YAML.
5. Start the updated Word Factori client and connect to that room first. It
   prepares your shuffled campaign. Then start the game, select the AP mod,
   and choose an empty mod save. Do not reuse an old room's save.

The first load of a new room still needs a fresh campaign load. After that,
items refresh on factory entry. Keep the AP client connected while playing.
For the first playtest, confirm I and C are both selectable regardless of
their button positions; complete one and check the newly received machine
after returning to Levels and entering another factory.

Only the exact verified original game is accepted. Unknown builds, other
binary mods, a running game, or a damaged patch are refused. The installer
keeps `data.wf-ap-original.win` beside the game. It never edits game saves.
No original game binary, source, recipes, fonts, or music are in this package;
the small delta requires your own installed game.

## Restore or update

Close the game and run **Restore Original Game.cmd**, selecting the same
`data.win`. The verified original is restored; saves and backup remain.
Enhanced rooms need the patch, so use a new supported-mode room after restoring.
Restore before updating to a different enhanced build. Steam verification can
also replace patched files; the client detects this and pauses enhanced use.

## What is verified, and what is not

- Automated Python tests cover room logic, first-page variation, duplicate
  delivery, reconnects, runtime publication, and installed-game verification.
- The previous tiered build passed 40 real AP 0.6.7 generations. Machine-only
  generation is verified separately; do not treat old results as new-build evidence.
- Isolated native-engine tests execute the real button availability method,
  page threshold function, and factory module-count hook. They check all six
  first-page buttons, runtime refresh, wrong-room/stale data rejection, caps,
  and quiet handling of missing/malformed files.
- This is **not yet a full visual playthrough** with a live AP server and the
  normal game screens. That remains the release gate. The harness substitutes
  startup and unrelated UI dependencies and uses a separate save directory.

If something fails, close the game and keep the client log. Do not delete
your saves. This build is intentionally opt-in until playthrough acceptance.
