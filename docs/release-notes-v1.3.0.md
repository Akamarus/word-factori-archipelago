# Word Factori Archipelago 1.3.0 — Nonlinear Page Progression

Version 1.3.0 makes each newly generated room's page layout part of its authoritative seed data. The default `shuffled_pages` option produces deterministic seed-specific pages; `fixed_pages` preserves the bundled canonical order.

## Player-facing changes

- A full page contains six levels, and completing any four opens the next page. The other two checks can be deferred and revisited later.
- The 30-level Core Campaign and 40-level Discovery Labs set both support shuffled pages.
- A shuffled level keeps its canonical stable key and Archipelago location ID even though its native Word Factori save slot moves.
- The first shuffled page is exactly the six canonical Starter Workshop levels, with shuffled slot order; later page membership remains seed-specific. The world requests one local-early Merger2 Access and one local-early Rotation Access from Archipelago fill, preventing the early frontier from collapsing to a single choice. Full pages preserve machine-profile diversity; one later Core Campaign page may contain four Rotation-unavoidable checks, while the other machine caps and all remaining page caps stay at three.
- Full layout identity is validated before the client rewrites the generated campaign or reports checks. Reconnects remain idempotent.

## Room compatibility

New rooms require the 1.3.0 APWorld and client to use shuffled pages and four-of-six logic. Existing 1.2.x rooms keep the canonical order and the server logic generated into those rooms; installing 1.3.0 does not rewrite or upgrade an existing room's server logic. The 1.3.0 client continues to recognize the legacy room format.

## Data safety

The integration continues to read Word Factori save data without modifying it. It writes only the integration's supported `levels.json` and `archipelago_campaign.json` files plus its idempotency sidecar. It does not patch `data.win` or redistribute proprietary recipe data.

## Verification status

Automated generation, mapping, compatibility, reconnect, goal, packaging, parity, and sensitive-data checks are included. Live acceptance of the new shuffled-page and four-of-six behavior is not claimed here; those rows remain `Pending live test` in `docs/testing/nonlinear-progression-acceptance.md` until observed.
