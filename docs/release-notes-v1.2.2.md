# Word Factori Archipelago 1.2.2 — Reload Reconciliation Fix

This patch makes item delivery less disruptive. The client now reloads the generated campaign only when received progression actually changes what Word Factori should expose.

## Player-facing changes

- Sticker deliveries no longer rewrite `levels.json` or request a Word Factori reload.
- Reconnecting to the same room preserves a semantically matching campaign without requesting a reload.
- Duplicate item delivery remains idempotent and does not create additional reload work.
- Machine items and Progressive World Access still request a reload when they genuinely change the installed campaign.
- A missing or damaged generated campaign is repaired on connection and clearly marked as requiring a reload.

## Install or update

1. Download `word-factori-archipelago-1.2.2.zip`.
2. Extract it to a normal folder.
3. Close Word Factori and Archipelago.
4. Double-click **Install Word Factori Archipelago.cmd**.

Existing users can instead run `install.ps1` with `-Force`. Existing 1.2.1 rooms are not upgraded in place; generate a new room with the matching 1.2.2 APWorld.

This remains an independent experimental community integration. It is not an official Word Factori or upstream Archipelago release.
