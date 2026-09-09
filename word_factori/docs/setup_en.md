# Word Factori Experimental Multiworld Setup

Version **[1.4.0 is a tester prerelease](https://github.com/Akamarus/word-factori-archipelago/releases/tag/v1.4.0)** with a full connected playthrough still pending. It uses one integration: enhanced, shuffled, machine-only progression. There is no integration-mode or fixed-layout selector. Generate a **new Archipelago room** with this APWorld and client and use a **fresh empty mod save**; old rooms are unsupported and cannot be converted by updating.

## Install

1. Download and extract **[word-factori-archipelago-1.4.0.zip](https://github.com/Akamarus/word-factori-archipelago/releases/download/v1.4.0/word-factori-archipelago-1.4.0.zip)**, the single player package. Do not use GitHub's automatic source-code archives.
2. Close Word Factori and Archipelago.
3. Double-click the root **Install Word Factori Archipelago.cmd**. It installs the APWorld and mod, verifies the original game, preserves a backup, and applies the required native delta patch.
4. If prompted, select `data.win` from your Word Factori installation (Steam → Manage → Browse local files).
5. Restart Archipelago. Generate your new room, launch **Word Factori Client**, and connect before starting checks.
6. Start Word Factori, select **word factori archipelago**, and choose an empty save slot.

The required game is Steam build **12616577** with the exact original `data.win` accepted by the installer. Unsupported builds, other binary modifications, a running game, and damaged patch data are rejected. The original is preserved as `data.wf-ap-original.win` beside the game. The package contains a delta requiring your own installed game, not a full game binary.

For an update, close the game and Archipelago and double-click the same installer again; it keeps the previous integration files as backups. Advanced users can run `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force`. Use `-Uninstall` to restore the original game and remove the installed APWorld and mod, keeping saves and backups. To restore only the game binary, run the root **Restore Original Game.cmd** with the game closed. It is **not an integration uninstaller**. The integration requires its patch, so run the main installer again before playing after restoration.

## Generate and play

Copy an example YAML to Archipelago's `Players` folder and change the player name. Choose `custom_level_set: core_campaign` for 30 levels or `discovery_labs` for 40. Choose Campaign Count or Final Factory as your goal. No World Access items are generated, and I stays available in every level. Machine ownership, recipe requirements, lab restrictions, and page progress determine what you can solve.

All six levels on an unlocked page are independently selectable, including the shuffled first page. Complete any four on a full page to open the next one; return for the other two whenever you want. The world requests local-early Merger2 Access and Rotation Access. With your starting Bender, these make at least four first-page levels solvable. Later pages retain machine-profile diversity but may be Merger2-heavy; at most one later Core Campaign page can have four Rotation-dependent checks. Labs keep their declared routes, and challenges keep their quantity limits.

Connect from the in-game panel, regular client, or an `archipelago://` link. Native save slots map to stable AP location IDs. After a machine arrives, **return to Levels and enter a factory**. Machines refresh on factory entry, without restarting the game, reloading the mod, or reselecting the save for each item. An already-open factory is not rebuilt. Stickers and ordinary reconnects do not require a reload. The initial connection to a new room still needs a fresh campaign load.

The client reads completed level indices but never writes Word Factori saves. It binds each room to one empty save slot and refuses checks if existing progress is present or the active slot changes. It also refuses checks and mod regeneration if the connected room and installed campaign identities differ.

Received items appear as blue popups on the left side of Word Factori. Click **AP MAIL** or press **F8** for the integrated **Items** and **Chat** panel. It supports connection, disconnect, connection status, chat, hints, commands, and masked password entry. Enter sends text, Shift+Enter inserts a line, and Escape closes the panel and returns focus to the game. The display works in windowed and borderless modes; use the regular Word Factori Client in exclusive fullscreen. If it does not appear, use `/wf_overlay status` and `/wf_overlay restart`. Item delivery and check reporting continue if the optional overlay renderer stops.

Only the bundled digest-verified `core_campaign` and `discovery_labs` manifests are selectable; arbitrary Workshop packs are not imported. An in-game missing-machine notice remains planned. Automated and isolated native-engine checks do not replace the pending connected in-game playthrough of this candidate.
