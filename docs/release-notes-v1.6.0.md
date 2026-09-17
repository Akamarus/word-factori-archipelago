# v1.6.0 — AP Mail and tester feedback follow-up

**Tester prerelease, not a stable release.** Download `word-factori-archipelago-1.6.0.zip`,
not GitHub's automatic source-code archive. The same player ZIP supports Windows
and experimental Linux/Proton setup.

## What changed

- **AP Mail → Type-a-Word** shows your room's selected words and their completion
  status. Targets also appear on connection, in `/wf_words`, and in the spoiler.
- **Experimental Linux/Proton in-game AP Mail:** Items, Chat, Type-a-Word, Status,
  received/sent filters, Older/Latest history, unread status and blue left-side
  popups. Open with AP MAIL or F8. No additional service or installer is needed.
  Connect and enter credentials in the regular native client; keep it running.
- Native Mail isolates its input from the factory and uses a bounded, room-bound
  channel with duplicate suppression. Production and checks continue independently.
  Windows keeps its existing overlay.
- Fixed the reproduced APWorld initialization rejection on Archipelago 0.6.8
  source. Packaged generation was tested from unrelated working directories,
  including a two-player normal/progressive room. Full 0.6.8 client testing is pending.
- Reduced repeated whole-factory scans in progressive simulation to one audit per
  tick. Placement, completion and out-of-tick checks still validate independently.
  This addresses measured overhead; it is not a claim that a memory leak was fixed.
- Added regressions for the reported recipe inventories and tracker reconstruction.
  Native constructions verified the reported S/B/H routes within their budgets;
  J2→S remains out of logic at the reported inventory. No unsupported logic
  relaxation or extra symbol-recipe locations were introduced.
- Updated installer receipts, verified native patch, upgrade/restore coverage,
  README, Linux instructions and tutorial. Full details are in `CHANGELOG.md`.

## Updating

1. Close Word Factori and Archipelago; extract the whole player ZIP.
2. Rerun **Install Word Factori Archipelago.cmd** on Windows, or
   `bash "Install Word Factori Archipelago.sh"` on Linux.
3. Restart Archipelago and update the tracker-side APWorld as well.
4. For candidate testing, use a new room and fresh empty mod save. Preserve old
   saves and `data.wf-ap-original.win`.

Replacing only the APWorld does **not** apply the native changes. No YAML defaults,
check IDs or room-layout contracts change in this release. Existing recipe checks,
optional word orders and optional progressive machines keep the same settings.

## Testing status and limitations

Automated tests and isolated Windows native-runner checks cover the bridge, UI
input, JSON interoperability, one-message/one-acknowledgment delivery, package
integrity and installer safety. They do **not** establish a complete connected
playthrough or real Linux/Proton Mail behavior. Proton/X11/Wayland, fullscreen,
Flatpak and sustained large-factory testing remain community-test priorities.
Use the regular client if Mail is unavailable; do not post passwords or personal
setup paths in public feedback.

Native Linux Mail supports plain chat and `/help`, `/wf_status`, `/wf_words`;
other commands and initial connection settings stay in the regular client.
Long display text is shortened; unsupported font glyphs use `?`, with `[KEY]`
and `[DOOR]` labels. Recipe filler percentage, max-speed preference, actual
sticker awards, symbol-recipe checks and broader naming/log polish are deferred.
