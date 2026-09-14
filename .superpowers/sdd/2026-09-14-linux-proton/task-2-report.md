# Task 2 implementation report

Implemented `tools/install_linux.py`, `tools/linux_transaction.py`,
`tests/test_linux_installer.py`, and root `Install Word Factori Archipelago.sh`.
The existing COPY/literal decoder and exact compressed delta are reused unchanged.

## Public CLI and package dependencies

Run from the player package with:

```bash
bash "Install Word Factori Archipelago.sh" [install|verify|restore|uninstall|recover] \
  --game-data "/absolute/game/data.win" \
  --prefix "/absolute/steamapps/compatdata/2072840/pfx" \
  --factori-root "/absolute/steamapps/compatdata/2072840/pfx/drive_c/users/steamuser/AppData/Local/factori" \
  --ap-worlds "/absolute/native/Archipelago/custom_worlds" \
  --config "/absolute/config/installation.json" --yes
```

`install` is the default and also updates installations. Omit `--yes` for local
confirmation after preflight/destination display. Omit the three game paths to
load the configuration or discover validated Steam installations; multiple
candidates require local selection or all three explicit overrides. AP destination
is always explicitly supplied or locally prompted; it must be an existing
`custom_worlds` directory. No system install location is guessed. The default config
path uses Task 1's XDG/home policy. Native mutations require Linux and readable
process information. Read-only `verify` and `--help` are portable.

Task 4 must include the shell entry, `tools/install_linux.py`,
`tools/linux_transaction.py`, and `tools/enhanced_delta.py`, plus the existing
single `tools/enhanced.patch.gz`, APWorld and mod data. The installer loads
`word_factori/platform_paths.py` directly from the APWorld without running its
package initializer; an unpacked source-file fallback supports development only.
No Archipelago runtime imports, external packages, sudo, or package installation.

## Shared receipt and configuration

Configuration uses Task 1's exact schema-1 fields: `schema`, `game_data`, `prefix`,
`factori_root`. Native receipt at the existing mod receipt filename contains:

```json
{
  "protocol": "enhanced_v1",
  "original_sha256": "d40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978",
  "patched_sha256": "5a964d5155f8f7acc63fd90bc81882a0559c4586f5de4fd9a0657badd8594194",
  "game_data": "<absolute selected native data.win>",
  "platform": "linux",
  "prefix": "<absolute selected Proton prefix>",
  "factori_root": "<absolute selected account factori directory>",
  "ap_worlds": "<absolute selected native custom_worlds directory>"
}
```

Wine receipts require independent selected game and original-backup hash checks.
Drive mapping translation is purpose-specific: external `Z:` mappings are allowed
only when they resolve to the exact selected game file. No receipt alone proves
installation; unknown mappings, unsafe components, or wrong copies are refused.
Client-generated levels/campaign JSON may differ from package defaults: verify
checks structural campaign identity, receipt pairing and pinned binaries instead
of comparing room-generated data to ZIP bytes.

## Transaction behavior and scope

Preflight reconstructs the entire delta and verifies pinned compressed/original/
patched hashes, previous original backup, configuration/receipt pairing, mod JSON,
APWorld readability, permissions and target boundaries. It rejects aliases,
hardlinks and parent traversal for owned mutation targets. It rechecks process
state, target hashes and staged payload hashes before each replacement.

Every file is staged beside its destination. Historical before-images and the
complete journal are retained in `factori/archipelago/install-transactions/<id>`
outside scanned mods. An exclusive hardlink publishes a completely written,
fsynced active journal, avoiding partial-journal publication and overwriting a
competing installer. Game patch replacement occurs last. Restore/uninstall writes
the original game first. Ordinary exceptions roll back verified changes;
interruption leaves an active journal requiring explicit `recover`.

Recovery derives all actual target/stage/history paths from a validated descriptor,
fixed target keys and a strict transaction token, never from arbitrary journal
paths. It verifies all recovery inputs before any mutation, restricts game and
original-backup entries to pinned hashes, and refuses changed files/corrupted
history or staging. If a game starts or files change externally during failure,
rollback may be intentionally refused and the journal retained for inspection/
recovery after the uncertainty is resolved. No process is killed.

Uninstall removes only the five packaged mod JSON files, existing receipt,
`word_factori.apworld`, and matching selected configuration. It preserves original
backup, all historical backups, saves, generated runtime/sidecar files, all other
unowned files, and directories. `restore` removes the receipt after restoring the
game and leaves the remaining integration in place. Reinstall before uninstalling
an already-restored installation, because deletion requires a pairing receipt.

This is recoverable coordination across filesystems, not an atomic cross-filesystem
commit. Journal storage requires hardlink support; failure to publish leaves game
and integration files unchanged. Empty directories/staging or historical copies
can remain after a failure before journal publication; no unvalidated automatic
recursive cleanup is attempted.

## TDD and verification evidence

Initial RED: focused test import failed because `tools.install_linux` did not exist.
Initial GREEN: 9 real temporary-filesystem tests passed.

Subsequent observed RED/GREEN regressions covered installer-path process false
positives, a forged journal trying to delete the game, competing-journal ownership,
parent-traversal overrides, complete journal publication on interruption, and
corrupted staged game bytes. All were fixed before expanding verification.

Final focused command:

```text
python -m unittest tests.test_linux_installer -q
Ran 30 tests
OK (skipped=1)
```

29 passed on this Windows host. The one explicit platform skip is a real Linux
`dosdevices/z:` symlink test, whose colon filename cannot exist on Windows. Other
coverage includes install/update, restore/uninstall preserving saves/backups,
rollback, interrupted recovery, hostile journals, invalid hashes/receipt/config,
bad delta operations, late game changes, unavailable/running process inspection,
permissions, ambiguous discovery, Wine C: receipt migration, hardlink refusal,
generated-room JSON compatibility, APWorld helper loading without initialization,
and subprocess CLI verify/help/errors. Tests only patch fixture hashes and inject
process records; production path, hash, transaction and process-name guards run.

`git diff --check` passed. Full regression/release/package verification belongs to
parent integration. No real game writes, Windows installer runs, dependency
installation, pushes, publishing or Linux/Proton gameplay claims were made.
