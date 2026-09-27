# Release-candidate polish design

Date: 2026-09-27. Status: approved by Jack; implementation plan requires review.

## Outcome and scope

Jack approved a focused polish pass toward a stable release: explain progression
inside AP Mail, make installation/connection problems recoverable, preserve the
connected regression tests, simplify setup documentation, and define real-game
acceptance gates. This is not another gameplay expansion.

Success means a player can tell what to do next without asking Discord, and a
maintainer can distinguish automated evidence from actual game acceptance.
The release remains a candidate until the gates below pass. This document does
not authorize publication, live installation changes, or game launches.

Preserve the single enhanced integration, shuffled pages, four-of-six progression,
normal and optional progressive machines, optional recipe checks and word orders.
Do not change item/location IDs or canonical names, generation rules, goals,
machine allowances, YAML defaults, or save format. I production remains available.
No new sticker grants, filler options, recipes, speed controls, or layouts.

## Approach and boundaries

Use one read-only Python presentation model for both AP Mail implementations,
then extend their bounded presentation protocols and renderers. The client remains
the authority for room validation, inventory and check reporting. The UI cannot
grant items, mark checks, unlock pages, write saves, or bypass patch validation.

A command-only explanation would avoid UI work but would not meet the approved
in-game clarity goal. Independent native/Python rule implementations would create
unnecessary divergence. Shared presentation derived from the existing rules is
the selected approach; neither renderer implements recipe or progression logic.

Keep this as three independently verifiable implementation slices: shared
progress/recovery presentation; Windows/Linux UI and protocol integration; then
connected CI and release documentation. Avoid unrelated client refactoring.

Existing integration points include `client.py`, `requirements.py`,
`quantity_logic.py`, `quantities.py`, `save.py`, the `overlay_*` modules,
`native_mail_adapter.py`, `native_mail_protocol.py`, and `tools/native_mail_*.gml`.
Extract the presentation calculations into a small dedicated module instead of
adding another large block of logic to either renderer.

## Progress view

Add a **Progress** tab alongside Items, Chat and Type-a-Word on both platforms.
Retain Linux's Status view and provide equivalent readable health/recovery
information on Windows. Tabs wrap into two rows when necessary rather than
shrinking labels below the existing readable text size. Use the established
panel colors, typography, scrolling, focus behavior and left-side notifications.
Do not add new popups for ordinary missing requirements.

Progress lists the room's campaign in actual shuffled page/slot order, with
one-based page labels and six rows per full page. Each row shows target, check
type, completion status, page access and machine requirements. Campaign labs are
labelled **Campaign lab**; they are not described as recipe discoveries. Keep
their canonical AP check names available for tracker/log matching.

Completion labels are **Completed** only for server-confirmed checks, **Sending**
for queued checks, and **Not completed** otherwise. Local completion and server
confirmation are separate facts: a server-side cheat must not imply that the
native save completed a level or unlocked its next page.

Page access is derived from the latest validated, room-bound active save, using
the existing page chain and completion threshold. Display **Unlocked in save**,
**Locked: finish N more on page P**, or **Save progress unavailable**. If an
earlier page blocks the chain, identify that earliest blocking page rather than
directing the player to an inaccessible page. Do not count recipe or word-order
checks toward campaign pages. Page one has no preceding-page completion gate.
These labels describe the last observed save, not direct observation of a button.

Machine details reuse existing per-location requirement alternatives and quantity
budgets, including lab/challenge restrictions. Show **Machines ready** when at
least one verified route is affordable. Otherwise show minimal alternatives,
such as **Need Rotation** or **Need 1 more Bender upgrade**. Retain the progressive
1/2/3/4/unlimited semantics; never treat unlimited as a negative allowance.
Present alternative routes as alternatives, not a combined mandatory shopping
list. If there is no verified route, say so; never label that case ready.

Keep machine readiness separate from page access. Explain in brief help text that
Universal Tracker describes logical reachability, whereas page access here uses
recorded local completions. Do not alter tracker rules in this polish pass.

Type-a-Word keeps its chosen-target and completion view, and gains machine
requirement text from the same presentation helpers. Do not add all 187 recipe
rows to Progress; explain recipe discoveries in help/README instead.

## Freshness, correctness and performance

Cache immutable campaign requirements by validated room contract. Recompute
presentation only when inventory, checks, room identity, relevant validated save
observations, or health status change. Consume ordinary scan results; rendering
must not read saves, hash game binaries, perform recipe searches, or bind a save.

Associate cached save observations with room generation, campaign and save ID.
Invalidate them on a room/save change or failed scan. Unknown is not locked or
unlocked. Disconnects visibly mark retained same-room information as last known;
fresh sessions and different rooms must not inherit prior targets or readiness.
Reconnect must refresh from validated data before showing current readiness.

The new shared fields have explicit types, length limits and enumerated statuses.
Campaign rows are bounded at 40; word orders retain the existing 20-row limit.
Native snapshots retain the 256 KiB ceiling. Preserve progression rows when
trimming optional history to fit. Bound requirement text and offer a concise
summary when alternative routes exceed the available space.

Version changed presentation protocols explicitly. Old/new renderer mismatches
show an update instruction and keep the regular client available; they must not
crash the game or accept malformed data. Do not weaken current room identities,
strict schema validation, input isolation, stale transport checks or size limits.
Regenerate native patch/hash artifacts through existing verified tooling when
the native UI changes; require matching installer assets, not an APWorld-only
update. Ship no proprietary game binary in the distribution.

## Recovery messages

Centralize short player-facing messages around existing failure categories:

| Condition | Player-facing action |
| --- | --- |
| Disconnected/reconnecting | Keep the client open; reconnect to the same room. State that live updates are unavailable. |
| Authentication rejected | Check room address, slot name and password in the regular client. Never display credentials. |
| Missing/outdated patch or receipt | Close the game and rerun the matching Windows or Linux installer. |
| Unsupported game build | Stop installation; use a supported build or report the build identifier privately. Do not promise that rerunning fixes it. |
| Incompatible room/campaign | Install the release used to generate that room, or ask the host which release it requires. |
| Wrong/unbound save or mod | Select the AP mod and this room's save; a new room requires a fresh empty slot. Preserve existing saves. |
| Missing native acknowledgment/stale Mail | Keep the client running, check the AP mod and matching patch, then reconnect/reopen as appropriate. |
| Malformed save/journal | Explain which checks are paused; preserve files and offer the regular client's diagnostic details. |

Show one primary blocker and its next step; retain detailed diagnostics in the
regular client. Never echo personal paths, passwords, raw save contents or
tracebacks into the in-game panel. Deduplicate unchanged warnings. Distinguish
connection health from bridge/patch health: a connected server is not proof that
the game integration is ready. Do not recommend restarting for each item receipt.
Never recommend deleting saves or automatically repair/delete game files.

## Automated verification

Bring the existing local connected runner, its tests and developer guide under
version control without rewriting them unnecessarily. Add dedicated Windows and
Ubuntu CI jobs using official AP 0.6.7 pinned to its verified tag commit and
explicit test dependencies. Do not follow the development branch or install all
optional game worlds. Retain the existing ordinary test/build jobs.

Run both recorded two-player seeds (160929 and 160930) against the newly built
package. Require all 263 checks and both server-confirmed goals per seed, replay
and reconnect assertions, tracker reconstruction comparisons and deliberate
premature-victory rejection. Dependency/setup failures fail the connected job;
missing dependencies must not silently turn a required test into a skip.
Use loopback only, bounded timeouts and no GUI/public room/secrets. Retain synthetic
test reports as CI artifacts even on failure; those artifacts must contain no
real player data or credentials and may be publicly accessible.

Add tests for page thresholds and chained locked pages; server-confirmed but
locally unfinished levels; normal/progressive alternative routes; challenge
restrictions; absent/malformed/stale saves; disconnect/reconnect and room switches;
protocol bounds/version mismatch; Windows/Linux presentation parity; recovery
copy; and no changes to item delivery, check reporting or I availability.

Re-run native input isolation and UI assertions after adding tabs. Cover first
click, Chat-to-other-tab transitions, held keys, scrolling, focus loss, room
changes and long text. Verify rendering does not trigger expensive logic or disk
reads every frame. Automated coverage does not substitute for the live gates.

## Documentation and stable-release gates

Rewrite the README opening as a short Windows/Linux quick-start with matching
download/installer/client steps and a troubleshooting section. Explain campaign
completion, recipe discovery and chosen word orders separately. Provide two
validated YAML examples: straightforward normal-machine play and an optional
progressive/recipe/word-order setup. No new YAML option or default is introduced.
Keep the Akamarus credit and full approved AI-assistance disclosure.

Create an acceptance record with package hash, date, platform, steps, results and
evidence link for each gate. **Pending**, **Pass**, **Fail**, and **Unsupported**
are distinct; unsupported features cannot be counted as passes.

1. Clean install, upgrade from 1.6.0, restore/uninstall on real Windows and a real
   supported Linux/Proton setup, preserving saves and backups.
2. Complete connected gameplay through victory on both platforms, jointly
   covering normal/progressive machines, recipes, chosen words, remote delivery,
   reconnect, tracker comparison and AP Mail Items/Chat/words/Progress/status.
   Confirm machine upgrades apply without per-item reloads.
3. Password-protected room connection and client/server restart/reconnect
   behavior without lost or duplicate progression.
4. Supported windowed/borderless UI at 100%, 125% and 150% Windows scaling;
   record the tested Linux compositor and Proton version. No click/key leakage,
   unreadable tabs or clipping. Exclusive fullscreen remains unsupported;
   untested ultrawide, mixed-DPI, Flatpak or compositor variants stay explicitly
   unverified rather than advertised as tested.
5. At least a 60-minute large-factory session on each platform: record an unchanged
   factory's machine count/speed, game/client memory and FPS or frame time after
   warm-up and at 15-minute intervals. Exercise Mail and item updates during the
   session, then repeat measurements at the same idle/active states. Investigate
   a continuing upward memory trend or sustained performance deterioration;
   do not certify a memory-leak fix from bounded array tests alone.
6. Full build/test/integrity verification and connected CI pass for the exact
   candidate package. No unresolved crashes, save-loss risks, progression blocks,
   duplicated item effects or confirmed logic errors.

Use a concise changelog separating fixes, presentation changes, installation
requirements and remaining limitations. Do not change status to stable until
the required evidence exists and Jack approves publication. If a gate cannot be
tested, leave it pending and retain candidate status instead of inventing evidence.

## Review and handoff

This specification preserves the approved scope and introduces no gameplay rule
change. Implementation planning follows written-spec approval; execution remains
inline as previously selected. Publication and any live-game session are separate
steps, not side effects of writing the plan or running headless checks.
