# Release Verification Record — 1.2.0

Date: 2026-08-23  
Platform: Windows 10.0.19045  
Archipelago: 0.6.7 frozen runtime, Python 3.13.11

## Automated result

- 246 unit/integration tests passed.
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

## Release-label decision

The distributable remains **experimental**. Code, generation, install, and
archive gates pass, but the full live visual/input matrix in
`full-ingame-client-acceptance.md` still contains pending rows because the
Windows capture provider cannot inspect the GameMaker/Kivy windows on this
machine. No pending row is promoted by inference.

