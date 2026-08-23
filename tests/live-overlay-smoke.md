# Word Factori in-game client live-smoke gate

Status: **PRIMARY WINDOWS PATH PASSED**

Recorded on 2026-08-23 with Windows 10.0.19045, 2560×1440 at 125%,
Archipelago 0.6.7 frozen launcher, and Word Factori Steam build 12616577.

## Passed

- [x] Frozen launcher starts one client parent and one bundled-Kivy child.
- [x] Selected mod, campaign digest, empty-slot binding, received delivery, and
  ready bridge are reported by the real `/wf_status` path.
- [x] Left mailbox, Items panel, Chat panel, and command response render over
  the windowed game using the discovered game font.
- [x] Native rounded input regions accept overlay controls; points outside them
  hit Word Factori.
- [x] F8 opens, Escape closes, input focus returns, and external focus does not
  leave Chat trapping the keyboard.
- [x] A minimized game at child startup is ignored until restore, avoiding a
  zero-size renderer surface; the restored game attaches normally.
- [x] Reconnect retains authoritative history without duplicate durable rows or
  unread replay.
- [x] First renderer failure restarts once; repeated cosmetic failure leaves the
  parent client connected.
- [x] Normal parent shutdown removes the owned child and restores hooks.

## Additional beta configurations

- [ ] Password-protected live room.
- [ ] 100% and 150% Windows scaling.
- [ ] Ultrawide and mixed-DPI monitor movement.
- [ ] Borderless mode on a second machine.

Exclusive fullscreen is an intentional fallback: use windowed/borderless mode
or the standard client. Automated tests remain required for all rows and cover
the unsupported live configurations' state, protocol, and failure boundaries.
