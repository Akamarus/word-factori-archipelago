# Full In-Game Client Acceptance

Status: **PRIMARY PATH PASSED — experimental public beta**

- Test date: 2026-08-23
- Platform: Windows 10.0.19045, 2560×1440, 125% scaling
- Archipelago: 0.6.7 frozen launcher
- Word Factori: Steam build 12616577

This is the release record for the Word Factori-styled Archipelago client that
renders over the game. It separates tested release behavior from display and
authentication permutations that still need additional machines.

## Automated evidence

`python -m unittest discover -s tests -v` ran 260 tests with zero failures. The
suite covers connection intents, password clearing, message normalization,
authoritative item/check reconciliation, room switching, renderer isolation,
native focus/hit regions, DPI setup, resize/minimize boundaries, generation,
goals, installer safety, and reproducible release archives.

The exact Archipelago 0.6.7 frozen generator loaded Word Factori 1.2.0 and
generated a deterministic two-player room containing one 30-location
`core_campaign` player and one 40-location `discovery_labs` player. It filled 70
items, calculated the playthrough, and wrote the room archive.

## Live acceptance matrix

| Area | Status | Recorded evidence |
|---|---|---|
| URI connect | PASS | Frozen client joined the local 0.6.7 room from an `archipelago://` launch. |
| Game binding | PASS | Selected mod, compatible campaign, active empty save binding, and bridge-ready state were reported by `/wf_status`. |
| Items/Chat | PASS | Both styled tabs rendered over Word Factori; retained captures are in this directory. |
| Text command | PASS | The real Chat composer submitted `/wf_status`; the parent handled it and its response rendered in Chat. |
| Focus and hit map | PASS | F8/Escape round-trip, owned-window focus, rounded native input regions, and click-through game area were exercised. |
| Minimize/restore | PASS | Launch while minimized no longer creates a zero-sized Kivy mouse surface; restore attaches normally. |
| URI reconnect | PASS | Reconnect retained one authoritative delivery without a duplicate row or unread replay. |
| Renderer failure | PASS | Parent networking remained connected and the cosmetic child restarted once. |
| Normal shutdown | PASS | Closing the parent removed the owned child and restored the native hooks. |
| 2560×1440, 125%, windowed | PASS | DPI-correct overlay size, placement, panel regions, and game click-through recorded. |
| Manual overlay connect | AUTOMATED | Address/slot/password intents and status transitions are covered; a separate live manual-connect run remains desirable. |
| Password-protected room | AUTOMATED | Masking, one-shot submission, and clearing are covered; no live protected room was used. |
| 100%/150%, ultrawide, mixed DPI | PENDING | Requires additional display configurations. |
| Exclusive fullscreen | FALLBACK | Unsupported by design; use borderless/windowed or the regular client. |

## Decision

The normal Windows path is suitable for a public experimental 1.2.0 release.
The remaining rows limit the release label, not core playability. No pending row
is promoted by inference, and the regular Archipelago client remains available
whenever the optional renderer is unavailable.
