# Linux setup with Steam Proton (unreleased, experimental)

These instructions apply to the development package containing
**Install Word Factori Archipelago.sh**, not the already-published v1.4.0 ZIP.
Linux support has automated filesystem/client tests but has **not been validated
in a real Linux/Proton playthrough**. Do not describe it as stable support yet.

There is one campaign and one player package for both platforms. Linux runs the
regular native Archipelago client while Steam runs the Windows game through Proton.
The in-game AP Mail overlay is Windows-only; items and chat remain available in
the regular client. No Wine-based installer or Windows Archipelago installation
is needed. This feature does not change the existing 1.4.0 campaign contract.

## Before setup

- Install native Archipelago 0.6.7 and Python 3.12 or newer using your normal
  distribution instructions. Setup does not install packages or ask for sudo.
- Own the supported Steam Word Factori build 12616577. Setup verifies the exact
  original game and bundled patch hashes; unknown binaries are refused.
- Launch Word Factori through Steam Proton once, then close it and Archipelago.
  This creates the game's Proton prefix and AppData folders. Setup never creates
  a prefix or chooses an account by guessing.
- Extract the complete development player ZIP. Keep all files together.

## Install or update

Open a terminal in the extracted package and run:

```bash
bash "Install Word Factori Archipelago.sh"
```

Setup searches the usual native and Flatpak Steam locations and their library
metadata. If several installations/accounts are found, choose one locally. Enter
the existing **native Archipelago custom_worlds directory** when asked. Check the
displayed destinations and confirm. No paths, logs, or account names are uploaded.

Setup validates and backs up the original game, installs the APWorld and JSON mod,
applies the same reversible native patch used on Windows, and saves the selected
paths in a local configuration file. Run the same command to update.

Restart Archipelago, launch **Word Factori Client**, and connect to your matching
room. Start Word Factori through Steam, select **word factori archipelago**, and
use a fresh empty mod save for a new room. Do not reset an existing room's bound
save just because its host OS changes. Existing room identity and save binding
checks still apply; older pre-1.4.0 rooms remain unsupported.

Play normally. Completed levels send checks; received machines become available
after returning to Levels and entering a factory. The already-open factory is
not rebuilt. Use the regular client for items, chat, hints, and connection status.

## If automatic discovery cannot find the installation

All paths below are examples to replace locally, not paths to post publicly:

```bash
bash "Install Word Factori Archipelago.sh" install \
  --game-data "/path/to/steamapps/common/word factori/data.win" \
  --prefix "/path/to/steamapps/compatdata/2072840/pfx" \
  --factori-root "/path/to/steamapps/compatdata/2072840/pfx/drive_c/users/steamuser/AppData/Local/factori" \
  --ap-worlds "/path/to/Archipelago/custom_worlds"
```

Supply all three game/prefix/factori options together. Use the actual Proton user
directory, which may not be `steamuser`. Paths must be absolute and writable.
Do not run as root to bypass a refusal. Symlinked installation descendants,
ambiguous accounts, unknown game hashes, and uncertain process inspection are
refused. Standard Steam root aliases are resolved during discovery. Nonstandard
setups may require an explicit canonical path.

The default configuration is `$XDG_CONFIG_HOME/word-factori-archipelago/installation.json`
when XDG_CONFIG_HOME is absolute, otherwise
`~/.config/word-factori-archipelago/installation.json`.
Advanced users may pass `--config /absolute/installation.json` to setup and
`--wf-config /absolute/installation.json` to the Word Factori client command line.
Use the default for normal launcher use. `--yes` skips confirmation but never
chooses among ambiguous installations; supply `--ap-worlds` for noninteractive use.

## Verify, restore, uninstall, or recover

These commands reuse the saved selection and still ask for the native
`custom_worlds` directory. Add `--ap-worlds "/your/Archipelago/custom_worlds"`
to avoid that prompt. Add your `--config` override if you used one during setup.

```bash
bash "Install Word Factori Archipelago.sh" verify
bash "Install Word Factori Archipelago.sh" restore
bash "Install Word Factori Archipelago.sh" uninstall
bash "Install Word Factori Archipelago.sh" recover
```

- **verify** is read-only. It checks the selected installation and readiness,
  independently of a connected room's campaign identity.
- **restore** restores the verified original game. Saves, backups, and the
  ownership receipt remain, allowing a later uninstall without repatching.
  The client deliberately refuses the restored, unpatched game until reinstalled.
- **uninstall** restores the original before removing the paired integration
  files, APWorld, and matching configuration. It preserves game saves, original
  and historical backups, and unowned runtime files.
- **recover** rolls back an interrupted setup using its validated transaction
  journal. Close the game first. If files changed externally, recovery refuses
  rather than overwriting them. Keep the journal and backups for private help.

Close the game before any change. Setup never kills it. Transactions are
recoverable but are not a single atomic operation across multiple filesystems.
Do not manually delete the original backup or transaction history to bypass errors.

## Private acceptance checklist

Before calling Linux support verified, run on real Linux/Proton: install and
verify; select the mod and empty save; complete a check; receive a machine and
see it after factory entry; reconnect without duplicate checks/items; reach the
configured goal; close the game and test restore then uninstall. Confirm saves
and backups remain. A simple pass/fail and error category is enough initially;
no public account paths, identifiers, or complete logs are required.
