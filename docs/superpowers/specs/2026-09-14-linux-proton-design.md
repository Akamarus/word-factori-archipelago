# Linux client with Word Factori through Proton

Status: implemented locally September 14; automated Windows verification passed.
Independent final review and Linux/Proton acceptance remain pending. Unpublished.

## Goal and boundaries

Allow installation from Linux and play through Steam Proton while the native
Linux Archipelago client handles items, checks, reconnection, and victory.
Preserve the current campaign, stable IDs, machine-only progression, and exact
native delta. This is platform support, not a second randomizer mode.

Keep the current Windows installer and overlay behavior unchanged. Linux uses
the regular Archipelago client for items and chat in this first phase. Do not
attempt a Linux in-game overlay, launch Wine as an installer workaround, change
game saves, generate a new native patch, or publish a release in this task.

No tester must post system paths, account identifiers, or logs publicly.
Discovery and configuration remain local; there is no telemetry or automatic
diagnostic upload.

## Approaches considered

1. Run the Windows installer and client together inside Wine/Proton. This
   introduces Windows-runtime dependencies and does not meet the requested
   native Linux client workflow. Not selected.
2. Native Python installer and a shared platform-path resolver. Reuses the
   existing delta and bridge while keeping platform differences at explicit
   boundaries. Selected.
3. Manual copying and environment-variable instructions. Useful for development
   but too error-prone as the normal installation experience. Explicit local
   path overrides remain available for unusual layouts.

## Existing causes and affected boundaries

- The root CMD invokes powershell.exe; install.ps1 assumes ProgramData and
  LOCALAPPDATA.
- WordFactoriContext defaults to a Windows-style AppData directory even on
  Linux.
- patch_ready interprets receipt game_data with the host's Path class. A
  Windows path written under Wine is not a usable native Linux absolute path.
- Mod selection and save discovery must also use the same selected Proton
  environment. Fixing only patch verification is insufficient.
- compatible_campaign conflates unavailable patch verification and actual
  campaign identity mismatch.
- The overlay's window tracking and input hooks are Windows-specific.

## Components and path contract

Add a small platform-path module shipped inside the APWorld, with no
Archipelago, GUI, or OS-specific imports at module load time. It resolves an
installation descriptor containing the native game-data path, Proton prefix,
and game-local AppData/factori directory. Windows retains its existing defaults.

Linux setup searches known native Steam and Flatpak Steam roots, then reads
Steam library metadata to discover additional libraries and Word Factori's
app installation and compatibility-data directory (app ID 2072840). Candidates
must be validated on disk; no recursive home-directory scan is permitted.
Support explicit game, prefix, and Archipelago custom_worlds paths when
discovery fails. If several valid candidates remain, ask the player to choose
locally instead of selecting the first one.

Do not create a Proton prefix. If the game's prefix has not been initialized,
explain that the player must launch and close the game once through Steam.
Validate the prefix's game AppData location rather than assuming the host Linux
username or silently choosing among multiple Windows users.

Persist the selected Linux installation in a versioned, local-only configuration
under the absolute XDG_CONFIG_HOME directory, or ~/.config when unset/invalid.
Use a Word Factori Archipelago-specific filename. Store only needed paths and
schema information, never room passwords. Setup and the client read this same
descriptor; room state and saves remain in their existing integration/game
locations inside the selected prefix.

Resolve Windows paths found in game metadata through the selected prefix's
drive mappings, not through the Linux client's current directory. Match the
resolved selected mod to the expected mod by actual file identity/path.
Reject unknown mappings, malformed paths, unrelated destinations, and
traversal outside the expected game account/mod subtree. Handle separators
and spaces without executing shell expressions from path text. Steam-root
symlinks can be resolved during discovery; symlinked mutation targets require
explicit validation and must never redirect cleanup outside the selected scope.

## Linux installer and patch safety

Add a root Linux shell entry point backed by Python standard-library code.
Require Python 3.12+ and an existing native Linux Archipelago installation.
The entry point checks dependencies and provides clear local prompts; it does
not install system packages, invoke sudo, or require Wine/PowerShell.
Document invocation with bash so ZIP executable-bit preservation is unnecessary.

The installer performs preflight and shows the exact local destinations before
the user confirms installation. Validate the APWorld and bundled mod data, the
pinned compressed delta hash, original/patched game hashes, receipt pairing,
backup contents, write permissions, target boundaries, and closed-game state.
Reuse or extract the existing validated COPY/literal decoder; do not distribute
a second independently generated patch. Reconstruct and hash the full result
before replacing any installed game data.

Preserve the exact original as data.wf-ap-original.win. An existing backup must
match the pinned original hash; never overwrite an unknown backup. An already
patched game may be accepted only with its verified original backup and correct
game pairing. Unknown binaries must be refused. A Wine-written receipt is not
proof of installation; a Linux installation must independently verify the
selected game and backup before writing a native-path receipt.

Stage sibling files on their destination filesystems and keep previous mod
versions outside the game's scanned mods directory. Record recoverable
transaction state before replacement, apply the game patch last, and restore
previous integration files/configuration on an ordinary failure. A subsequent
run must detect interrupted transactions and offer recovery instead of treating
a partial install as complete. Recheck relevant hashes and running-game state
immediately before replacement; abort when required process-state inspection is
unavailable. Do not promise an atomic transaction spanning multiple filesystems.

Provide install/update, read-only verification, restore-original, and uninstall
operations. Uninstall restores the game before removing only the validated
integration-owned files. Preserve all game saves, original backup, and prior
installation backups. Refuse ambiguous or unrelated deletion targets.

## Client behavior and diagnostics

The native Linux client uses the configured descriptor to find the receipt,
game data, mod selection, account reference, active save, and runtime sidecars.
Keep digest validation, authoritative item reconciliation, empty-slot binding,
and duplicate-check protection intact.

Return structured readiness failures: setup missing, configured path missing,
receipt invalid, game hash mismatch, backup/setup verification issue, or
campaign identity mismatch. Only an actual campaign mismatch should use that
message. Missing patch readiness blocks campaign preparation/check submission
without a second misleading campaign error.

On Linux, disable the Windows overlay before spawning its renderer and explain
once that items/chat are available in the regular client. This must not affect
networking or progression. Unknown paths or missing configuration should lead
to setup instructions, not writes to a guessed AppData directory.

## Packaging and compatibility

Keep one player ZIP containing the APWorld, existing Windows entry points,
Linux entry point/helpers, one delta, and platform-specific instructions.
Update the explicit package allowlists and integrity verification accordingly.
No player game binaries, recipes.data, fonts, saves, or local configuration are
included. Existing 1.4.0 campaign contracts remain unchanged by this feature;
do not require a new room merely because the host OS changes. An existing room
must still satisfy its original save-binding and identity checks.

Do not update the installed Windows game/client, reset a room, push to GitHub,
or publish a new tester package without a subsequent explicit request.

## Verification and acceptance

Use test-first changes with real temporary filesystem fixtures. Cover:

- Native and Flatpak Steam roots, additional libraries, spaces, missing prefixes,
  multiple candidates, malformed metadata, local overrides, and case handling.
- Windows-path translation, unknown drive mappings, selected-mod identity,
  account path containment, and refusal of unsafe targets.
- Native Linux receipts and independently verified migration from Wine-path
  receipts; reject wrong game/backup/patch hashes.
- Install, idempotent update, restoration, uninstall, rollback, interrupted
  transaction recovery, permission failures, and running-game refusal.
- Client setup errors versus campaign mismatch; normal runtime publication,
  check reading, reconnect, duplicate delivery, and victory with Linux paths.
- No Linux overlay process; unchanged Windows behavior and archive contents.

Run the full Windows regression suite and release verifier. Add Linux CI for
platform-neutral and Linux installer/client tests; Windows-only process tests
must be explicitly scoped, not hidden by blanket skipping. Synthetic game
fixtures test failure/transaction behavior; separately verify the real bundled
delta against the user's owned original game in a private disposable directory.

Actual compatibility remains unverified until a real Linux/Proton session
demonstrates setup, mod detection, a completed check, a newly received machine
after factory entry, reconnect, and restoration. Automated filesystem tests or
WSL tests do not establish Proton gameplay acceptance. Label any eventual
Linux build experimental until that evidence exists.
