# Word Factori Archipelago 1.4.1 — Linux Tester Prerelease

One player package now includes **native Linux setup for playing Word Factori through Steam Proton**, alongside the existing Windows installer.

This is an **experimental tester prerelease**, not a stable release. Automated Windows and Ubuntu checks pass; a real Linux/Proton playthrough and a full connected playthrough of the current progression remain pending.

## Download

Download **word-factori-archipelago-1.4.1.zip** below for either platform, then extract it completely. Do not use GitHub's automatic source-code archives.

You need your own supported Steam copy of Word Factori (build 12616577) and Archipelago 0.6.7. Setup verifies the exact game and applies the same reversible native delta used on Windows. The package does not contain the full game binary or write game saves.

## Linux quick start

1. Install native Archipelago 0.6.7 and Python 3.12 or newer.
2. Launch Word Factori through Steam Proton once, then close the game and Archipelago.
3. Open a terminal in the extracted ZIP folder and run:

   ```bash
   bash "Install Word Factori Archipelago.sh"
   ```

4. Choose your installation if prompted, enter the existing native Archipelago `custom_worlds` directory, and confirm the destinations.
5. Restart Archipelago, launch Word Factori Client, and connect. Start the game through Steam, select **word factori archipelago**, and choose an empty mod save for a new room.

Use the regular native client for items and chat. **The in-game AP Mail overlay remains Windows-only.** No Wine-based installer, Windows Archipelago installation, or sudo is needed.

The [Linux guide](https://github.com/Akamarus/word-factori-archipelago/blob/v1.4.1/docs/linux-proton.md) includes manual paths, verify, restore, uninstall, and recovery commands. Installation choices remain local; no personal setup details need to be posted publicly.

## Windows and existing players

Windows installation is unchanged: close the game and Archipelago and run **Install Word Factori Archipelago.cmd** from the new ZIP.

The 1.4.0 campaign contract is unchanged. An existing matching 1.4.0 room can retain its bound save when updating; do not reset it merely for this update. Pre-1.4.0 rooms remain unsupported.

There is still one integration: curated 30- or 40-level campaigns, shuffled six-level pages, four completions to advance, machine-only progression, and I available in every level. Received machines apply after returning to Levels and entering a factory; an already-open factory is not rebuilt.

## What to test

On real Linux/Proton, please try install, connection, a completed check, a received machine after factory entry, reconnect, victory, and restore/uninstall with the game closed. Confirm saves and backups remain. A pass/fail and short error description are enough initially; please do not post private paths or full logs publicly.

Automated coverage includes Linux discovery, path validation, recoverable installer transactions, both bundled campaigns, client reconciliation, and launching the shell installer from the extracted player ZIP. This does not establish live Proton compatibility.
