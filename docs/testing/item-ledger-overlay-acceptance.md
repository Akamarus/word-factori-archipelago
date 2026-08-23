# Item-Ledger Overlay Acceptance Record

Status: **PARTIAL — experimental prototype gate remains closed**

Test date: 2026-08-23  
Platform: Windows 10.0.19045  
Archipelago: 0.6.7 frozen launcher  
Word Factori: Steam build 12616577  
Source checkpoint: `69e0fb4`  
APWorld SHA-256: `dd9c4271789011aa591b7fd57918594a0483f4efe3f5697ee680db1282368309`  
Packaging-checkpoint release ZIP SHA-256, before this evidence file was added: `63d3d95218f37a453accae4c59f6738775da87791c8d29655af62f7c67529cb5`

The Windows desktop capture provider failed for both GameMaker and Kivy with `SetIsBorderRequired ... 0x80004002`. A fresh 2026-08-23 retry against the Archipelago Launcher reproduced `SetIsBorderRequired failed: No such interface supported (0x80004002)`; accessibility exposed only the top-level window and title-bar controls. Visual, geometry, and pointer claims are therefore left pending unless directly observed through a separate reliable channel. Automated tests are supporting evidence only and never promote a live row by themselves.

## Runtime and security boundary

| Scenario | Result | Evidence |
|---|---|---|
| Frozen launcher starts one client and one renderer child | PASS | Repeated frozen launches produced one parent and one later overlay child. |
| Renderer uses Archipelago's bundled Kivy | PASS | Kivy 2.3.1 imported from the Archipelago 0.6.7 frozen runtime; no additional runtime or service was installed. |
| Renderer receives visual data only | PASS | Protocol and frozen-namespace tests constrain the child to validated visual snapshots/actions; network context, sockets, addresses, and passwords are not part of the item-only payload. |
| Installed game font and fallback font | PENDING | Font discovery/fallback is automated, but visible font rendering could not be captured reliably. |
| Proprietary files excluded from distribution | PASS | Builder and verifier reject `data.win`, `recipes.data`, save data, Fredoka/Letters fonts, and `.superpowers` session files. |

## Items and reconciliation

| Scenario | Result | Evidence |
|---|---|---|
| Initial authoritative sync is silent | PASS | Two-player room seeded history without durable unread notifications. |
| New received item creates one ledger event | PASS | Live cheat delivery persisted once with its authoritative receive index. Visual popup appearance remains covered separately below. |
| Replayed receive creates no duplicate | PASS | Disconnect/reconnect retained one `Rotation Access` row and zero unread keys. |
| Self item appears once | PASS | Self delivery reconciled through its authoritative receive index without a duplicate sent row. |
| Connected sent item appears once | PASS | `Merger2 Access` retained its checked location and destination in the live two-player ledger. |
| Missed sent item is backfilled as earlier | PASS | Checked-location scouting backfilled historical sends silently in the live room. |
| Reconnect preserves history and unread state | PASS | Installed-copy reconnect kept the authoritative row and read state without durable replay. Visual no-popup-storm remains pending below. |
| Switching rooms replaces ledger identity | PASS | Automated epoch/identity coverage verifies replacement, and no state is merged across seed/team/slot identity. |
| Negative synthetic location sentinel | PASS | Cheat/start-inventory receive persisted and protocol-validated location `-1` after the live defect was corrected. |

## Display, input, and geometry matrix

| Scenario | Result | Evidence |
|---|---|---|
| Game absent, then windowed attachment within one second | PENDING | Capture provider could not show either window. |
| Blue received popup on the left | PENDING | Durable event was observed; visual placement was not. |
| Sent and self wording | PENDING | Presentation values are tested; live text was not visually verified. |
| Mailbox unread badge and styled ledger | PENDING | Live pixels were unavailable. |
| Interactive controls and click-through factory grid | PENDING | Native hit-test coverage passes; live pointer behavior was not observed. |
| Focused-game F8 opens and marks read | PASS | Live F8 changed one durable unread key to zero through the child channel while Word Factori remained focused. |
| Escape closes without trapping focus | PASS | Windows accessibility still reported Word Factori focused after live F8 and Escape. |
| Move and resize tracking | PENDING | Live geometry could not be observed. |
| Minimize, restore, focus loss, and game close | PENDING | Live visibility changes could not be observed. |
| 1920×1080 windowed | PENDING | Resolution-specific live result not recorded. |
| 1920×1080 borderless | PENDING | Resolution-specific live result not recorded. |
| 2560×1440 windowed | PENDING | Resolution-specific live result not recorded. |
| 2560×1440 borderless | PENDING | Resolution-specific live result not recorded. |
| Ultrawide windowed | PENDING | No ultrawide monitor result recorded. |
| Ultrawide borderless | PENDING | No ultrawide monitor result recorded. |
| 100% Windows scaling | PENDING | Scaling-specific live result not recorded. |
| 125% Windows scaling | PENDING | Scaling-specific live result not recorded. |
| 150% Windows scaling | PENDING | Scaling-specific live result not recorded. |
| Movement between monitors with different scaling | PENDING | Multi-monitor DPI transition not recorded. |
| Long player, item, game, and location names | PENDING | Bounded presentation is tested; live clipping/wrapping is not. |
| Reduced motion and cosmetic preferences | PENDING | Persistence/ranges are tested; live visual effect is not. |
| Exclusive fullscreen | FALLBACK | Unsupported boundary: use windowed/borderless mode or the regular client. |

## Failure isolation and cleanup

| Scenario | Result | Evidence |
|---|---|---|
| First renderer crash restarts once | PASS | Closing child PID 1184 kept client PID 20828 connected and created replacement child PID 10336. |
| Second renderer crash disables cosmetic child | PASS | Closing replacement PID 10336 created no third child; a later receive still persisted. |
| Checks and unlock rendering survive renderer failure | PASS | Parent-side bridge is independent and automated lifecycle tests pass; the live post-failure receive confirmed parent operation. |
| Normal client shutdown removes child and restores hooks | PENDING | Normal-shutdown process/window residue was not directly inspected live. |
| Renderer unavailable falls back to regular client | PASS | Failure-isolation logs and lifecycle tests keep the regular client active without blocking item reconciliation. |

## Automated release evidence

`python -m unittest discover -s tests -v` completed 211 tests with zero failures. `tools/build_release.py`, `tools/verify_release.py`, and `git diff --check` completed successfully. The verifier confirmed source/archive parity, campaign JSON/index integrity, fresh locally derived recipe requirements, and proprietary-data exclusions.

## Decision

This build remains an **experimental prototype**. Its state, idempotency, process isolation, frozen-runtime loading, F8/Escape behavior, installer, and release hygiene are accepted. The official visual gate remains open until attachment, font, pointer click-through, resize/focus/minimize, DPI/resolution, multi-monitor, and clean-shutdown rows receive reliable live evidence. The full in-game client may continue in development, but no official-release claim may rely on this partial matrix.
