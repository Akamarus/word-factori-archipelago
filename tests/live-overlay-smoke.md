# Word Factori item-ledger overlay live smoke gate

Status: **PARTIAL — frozen process and failure-isolation rows passed; visual/input rows remain pending.**

Live run: 2026-08-23, Codex; Windows 10.0.19045; Archipelago 0.6.7 frozen launcher;
Word Factori Steam build 12616577; APWorld SHA-256
`4d97dbd7fa4345cc6f80b188de53be93d8082ea7d798cd3c3e6bdcade1d37965`.
The desktop capture provider failed for both GameMaker and Kivy with
`SetIsBorderRequired ... 0x80004002`, so no visual row is inferred from process,
ledger, or source evidence. Monitor layout and DPI variants remain unrecorded.

Do not mark any row PASS from mocks, source review, an unfrozen Python run, or a screenshot alone. Run this checklist on Windows using the exact development APWorld installed into the same Archipelago build being tested. Record the Archipelago version, APWorld commit, Word Factori depot/build, Windows display scaling, monitor layout, and tester/date before changing a status.

## Prerequisites

- Build and install the development APWorld without copying `FredokaOne.ttf` or any game binary into it.
- Confirm the installed game directory contains `word factori.exe` and, for the primary font case, `FredokaOne.ttf` beside it.
- Prepare a valid room/slot with one known received item, one item sent to another player, and one self item.
- Keep the ordinary Word Factori Client visible as the fallback and capture its logs.
- Launch the component only through the frozen `ArchipelagoLauncher.exe` flow; do not substitute a source Python process.

## Hard process/runtime gate

- [x] **PASS** — `ArchipelagoLauncher.exe` started one frozen Word Factori Client process and exactly one later overlay child process. Repeated clean launches reproduced the one-parent/one-child boundary.
- [x] **PASS** — The child imported Kivy 2.3.1 from `C:\ProgramData\Archipelago\lib\library.zip` under frozen Python 3.13.11 and entered its application loop without a separate runtime, download, WebView, or service.
- [ ] **PENDING** — The child receives only visual configuration and pipe messages; inspection/logging shows no server address, slot password, AP context, or network connection in the child.
- [ ] **PENDING** — With the installed `FredokaOne.ttf` present, the UI visibly uses Fredoka One. After temporarily renaming that font while the game is closed, the next launch uses the bundled GUI fallback and remains readable; restore the file afterward.

If the frozen child cannot spawn or import Kivy, stop Task 6. Do not add a runtime download and do not move networking into the renderer.

## Attachment, scaling, and interaction

- [ ] **PENDING** — With Word Factori absent, no overlay window is visible. Starting the game windowed attaches the mailbox to the left side within one second.
- [ ] **PENDING** — A new received item shows one blue popup on the **left**, with received wording, item, player, and game; a sent item uses sent wording; a self item appears only once as “for yourself.”
- [ ] **PENDING** — The red mailbox shows unread count. Clicking it opens a dark rounded ledger with purple header, All/Received/Sent filters, direction icons, scrollable rows, and connection/reload status.
- [ ] **PENDING** — Clicking mailbox, toasts, ledger rows/scrollbar, and filters works. Clicking the factory grid anywhere outside those current rectangles passes through and controls the game.
- [ ] **PENDING** — `F8` toggles the ledger without focusing the overlay while closed. Escape/close behavior does not leave keyboard focus trapped.
- [ ] **PENDING** — Moving and resizing Word Factori moves/resizes the overlay within 200 ms; mailbox, toast, and ledger remain inside game bounds.
- [ ] **PENDING** — Minimizing, switching focus away, and closing Word Factori hide the overlay. Restoring/refocusing shows it again and preserves queued notification order.
- [ ] **PENDING** — Repeat the attachment/click-through check at 100%, 125%, and 150% Windows scaling and after moving between monitors with different scaling.
- [ ] **PENDING** — Repeat at 1920×1080, 2560×1440, and one ultrawide resolution in windowed and borderless modes. Exclusive fullscreen remains unsupported/fallback unless separately verified.
- [ ] **PENDING** — Reduced motion has no slide/fade movement; interface scale, left offset, notification duration, and max-visible settings visibly take effect and remain bounded.

## Failure and cleanup

- [x] **PASS** — Force-closing child PID 1184 left client PID 20828 connected and produced exactly one replacement child, PID 10336, at the next health check.
- [x] **PASS** — Force-closing replacement PID 10336 left client PID 20828 alive with no third child. A later synthetic `Reflection Access` delivery persisted as receive index 4 with location sentinel -1, proving item/ledger work continued after cosmetic disablement. Level regeneration and victory were not re-exercised in this row.
- [ ] **PENDING** — Disconnect/reconnect preserves ledger rows and unread state without duplicate popups or a historical popup storm.
- [ ] **PENDING** — Close the Word Factori Client normally: the owned child exits, its hotkey is unregistered, original Win32 extended styles/window procedure are restored, and no overlay process/window remains.

Task 7 may begin only after the controller records PASS evidence for the hard process/runtime gate and the primary attachment, font, click-through, focus, resize, crash/restart, and shutdown rows. Any failure must include the exact launcher/client log excerpt and reproduction steps.

## Additional observed evidence

- Frozen namespaced APWorld loading initially failed on an absolute intra-package
  import. The corrected build loads without a world-import traceback and is covered
  by `test_apworld_namespace.py`.
- A two-player local room recorded received, self, and sent rows. Self items appeared
  once through their authoritative receive index. Sent `Merger2 Access` retained
  `Complete V` and the second player as its destination.
- Archipelago cheat/start-inventory deliveries use negative location sentinels. The
  initial run logged `ValueError: location_id must be a non-negative integer`; the
  corrected build persisted and rendered-protocol-validated the signed sentinel.
- Two pre-fallback F8 injections into the focused game produced no durable open
  action. A focus-gated `GetAsyncKeyState` fallback was then added for occupied F8
  registrations and installed in the hash above, but the final injection retest was
  interrupted by active user input and a minimized game window. The F8/Escape row
  therefore remains PENDING rather than being promoted from automated coverage.
