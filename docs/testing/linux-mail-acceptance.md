# Native Linux Mail acceptance matrix — 1.6.0 candidate

No Linux host is available for this preparation. Do not turn a Windows scratch
result or Python installer fixture into a Linux gameplay pass.

| Scenario | Windows evidence | Actual Linux/Proton |
|---|---|---|
| File protocol, strict schema and duplicate requests | Python tests + native/Python round trip pass | Pending |
| First click/F8, Chat→Items, no click-through | Isolated input and UI assertions pass | Pending |
| Held key, placement, connection, production while open | Prior full-object scratch/manual checks pass | Pending |
| Resize, focus, windowed/fullscreen | Bounded Windows scratch checks only | X11 and Wayland pending |
| Items, unread persistence, history, Chat, selected targets | Python/native component tests pass | Connected two-player test pending |
| Installer/upgrade/restore, native and Flatpak paths | Synthetic installer tests; CI configured | Real installations pending |
| 1,000 toggles / 100 room epochs | Bounded native arrays pass; not a memory/FPS soak | Sustained session pending |
| Remote delivery, reconnect, victory, Universal Tracker | Automated reconciliation/logic tests | Complete multiworld pending |

## Reproducible private two-player setup

Create two YAML files with different names. Use this first player:

```yaml
name: MailTester
game: Word Factori
Word Factori:
  custom_level_set: discovery_labs
  recipe_checks: true
  progressive_machines: true
  type_a_word_checks: true
  type_a_word_count: 3
  type_a_word_words: ['CAT', 'I=', '(=)']
  goal: campaign_count
  campaign_count: 20
```

Copy it for `MailPartner`, changing the name and setting `progressive_machines:
false`. Generate using the matching candidate APWorld; connect two clients to a
private room, each bound to its own fresh empty save. Keep previous saves/backups.
No test room is hosted or published automatically by these instructions.

On the Linux tester's own setup:

1. Install and verify the package, then launch Steam Proton and select the AP mod.
2. Open every Mail tab; compare chosen targets with `/wf_words` and the spoiler.
3. Exchange remote items and chat. Check received/sent/self filters, popups, unread
   persistence and Older/Latest history. Reconnect without replaying checks/chat.
4. While editing a factory, type and hold letter shortcuts in Chat; dismiss over
   the grid/Play button. Verify no accidental building, deletion or simulation.
5. Test focus loss, resize, windowed/fullscreen on the available compositor.
   Do not claim both X11 and Wayland unless both were actually tested.
6. Complete factories, recipes and selected words; receive progressive upgrades
   while playing. Compare tracker logic and reach the configured victory.
7. Play a sustained large factory, recording elapsed time and whether performance
   degrades. Close everything, restore/uninstall, and confirm saves/backups remain.

Report pass/fail, release version, broad platform/compositor and error category
first. Personal paths, account names, room passwords and full logs are not needed
publicly. Any detailed diagnostic sharing should be voluntary and redacted.
