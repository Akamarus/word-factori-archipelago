# Word Factori Archipelago 1.4.0 — Tester Prerelease

This is an experimental tester release, not a stable release. A full connected in-game playthrough of this version remains pending.

## Download and install

Download **word-factori-archipelago-1.4.0.zip** from this release's Assets, extract it, close Word Factori and Archipelago, and double-click **Install Word Factori Archipelago.cmd**. Use the same installer for updates. Do not use GitHub's automatic source-code archives.

Requires Windows, Archipelago **0.6.7**, and Word Factori Steam build **12616577**. The installer verifies your own exact game build, backs up the original, and applies the required reversible native delta patch. Unknown or conflicting game builds are refused. The package does not include a full game binary.

**Generate a new room with the included APWorld and use a fresh empty mod save. Old rooms are unsupported; updating cannot convert them. Keep your existing saves.** Connect the Word Factori Client before starting the new campaign.

## What's changed

- One integration and one installer: enhanced, shuffled, machine-only progression is now the only new-room mode.
- Seed-specific pages, including the first page. All six levels on an unlocked page are selectable; complete any four to advance and revisit the others later.
- No World Access items. Machine ownership, recipe requirements, and page progress control what you can solve.
- The basic I source stays available everywhere. Discovery Labs retain their machine-route restrictions, and challenge levels retain their quantity limits.
- Received machines refresh when you **return to Levels and enter a factory**. No game restart, mod reload, or save reselection is needed per item. An already-open factory is not rebuilt.
- Choose the 30-location Core Campaign or 40-location Discovery Labs set, with Campaign Count or Final Factory victory.
- Integrated AP Mail Items/Chat panel, blue item popups on the left, and the regular client as fallback.
- Transactional installation/update, original-game backup, and a separate **Restore Original Game.cmd**.

## Testing status and feedback

Automated coverage includes reachability, progression, duplicate items/checks, reconnects, victory, installer rollback/restoration, and package integrity. Automated and isolated native-engine checks are not a substitute for a full connected playthrough.

Please test first-page selection, four-completion page unlocks, newly received machines after factory entry, AP Mail clicks/tab switching, reconnects, and victory. Report the target level, received machines, steps to reproduce, and relevant client log; remove server passwords or other private information before sharing.

Use windowed or borderless mode; exclusive fullscreen is unsupported. In-game missing-machine notices are still planned. Password rooms, additional display scaling, ultrawide, and mixed-DPI/multi-monitor combinations need more testing.

See the [README](https://github.com/Akamarus/word-factori-archipelago#simple-installation) for installation, room setup, logic, and troubleshooting.
