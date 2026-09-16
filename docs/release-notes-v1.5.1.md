# Word Factori Archipelago 1.5.1 — Recipe Loading and Symbol Orders

Tester prerelease for Windows and Linux/Proton. This addresses the three reports received after 1.5.0; it is not a declaration of stable or fully playtested support.

## Fixed: crash when loading saves

The reported `Unable to find instance for object index 6` failure was reproduced in the original game's recipe-loading code without AP hooks or a player save. Reversed duplicate inputs in the online recipe table could make the normalizer stop processing the rest of a machine's recipes. A later refresh encountered an unprocessed string where a recipe structure was expected.

The native patch now skips the already-processed entry and continues. AP sessions additionally reload the verified bundled recipe table and ignore online recipe replacements, keeping the game aligned with Archipelago's logic. Entering AP after receiving a vanilla online update is covered. Vanilla sessions outside AP retain online recipe updates.

This fixes the reproduced recipe-loading path; it does not edit, reset or repair player saves. Full-game Windows and Proton save-loading confirmation is still requested.

## Fixed: Archipelago groups

Item and location groups are now declared on `WordFactoriWorld` before Archipelago registers it. They are not inserted dynamically after initialization or changed by the seed.

- Item groups: `Machines`, `Progressive Machines`, `Stickers`.
- Location groups: `Campaign Levels`, `Recipe Discoveries`, `Word Orders`.
- Optional checks remain absent when their option is disabled. Groups do not add checks or represent shuffled pages.

## Expanded: Type-a-Word symbols

`type_a_word_words` now accepts every verified native target character: **A–Z** plus **`()#%$@+=&0123456789🔑🚪~`**. Both normal-access and progressive-machine logic have updated, native-verified production routes, including the game's rotated-six representation of 9.

ASCII lowercase is still converted to uppercase. Targets remain **2–12 characters**; the list limit remains **200**, and `type_a_word_count` still selects **1–20** orders. Spaces inside targets and unsupported characters are rejected. Quote YAML entries so numbers and punctuation stay text:

```yaml
Word Factori:
  type_a_word_checks: true
  type_a_word_count: 3
  type_a_word_words: ['JACK', 'I=', '(=)', '99', 'A9🔑', '🔑🚪']
```

No new YAML options were added in 1.5.1. The 187 optional letter-recipe checks, stable word-order check IDs, progressive tiers, page progression and victory conditions are unchanged. Symbol order support does not add symbol Recipe Journal checks.

## Install or update

1. Download **word-factori-archipelago-1.5.1.zip** below, not GitHub's automatic source-code archives. The single ZIP supports both platforms.
2. Close Word Factori and Archipelago. Extract into a separate folder and rerun **Install Word Factori Archipelago.cmd** on Windows, or `bash "Install Word Factori Archipelago.sh"` on Linux.
3. Restart Archipelago and update the Word Factori APWorld in Universal Tracker's environment too.
4. Generate a **new room** using matching 1.5.1 components and use a **fresh empty mod save**. Older symbol/quantity contracts are not silently converted. YAML changes cannot retrofit an existing room.
5. Keep existing saves and `data.wf-ap-original.win`. Both installers recognize 1.5.0 and earlier supported native patches and upgrade through the verified original backup. Unknown builds or damaged required backups are refused.

Requires Archipelago **0.6.7** and the installer-verified Word Factori Steam build **12616577**. Linux still uses the regular native AP client; the AP Mail overlay remains Windows-only. README, setup guides, changelog and the word-order YAML example have been updated.

## Verification and requested testing

- **660 automated tests: no failures, two skipped.**
- **Eight isolated native recipe-loading assertions** passed, including repeated normalization and vanilla/AP recipe transitions.
- **70 isolated native production cases** passed, including all 22 symbols and repeated/mixed symbol words.
- The packaged APWorld generated normal and progressive rooms in real Archipelago 0.6.7 with six symbol orders each; YAML exercised all six static groups.
- The native patch compiled and reopened successfully; its distributable delta round-tripped against the verified original. Installer regression tests include 1.5.0 upgrade and restore.

Please test save loading on Windows/Proton and symbol-order completion with the connected client and Universal Tracker. These automated and isolated checks do not replace a complete connected playthrough. Include your version, options, target/check and error message with reports, but redact passwords and personal paths.
