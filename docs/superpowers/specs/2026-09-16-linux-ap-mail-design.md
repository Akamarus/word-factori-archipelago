# Linux AP Mail: native in-game presentation

Date: 2026-09-16

Status: direction and detailed specification approved by Jack on 2026-09-16.
This document does not claim implemented Linux UI support. It changes no live
installation, save, room, release or existing Windows presentation.

## Goal and scope

Give Linux/Proton players AP Mail inside Word Factori, styled like the approved
Windows panel, without requiring a separate overlay window or a second Windows
Archipelago installation. Keep the existing Linux installer and native client.

The first complete delivery includes Items, Chat, Type-a-Word, delivery popups
and connection status. It is not an items-only release. Initial connection,
server/slot selection and password entry remain in the regular Linux client,
as approved. The panel can request disconnect/reconnect using that client's
existing configuration; it never puts credentials in mailbox files.

Full in-panel connection forms and replacing the Windows overlay are outside
this change. Linux UI acceptance is distinct from a future stable-release
decision about complete cross-platform client parity.

## Existing integration and ownership

The current Linux client explicitly disables the Windows overlay. Its installer
already pairs native Archipelago with a selected Steam/Proton game and mod
directory. The verified native patch already exchanges room-bound JSON with the
client, but has no AP Mail drawing or input hooks. Those hooks need proof; they
are not assumed to exist merely because GameMaker supports drawing and input.

| Component | Owns | Must not do |
|---|---|---|
| Existing Python client | Networking, check reconciliation, item history, chat, selected targets | Depend on the panel for progression |
| New native-mail adapter | Bounded presentation snapshots, action validation and acknowledgments | Write game saves, grant items or accept check-completion actions |
| New native game panel | Drawing, local open/tab/scroll state, input capture, action requests | Connect directly to AP or reinterpret progression rules |
| Existing installer | Exact-build patch verification, original backup, paired paths | Require sudo, a compositor extension or unverified executable downloads |

Reuse the existing dispatch ledger, client transcript, word-order presentation
and command routing where appropriate. Do not duplicate their progression or
room-resolution logic. Keep the transport separate from the Windows renderer
protocol; Windows remains on its existing presentation path for this delivery.

## User experience

- Red AP MAIL button on the left with unread delivery count; F8 also toggles it.
- Blue item notifications on the left, no focus stealing and no overlap with
  the expanded panel. Historical reconnect deliveries do not replay as new.
- Dark rounded panel, purple header, native game font and matching controls.
  No proprietary fonts or textures are redistributed.
- Tabs: Items, Chat, Type-a-Word, and connection status. Items has All, Received
  and Sent filters. Chat displays messages, hints and command results. Words
  display selected room targets and Not completed / Sending / Completed status.
- Opening, closing, filtering, scrolling and changing tabs happen immediately
  against cached data, without waiting for a bridge round trip.
- Server-confirmed checks determine Completed; the existing pending queue
  determines Sending. The words tab cannot mark a target complete.
- Escape, F8 or Close dismisses the panel. An outside click dismisses it but is
  consumed rather than placing a machine underneath. Tab switches never close
  the panel. Mouse wheel over the panel scrolls it, not the factory.
- Chat input owns keyboard input only when explicitly focused. Enter sends;
  Shift+Enter inserts a newline. Game shortcuts, text entry and placement must
  not also receive AP Mail's input. No global keyboard hook is needed.
- Opening the panel does not alter simulation speed or progression. Focus loss
  releases input capture; room changes and disconnection clear unsent drafts.
- Scale and clamp the panel within the game's GUI viewport. Test windowed and
  fullscreen operation, resize, display scaling and focus changes. A failed
  native input/layout probe blocks rollout rather than weakening this contract.
- Unsupported text glyphs use readable fallbacks. Key/door target symbols retain
  the same explicit labels as the Windows word list if native glyphs cannot be
  safely reused. Text rendering must never execute markup supplied by players.

If the client is absent, AP Mail opens an explanatory local status panel.
On a live disconnect it retains this session's history labeled offline, disables
send and offers reconnection through the configured client. Room switches clear
old history, targets and notifications before showing another room.

## File bridge contract

Use integration-owned files beneath the selected mod's `archipelago_mail`
subdirectory. Python resolves paths through existing installation validation;
the game uses fixed relative names. No payload supplies a filesystem path.
This bridge is for cooperating processes under the same user account, not an
authentication boundary against other processes with that user's file access.

### Client to game

- A small manifest carries protocol version, a fresh client-session identifier,
  current presentation revision and heartbeat sequence. A presentation snapshot
  carries the matching session/revision plus room identity, contract identity,
  connection state, bounded rows, target status and action acknowledgments.
- The game announces a fresh renderer-instance identifier on startup. Interactive
  delivery requires a matching handshake; files left by a previous game process
  cannot authorize sending or replay old notifications.
- Read the manifest at most four times per second from the normal UI update
  path. Read/parse the larger snapshot only when its revision changes. Never do
  filesystem work in drawing callbacks, machine operations or simulation ticks.
- Heartbeats advance once per second. Five seconds without an observed advance
  marks the bridge unavailable and disables outbound actions. Use elapsed local
  time, not comparisons between Windows/Proton and Linux wall clocks.
- Manifest limit: 4 KiB. Snapshot limit: 256 KiB, with at most 50 item rows,
  50 transcript rows, 20 word targets, three active notifications and 32 action
  acknowledgments. Display text is truncated to bounded fields; the full ledger
  remains in the regular client. Oldest history is trimmed first if the aggregate
  byte ceiling would be exceeded; authoritative target rows are never discarded.
- Snapshots are published through same-directory temporary files and replacement.
  Verify this behavior across native Linux and Proton in acceptance tests. The
  reader checks file size, schema, session, revision and field bounds before
  using it. Missing/partial/mismatched data preserves only a labeled last-good
  display until freshness expires; it never crashes the game.
  Invalid updates disable interactive sending immediately. Last-good history is
  retained only for the same validated room; a changed room clears it.

### Game to client

- Fixed-name request file, one outstanding request at a time; a bounded envelope
  contains protocol, client session, renderer instance, room, sequence number,
  action kind and bounded payload. Acknowledgment is tied to that exact identity.
  A separate bounded hello record establishes the renderer handshake before any
  request is accepted. Only one active renderer/client pair may own a mailbox;
  conflicting owners disable Mail with a regular-client warning.
- Allowed actions are submit text, acknowledge displayed deliveries, request
  older bounded history, disconnect and reconnect. Opening/tabs/scrolling stay
  local. No item granting, check completion, save editing, shell execution or
  arbitrary file actions are exposed.
- Submitted text is capped at 1,024 code points and 8 KiB for the whole request.
  Use the existing validated chat/server-command path. Local commands use an
  explicit allowlist for status/help/word-list operations. Credential-changing
  commands are rejected with an instruction to use the regular client.
- Reconnect is a connection-control action for the current paired client session,
  not an old room's queued action. It uses configuration already held by that
  client and requires a fresh click; room-bound chat remains disabled offline.
- Python validates the current session and room, processes sequence numbers
  once within that session and returns an acknowledgment. Retries of a request
  already handled return its existing result, without resending chat.
- UI states distinguish queued, forwarded to client/server transport, rejected
  and delivery uncertain. A transport acknowledgment is not proof every recipient
  saw the chat. After a client crash/session change, an uncertain chat message is
  never automatically replayed; tell the player to inspect chat before resending.
- A full queue disables Send temporarily, with a visible explanation. It does
  not overwrite a pending request or freeze the UI. Degraded filesystem behavior
  disables interaction and leaves the regular client usable.

No connection password is included in either envelope. Ordinary chat content is
local application data and must not be uploaded automatically in diagnostics.

## Native patch and failure containment

Use only the allowlisted original game build and the existing reversible delta
process. First identify and test native GUI drawing, UI input dispatch, font
selection, room lifecycle and GUI-coordinate conversion in a scratch copy.
Keep hook transforms exact and reject absent/ambiguous sites. Do not copy
decompiled source or game resources into the repository or player package.

Input capture must cover the game's real input dispatch path, not just its tick
function. Prove that consumed clicks and keys cannot reach game UI or factories.
Native panel state must be reset safely on room transitions, with one owning
instance and no accumulating draw handlers, surfaces or polling timers.

Contain parsing, rendering and bridge errors at their respective boundaries.
If AP Mail fails, release all input capture, clear pending visual state and show
an actionable regular-client message. No error handler may interrupt or weaken
the machine-budget enforcement introduced by the earlier performance fix.

Enable native Mail only for the paired AP mod and a supported Mail capability
handshake. Missing Mail capability disables only the UI after ordinary progression
compatibility has passed; it does not broaden the permitted game-hash set. An
incompatible progression patch remains subject to existing strict verification.
Vanilla mode must have no AP Mail hooks active.

## Installation and release behavior

Deliver the native UI in the existing player ZIP and Linux installer. Updating
requires closing the game and rerunning the installer; no new launch wrapper,
Wine-based AP client, graphical package manager or sudo step is introduced.
The normal Linux client launches as it does today and provides the fallback.
Treat mailbox files as ephemeral integration-owned runtime state, not save data.
The installer must preserve unrelated files and the verified original backup.

No YAML changes, check IDs, recipe requirements or room layout changes are
needed for Mail. UI errors and UI disablement must not change progression.
Do not merge, install or publish this work as part of approving this document.

## Validation and decision gates

1. **Native feasibility:** on a scratch game copy, prove GUI positioning/font,
   immediate toggle, click/key consumption, tab switching, focus loss and lifecycle
   cleanup. If this fails, report the precise blocker before adopting a companion
   window; the approved in-game design is not silently replaced.
2. **Protocol tests:** malformed/oversized files, missing fields, stale revisions,
   wrong room/session, duplicate requests, interrupted replacement, client/game
   restart, uncertain chat delivery and stale heartbeat. Test no progression
   mutations and no credentials in envelopes.
3. **UI/native tests:** Items filters, bounded history, selected-word states,
   all tabs, wrapping and symbol fallback, scroll behavior, immediate open/close,
   no click-through, no shortcut leakage, vanilla isolation and error recovery.
4. **Performance:** measure polling/parsing separately from simulation. Confirm
   one-time setup, stable resource counts and no ever-growing transcript/cache
   during repeated room changes and a sustained session. Existing quantity-tick
   enforcement and performance regressions must remain passing.
5. **Packaging:** exact patch hash, compile/reopen checks, delta round trip,
   upgrades/restores on both installer paths, owned-file hygiene and no game
   binaries/fonts/raw recipes in the player ZIP. Windows presentation stays intact.
6. **Real Linux acceptance:** test a connected two-player room on X11 and Wayland
   under Steam Proton, fullscreen and windowed; include native and Flatpak Steam
   path handling where available. Complete checks, receive upgrades, use all Mail
   tabs, exchange chat, reconnect and reach victory. Windows scratch probes do
   not count as Linux evidence. Collect only volunteered, redacted diagnostics.

The current host is Windows and cannot establish Linux compositor/Proton behavior.
Automated and scratch-native milestones may finish here, but Linux support remains
experimental until the required external playthrough evidence exists. The full
client requirement before an official release remains open, not waived by this UI.

## Proposed implementation boundaries

- Separate Python native-mail transport/model modules, integrated at the existing
  client presentation and action boundaries; avoid enlarging the Windows renderer.
- Integration-authored native Mail UI/bridge helpers and narrowly verified hook
  transforms, with a standalone scratch acceptance harness.
- Unit, lifecycle, protocol and native acceptance fixtures; installer/release
  manifest updates only after the candidate patch passes its gates.
- Player-facing Linux instructions updated when the feature is actually packaged,
  clearly distinguishing automated evidence from real Linux playtesting.

Implementation ordering is recorded in
`docs/superpowers/plans/2026-09-16-linux-ap-mail.md`.
