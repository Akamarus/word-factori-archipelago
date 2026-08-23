# Item-Ledger Overlay Acceptance Record

Status: **PRIMARY PATH PASSED — experimental public beta**

- Test date: 2026-08-23
- Platform: Windows 10.0.19045, 2560×1440, 125% scaling
- Archipelago: 0.6.7 frozen launcher
- Word Factori: Steam build 12616577

## Accepted boundaries

- The frozen launcher starts one networking parent and one cosmetic renderer
  child using bundled Kivy. The child receives validated visual snapshots and
  actions only; credentials and the AP network context remain in the parent.
- The package excludes `data.win`, installed recipes, proprietary fonts, save
  files, credentials, generated rooms, and session artifacts.
- Initial room history is silent. New received, sent, and self events reconcile
  by authoritative indexes. Replayed packets and reconnect do not duplicate
  durable rows or unread state, and switching room identity replaces history.
- The left-side mailbox, Items panel, Chat panel, native rounded hit regions,
  and `/wf_status` response were rendered over the live game. Outside the active
  regions, hit testing returns the Word Factori window.
- F8 and Escape return focus correctly. Launch while the game is minimized,
  restore, external focus changes, and normal parent shutdown do not crash or
  strand the renderer.
- One renderer crash is restarted; a repeated failure disables only the
  cosmetic child while checks, item reconciliation, and unlock rendering remain
  active in the standard client.

## Open beta matrix

Live 100%/150% DPI, ultrawide, mixed-monitor DPI, and password-protected-room
runs remain unrecorded. Exclusive fullscreen is unsupported by design. These
rows prevent an official/upstream label but do not block the experimental 1.2.0
package. Automated contracts cover bounded names, Unicode, reduced motion,
cosmetic preference ranges, password clearing, connection errors, and fallback.

## Automated release evidence

The full suite completed 260 tests with zero failures. Release building,
verification, installed-copy parity, fresh locally derived recipe requirements,
frozen two-player generation, archive reproducibility, and proprietary-data
exclusion all passed.
