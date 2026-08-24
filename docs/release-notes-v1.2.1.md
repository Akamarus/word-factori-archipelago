# Word Factori Archipelago 1.2.1 — Experimental Public Beta

This patch release gives players a smaller, purpose-built download while preserving the 30-level Core Campaign, recommended 40-level Discovery Labs campaign, progression logic, save safeguards, and integrated Items/Chat client from 1.2.0.

## Install

1. Download `word-factori-archipelago-1.2.1.zip`.
2. Extract it to a normal folder.
3. Close Word Factori and Archipelago.
4. Double-click **Install Word Factori Archipelago.cmd**.

Existing users can run `install.ps1` with `-Force`. See the packaged README for generation, connection, update, uninstall, and troubleshooting instructions.

## Packaging changes

- The player ZIP now contains only the APWorld, supported JSON mod, installer, examples, player documentation, license, and README images.
- Loose repository source files, tests, tools, internal plans, testing records, caches, generated rooms, saves, credentials, proprietary game data, recipes, and fonts are excluded. Required integration code remains contained inside the APWorld.
- A Windows CI workflow and clean-checkout verification command now exercise the same build, test, and release-verification sequence.

This remains an independent experimental community integration. It is not an official Word Factori or upstream Archipelago release.
