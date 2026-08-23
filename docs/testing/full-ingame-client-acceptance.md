# Full In-Game Client Acceptance

Status: **PRELIMINARY — automated renderer contract passes; live matrix remains open**

This record covers the Word Factori-styled Archipelago client rendered over the
game. It is not an official-release sign-off. The release label must remain
experimental until every live row is exercised in the frozen Archipelago
runtime and recorded with evidence.

## Automated evidence

Run on 2026-08-23 with Python 3.13:

```text
python -m unittest discover -s tests -v
Ran 238 tests in 3.968s
OK
```

The automated suite currently verifies:

- strict versioned intents for connect, disconnect, chat/command text, and password submission;
- parent-only networking and rejection of credentials in parent-to-renderer snapshots;
- Items/Chat/connect/password view and keyboard-focus contracts;
- native `NOACTIVATE` removal only while an input view is active;
- restoration of passive style and Word Factori focus on intentional close;
- no focus steal when the player alt-tabs away;
- bounded message history, Unicode presentation, actionable notices, and item ledger behavior;
- renderer isolation, malformed-pipe containment, reconnect reconciliation, and fallback behavior.

## Live acceptance matrix

| Area | Required observation | Status |
|---|---|---|
| Manual connect | Address, slot, and optional masked password connect from the overlay | PENDING |
| URI connect | `archipelago://` launch reaches the same connected state | PENDING |
| Authentication | Password prompt is masked, submits once, and clears immediately | PENDING |
| Items/Chat | Tabs switch cleanly and preserve the Word Factori visual language | PENDING |
| Text input | Enter submits; Shift+Enter adds a line; Escape closes and returns focus | PENDING |
| Commands | `!hint`, `!remaining`, `/wf_status`, `/received`, and invalid commands render correctly | PENDING |
| Chat | Local and remote chat render once with readable attribution | PENDING |
| Connection states | Connecting, authenticating, connected, reconnecting, error, disconnect | PENDING |
| Invalid inputs | Bad address, slot, password, game, and version show safe actionable notices | PENDING |
| Focus | F8, outside click, Escape, alt-tab, minimize, and restore do not trap input | PENDING |
| Display | Windowed, borderless, scaling, ultrawide, and multi-monitor placement | PENDING |
| Resilience | Renderer crash falls back to regular client without affecting AP state | PENDING |
| Complete play | A seed can be completed without exposing the generic client | PENDING |

## Current evidence limitation

The existing live capture path cannot inspect the Archipelago launcher window on
this machine (`No such interface supported`, Windows error `0x80004002`). This
prevents trustworthy automated screenshots or clicks in the frozen runtime. It
does not change the automated result, but it keeps every visual/live row open.
No row is treated as passed by inference.

