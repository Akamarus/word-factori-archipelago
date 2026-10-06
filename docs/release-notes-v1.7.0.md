# v1.7.0 — Progress, recovery and generation fixes

**Tester prerelease, not a stable release.** Download
`word-factori-archipelago-1.7.0.zip`, not GitHub's automatic source-code archive.
The same player ZIP supports Windows and experimental Linux/Proton setup.

## Archipelago 0.6.8 compatibility update — October 6

**The existing v1.7.0 download works with final Archipelago 0.6.8.**
Packaged generation, actual Universal Tracker sphere comparisons, mixed-game
generation and connected server/client tests passed. No gameplay fix or
replacement download is required, and 0.6.7 remains supported.

Already on Word Factori v1.7.0? Upgrading AP alone does not require a new
Word Factori room/save, YAML changes or repatching the game. If you install AP
in a different folder, install the same v1.7.0 APWorld there. The fresh-room
instructions below apply to updating the Word Factori integration from an
older release, not merely upgrading AP.

The published assets and tag have not been replaced. This remains a tester
prerelease: automated tests simulate game completions and do not constitute
a new live Windows/Proton playthrough. See the
[compatibility test record](https://github.com/Akamarus/word-factori-archipelago/blob/main/docs/testing/archipelago-068-20261006.md).

## What changed

- **AP Mail Progress and Status on both platforms.** See your room's shuffled
  campaign order, server-confirmed checks, local page locks and missing-machine
  routes. An unlocked page does not mean every puzzle is currently solvable.
- **Clearer Type-a-Word requirements**, including alternative routes and
  progressive quantities. Campaign explanations respect restricted labs and
  challenge limits. I sources remain available.
- **Safer recovery guidance** for connection, patch, campaign/save and journal
  problems. Offline/last-known/unavailable information is labeled explicitly;
  presentation failures cannot award checks or interrupt item reconciliation.
- **Mail layout and protocol polish:** tabs wrap on narrow panels, Progress text
  scrolls, and both displays retain bounded messages, input isolation and the
  regular-client fallback. Windows presentation protocol is now 4; native Mail
  protocol is 2. The matching native delta is included.
- **Universal Tracker saved-room fix:** tuple-based saved arrays now reconstruct
  correctly, including selected words. Corrupt layouts and mismatched digests
  are still rejected.
- **Progressive generation fix:** reverse placement preserves the early campaign
  checks needed by the verified upgrade path. No items are forcibly preplaced.
- **Faster normal-machine generation/Tracker rules:** reject unavailable machines
  first, stop when a page threshold is satisfied, and avoid evaluating the same
  predecessor repeatedly during one reachability query. Results are discarded
  between queries and on exceptions. This is not an in-game FPS claim.
- **Type-a-Word option errors are classified correctly.** Invalid or empty lists
  still produce useful errors; test fuzzing now has a valid 20-target meta list
  without disabling randomized word checks.
- **More regression coverage:** packaged generation, actual Tracker sphere
  comparisons, mixed Kingdom Hearts rooms, required accessibility, connected
  duplicate/reconnect handling and deliberate premature-victory rejection.
  Windows/Ubuntu connected CI now covers pinned official Archipelago 0.6.7 and 0.6.8.

## YAML and progression

No new YAML options, changed defaults, check IDs, item IDs, machine tiers or
four-of-six page-unlock rules. Existing `recipe_checks`, `type_a_word_checks`,
`type_a_word_words`, `type_a_word_count` and `progressive_machines` remain supported.
The updated progressive example enables recipes and three selected word orders;
that example does not change the defaults. The APTests meta YAML is a testing
configuration, not a replacement player YAML.

## Updating

1. Close Word Factori and Archipelago; extract the complete new player ZIP.
2. Rerun **Install Word Factori Archipelago.cmd** on Windows, or
   `bash "Install Word Factori Archipelago.sh"` on Linux. Do not use Wine or sudo
   for the Linux installer; select the native AP `worlds/` or `custom_worlds/` folder.
3. Restart Archipelago and update the tracker-side Word Factori APWorld too.
4. Generate a new room and use a fresh empty mod save. Preserve existing saves
   and `data.wf-ap-original.win`; do not delete them to update.

Replacing only the APWorld does **not** apply the Mail/native changes. Supported
1.6.0 and earlier installations upgrade through the verified original backup.
This is a one-time update restart, not a return to per-item reloads. In normal
mode, return to Levels and enter a factory for newly received machines;
progressive allowances update during play.

## Verification and remaining limits

The pre-version-bump candidate passed the full APTests browser run: **205 unit
tests and 14,500 generations across all 11 categories**, with **zero failures,
ignored cases, raw timeouts or worker restarts**, in 11 minutes 34 seconds.
Independent 74-case Tracker and 74-case mixed-world matrices passed. The local
suite ran 808 tests with eight expected opt-in skips, and a separate 16-test
real-AP/connected group passed. See `docs/testing/aptests-regressions-20260929.md`
for exact candidate hashes and reproducible commands.

Automated generation and simulated game-boundary tests are not complete live
playthroughs. Windows/Linux install lifecycle, real connected playthroughs,
password/reconnect behavior, supported display modes and sustained large-factory
performance remain release gates. Exclusive fullscreen is unsupported. The
regular client remains the fallback when AP Mail is unavailable.

No proprietary game binary, font, player save or credentials are distributed.
