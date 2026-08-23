# Word Factori In-Game Archipelago Client Design

**Date:** 2026-08-23

**Status:** Approved design; implementation not started

**Target:** Item-only prototype first, full client before official release

## Purpose

Add a native-looking Archipelago interface that appears over Word Factori while preserving the project's existing safety boundary. The interface must show items sent and received, retain room-scoped history, and look like part of Word Factori rather than a generic text overlay.

The first release of this subsystem is item-only. The architecture must support chat, commands, connection controls, and complete replacement of the visible generic client before the integration is described as an official release candidate.

## Constraints

- Do not patch or redistribute `data.win` or any other proprietary game binary.
- Do not invent or write unverified Word Factori save fields.
- Do not require a separate runtime, background service, overlay installer, or network connection.
- Do not allow overlay failure to interrupt checks, item delivery, level regeneration, or victory reporting.
- Keep the player installation to one downloaded package and one installer action for prototype releases.
- Continue supporting Windows, Archipelago 0.6.7, and the verified Word Factori depot first.
- Preserve the regular client interface as a fallback.

## Verified capability boundary

Word Factori's supported mod format exposes JSON-controlled levels, recipes, tips, credits, stickers, title art, preview art, and an optional letter font. It does not expose verified runtime scripting or custom UI hooks. A live notification client therefore cannot be implemented as a JSON-only game mod.

The installed game includes `FredokaOne.ttf` as a standalone file. The overlay will load that installed font at runtime and will not copy it into release artifacts.

Archipelago provides the required event data through ordered `ReceivedItems` packets and structured `PrintJSON` packets of type `ItemSend`. The client remains the sole Archipelago network peer.

References:

- [Archipelago CommonClient](https://github.com/ArchipelagoMW/Archipelago/blob/main/CommonClient.py)
- [Archipelago network protocol](https://github.com/ArchipelagoMW/Archipelago/wiki/Archipelago-Network-Protocol/8652186a7a1f0f35ca781d45dfc9501f61c05060)

## Chosen presentation

Use a Word Factori-styled **Mailbox + Dispatch Ledger**.

### Collapsed state

- A small red mailbox button sits on the left side of the game workspace.
- An unread badge shows the number of unseen dispatches.
- All other overlay space is click-through.
- Pressing `F8` or clicking the mailbox opens the ledger.

### New-item notification

- A blue rounded popup appears on the left beside the mailbox.
- It uses the installed Fredoka One font and Word Factori-derived colors, spacing, corners, borders, and shadows.
- The primary line identifies the item and direction.
- The secondary line identifies the other player and game.
- Notifications remain visible for six seconds.
- At most three notifications queue visibly; later notifications wait in order.
- Opening the ledger dismisses visible notifications without deleting history.
- Historical synchronization never creates a popup storm.

### Expanded ledger

- The ledger opens as a rounded dark panel with a purple header.
- It provides `All`, `Received`, and `Sent` filters.
- Each row has a direction icon in addition to color, so direction is not color-dependent.
- Entries show item, player, game, local source location when relevant, and a local observed time.
- Long names wrap without overlapping controls.
- A footer displays actionable state such as `reload your Word Factori slot to use Merger2`.
- `Escape`, `F8`, clicking the mailbox, or clicking outside the panel closes it.
- Keyboard focus is never taken while the ledger is closed.

### Focus behavior

- The overlay follows the Word Factori window's position, dimensions, monitor, and Windows display scaling.
- It hides when Word Factori is minimized or not focused.
- Events received while hidden remain queued and are presented when the player returns.
- Windowed and borderless-fullscreen modes are supported initially.
- Exclusive fullscreen uses the regular client fallback until explicitly verified.

## Architecture

```text
Archipelago server
       |
       v
WordFactoriContext (authoritative network and bridge state)
       |
       v
DispatchEventNormalizer
       |
       +--> DispatchLedgerStore
       |
       v
OverlayPresentationModel
       |
       v
private process pipe
       |
       v
KivyOverlayProcess --> Word Factori window tracking
```

### WordFactoriContext

The existing client continues to own the Archipelago connection, save scanning, check submission, item reconciliation, mod regeneration, and victory. It forwards relevant packets to the dispatch subsystem after its normal processing.

### DispatchEventNormalizer

Converts Archipelago packets into immutable, renderer-independent events. It resolves item, location, player, and game names through the connected data package and slot information.

It emits only events involving the local slot:

- an item received by the local slot;
- an item sent from a checked Word Factori location to another slot; or
- an item found locally for the local slot.

It does not emit general chat, joins, parts, hints, or unrelated players' item traffic during the item-only phase.

### DispatchLedgerStore

Persists normalized events separately from `BridgeState`. A corrupt cosmetic ledger must not affect progression safety.

The store is:

- scoped by seed, team, and slot using the existing connected identity convention;
- written beneath `%LOCALAPPDATA%\factori\archipelago`;
- limited to the latest 200 entries;
- written atomically through a temporary file and replace operation;
- rebuildable from authoritative server state;
- versioned independently for future schema migrations.

### OverlayPresentationModel

Owns unread state, active filter, notification queue, display duration, reload-required state, connection state, and overlay preferences. It contains no Kivy widgets and can be unit tested without a graphical environment.

### KivyOverlayProcess

Runs as a child process launched automatically by the Word Factori client. It uses the Kivy runtime already distributed with Archipelago.

The renderer:

- loads `FredokaOne.ttf` from the running Word Factori installation;
- falls back to the standard Archipelago GUI font if the file is unavailable;
- draws only original geometric UI elements and does not copy proprietary sprites;
- receives presentation updates through a private parent-child process pipe;
- returns only local UI actions such as open, close, filter, and mark-read;
- uses Windows window styles and hit testing so non-interactive areas remain click-through.

The overlay process never receives the Archipelago password or opens a server connection.

### GameWindowTracker

Locates `word factori.exe` through the running process rather than assuming a Steam library path. It observes window bounds, minimized state, foreground state, monitor, and display scaling. It reports unsupported modes to the parent so the regular client can be used as a fallback.

## Event identity and reconciliation

### Received items

`ReceivedItems` is authoritative. A received event is keyed by room identity and its zero-based receive sequence index. The starting `Bender Access` pseudo-item is not displayed as a network delivery.

On reconnect:

1. Rebuild the authoritative received sequence.
2. Retain existing matching ledger entries.
3. Add missing historical entries without individual notifications.
4. Notify only for indices beyond the previously acknowledged high-water mark.
5. Remove stale cosmetic entries that cannot exist in the authoritative sequence.

### Sent items

Live sends are recognized from structured `PrintJSON` packets of type `ItemSend` where the source player is the local Word Factori slot. A sent event is keyed by room identity, source location, item, and recipient.

To reconstruct events missed while the client was closed, the client requests `LocationScouts` only for already checked local Word Factori locations. Returned `LocationInfo` data supplies the item and recipient without revealing unchecked placements.

### Self items

When source and recipient are both local, create one `found for yourself` entry. Do not create separate sent and received rows or duplicate notifications.

### Time

Archipelago item packets do not provide a durable event timestamp. New events store the local observation time. Reconstructed historical events are labeled `earlier` instead of displaying an invented exact time.

## Process isolation and recovery

- The parent client starts the overlay after client initialization.
- If the game is not running, the overlay waits without opening a visible window.
- If the renderer exits unexpectedly, the parent logs the error and attempts one automatic restart.
- Repeated renderer failure disables the overlay for the session and leaves the regular client operational.
- A broken pipe cannot block the network or save watcher loops.
- On client shutdown, the parent asks the renderer to close and then terminates only that owned child if it does not exit promptly.
- Switching rooms replaces the active presentation state and never mixes ledgers.
- Disconnecting changes the ledger status to disconnected but preserves history.

## Preferences

The item-only release supports:

- overlay enabled;
- interface scale;
- left-side vertical offset;
- notification duration;
- reduced motion;
- maximum visible queued notifications.

Defaults match the approved mockup. Preferences are stored locally and do not affect logic or the Word Factori save.

## Installation and launch

### Prototype release

The release remains a single ZIP. It includes a friendly double-click installer wrapper and retains `install.ps1` for advanced and unattended use.

Player flow:

1. Extract the ZIP.
2. Double-click **Install Word Factori Archipelago**.
3. Launch **Word Factori Client** from the Archipelago Launcher.
4. Start Word Factori.
5. The overlay attaches automatically.

No separate overlay program, font, Python package, WebView, service, or runtime is installed. `-Force` remains the supported update path. An uninstall option removes only integration-owned files.

### Official release

When the world ships with Archipelago, players install only the supported Word Factori mod content and launch the standard Word Factori component. The integrated client handles the remaining setup.

## Full-client expansion gate

The item-only phase is a prototype and does not qualify the integration for an official release. The same overlay and event boundaries must be extended to support:

- connecting and disconnecting;
- slot selection and password requests;
- automatic reconnection;
- Archipelago chat display and input;
- commands, hints, and command results;
- server, campaign, mod, save-slot, and version errors;
- keyboard focus only while the ledger is open;
- operation without keeping the generic client visible.

Full-client input is sent to the authoritative parent process. The renderer never constructs protocol packets or stores credentials.

## Testing

### Unit tests

- received index normalization and duplicate handling;
- sent event normalization and local-slot filtering;
- self-item collapse;
- historical synchronization without popup storms;
- checked-location scout reconstruction;
- room-scoped persistence and migration;
- corrupt-ledger recovery;
- notification queue limits and unread behavior;
- connection and reload-required presentation state;
- long display names and missing lookup data;
- renderer-pipe serialization and malformed-message rejection.

### Integration tests

- mocked `ReceivedItems`, `PrintJSON`, `LocationInfo`, reconnect, and room-switch sequences;
- bridge and check processing continue when the overlay is disabled or crashes;
- child startup, one-restart policy, clean shutdown, and fallback behavior;
- installer clean install, forced update, and uninstall;
- release archive excludes proprietary fonts, game binaries, saves, and generated rooms.

### Visual and live acceptance

- 1920x1080, 2560x1440, and representative ultrawide layouts;
- Windows 100%, 125%, and 150% display scaling;
- windowed, borderless, minimized, focus switching, resize, and multi-monitor movement;
- long player, game, item, and location names;
- live two-player sent, received, self-item, reconnect, and missed-send scenarios;
- visual comparison against the approved blue left-toast and mailbox mockup;
- confirmation that unsupported display modes fall back without lost events.

## Out of scope for the item-only phase

- Chat, commands, hints, and connection entry inside the overlay
- DeathLink or trap presentation
- Arbitrary game UI injection
- Exclusive-fullscreen support without verification
- Linux or macOS overlay support
- Redistributing Word Factori fonts, icons, sprites, or other proprietary assets
- Replacing the existing save bridge or recipe logic

## Completion criteria

The item-only subsystem is complete when it installs with the existing package, automatically attaches to Word Factori, displays and persists deduplicated local sends and receives in the approved style, survives reconnects and renderer failures, passes the automated and live acceptance matrix, and leaves all existing integration behavior unchanged when disabled.

The integration is eligible to drop the experimental label only after the full-client expansion gate is implemented and its connection, chat, command, error, focus, installation, and live multiworld acceptance tests pass.
