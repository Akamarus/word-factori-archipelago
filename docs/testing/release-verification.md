# Release Verification Record — 1.2.0

Date: 2026-08-23  
Platform: Windows 10.0.19045  
Archipelago: 0.6.7 frozen runtime, Python 3.13.11

## Automated result

- 260 unit/integration tests passed.
- The APWorld and release ZIP passed source/archive parity checks.
- The verifier confirmed 30- and 40-location curated set manifests, JSON index
  integrity, deterministic recipe requirements, headless imports, and exclusion
  of proprietary binaries, recipes, fonts, saves, credentials, and session data.
- Building twice after deliberately changing the APWorld file timestamp produced
  identical archive bytes.

## Frozen generation result

The installed `ArchipelagoGenerate.exe` loaded `Word Factori v1.2.0` from the
release APWorld and generated seed `120240823` with both shipped fixtures:

- player 1: `discovery_labs` (40 locations);
- player 2: `core_campaign` (30 locations).

The generator created 70 items, calculated reachability and progression
balancing, produced the playthrough, and wrote the final room archive without a
Word Factori warning or error. Warnings shown for unrelated installed APWorlds
were outside this project.

## Frozen client and game result

- The installed APWorld launched through Archipelago 0.6.7, connected by an
  `archipelago://` URI, bound an empty Word Factori mod slot, and reconciled an
  authoritative received item.
- The child renderer used Archipelago's bundled Kivy runtime; no extra service,
  runtime download, proprietary font, or game binary entered the package.
- At 2560×1440 and 125% Windows scaling, the overlay attached to the windowed
  game. The mailbox, Items panel, Chat panel, and `/wf_status` response rendered
  over Word Factori. Native hit-map inspection showed overlay controls inside
  the rounded regions and the game window outside them.
- A minimized-start run kept the parent and child alive, then attached after
  restore. Closing the parent removed the owned child. An intentional renderer
  failure left the parent connected and restarted the cosmetic child once.
- Reconnect retained the authoritative item once, with no duplicate durable row
  or unread replay.

## Release-label decision

Version 1.2.0 is accepted as a **release-ready experimental public beta**. Core
world logic, packaging, installer behavior, game-save reconciliation, victory,
frozen-client startup, and the primary live Windows path pass. It is not labeled
an official or upstream release because password-room interaction and the full
100%/150% DPI, ultrawide, and mixed-monitor matrix remain open. Exclusive
fullscreen is intentionally unsupported.
