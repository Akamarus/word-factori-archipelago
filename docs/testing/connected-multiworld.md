# Connected multiworld acceptance (developer test)

This opt-in test uses **official Archipelago 0.6.7 or 0.6.8**, a packaged Word Factori
APWorld, a real loopback WebSocket server, and two real Word Factori client
contexts. No public room, installed game, GUI, credentials or player saves are
used. It is not an automated in-game playthrough.

## What it verifies

CI requires this coverage on Windows and Ubuntu for both AP 0.6.7 commit
`debe4cf035c7c15efe6fb95f72343af0d420c68c` and AP 0.6.8 commit
`54803be064fc7e80c4628777ed0b46a9390f255f`. The job verifies source availability,
builds the APWorld, runs the successful-room and premature-victory tests, then
runs seeds 160929 and 160930. Synthetic reports/logs are retained for seven days.
Dependency or setup failures fail the job; they do not count as skipped acceptance.
Install developer dependencies with `python -m pip install -r tools/requirements-connected.txt`.
New candidate evidence belongs in the release-candidate acceptance record below;
the historical record at the end is not evidence for a changed package.

- Generates a fresh two-player room with full accessibility:
  - Normal machines, 30 campaign factories, three selected word orders,
    and a 25-campaign-completion goal: **33 checks**.
  - Progressive machines, 40 campaign/lab factories, 187 recipe discoveries,
    three selected word orders, and the final-factory goal: **230 checks**.
- Loads the generated multidata into the real AP server. Cheats, collect and
  release are disabled. The listener binds only to `127.0.0.1` on a free port.
- Reads the actual connected clients' delivered inventory to advance through
  reachable checks. It does not inject progression items, read future placements
  to choose checks, or ask the server to release a slot.
- Passes synthetic completion journals through the production client's ordinary
  save scanning, binding, pending-check and reconciliation paths.
- Restarts a client after recording completions offline and verifies its saved
  room/save binding and catch-up behavior.
- Disconnects and reconnects the same client instance after progression, then
  verifies item reconciliation and preservation of its room/save binding.
- Repeats checks over the real connection and requests full item replays using
  `Sync`. Waits for real async reconciliation, then verifies that inventory,
  applied item indices and published machine allowances have not increased.
- Reconstructs each player's world through the same slot-data entry point used
  by Universal Tracker, under a different RNG seed. Compares its reachable
  location IDs with the generated world's rules at each progression step.
- Enforces a test-side four-of-six physical-page model when selecting campaign
  completions. Records how often this prevents entering a later page.
- Rejects premature victory and requires both server-confirmed goals plus
  **all 263 checks**, including optional checks after victory.
- Fails on timeouts, deadlocks, background task exceptions, bridge errors,
  persistence errors or absent scenario coverage. It produces `report.json`
  and `worker.log`, and closes its client connections and listener automatically.

## What is simulated, and what is not proven

The proprietary game boundary is simulated: harmless installation fixture bytes,
the native room acknowledgment, recipe/word/level completion journals and the
physical-page model. Only the expected binary hashes are substituted inside the
test worker; the actual receipt validator and client state handling still run.
The original game executable and `data.win` are never opened or modified.

Tracker comparison checks **reconstruction consistency**, not independent proof
that every recipe can be built. This does not launch Universal Tracker's UI,
Word Factori, native AP Mail or Proton, measure factory performance, or establish
real gameplay/page-button behavior. Agreement between two uses of the same rules
cannot detect a shared recipe-rule error. Native puzzle tests and human Windows/
Linux playthroughs remain necessary. Server restart/persistence and password
authentication are not covered by this scenario.

## Run it

Use Python 3.12 with the dependencies required by the official AP source
checkout installed in that environment. The runner never downloads dependencies
or upgrades packages. It copies only core Python files and framework directories
from the source, not its settings, installed games/worlds, caches or saves.
The supplied AP source/APWorld are trusted executable code, not untrusted uploads.

Build the current package first, then run from the repository:

```powershell
python tools/build_release.py
python tools/verify_connected_multiworld.py --ap-source "C:/src/Archipelago" --seed 160929 --output "../word-factori-test-runs/seed-160929"
python tools/verify_connected_multiworld.py --ap-source "C:/src/Archipelago" --seed 160930 --output "../word-factori-test-runs/seed-160930"
```

On Linux, use the same CLI with Linux paths. Use the **0.6.7 or 0.6.8 source tag**,
not the development branch. Output must be a **new directory** each time; an
existing destination is refused rather than overwritten. Short temporary game
paths avoid Windows path-length limits and are removed automatically. Reports,
the exact tested APWorld, generated room/spoiler and logs remain in the output
directory. The report includes the seed and APWorld SHA-256.

Optional flags:

- `--apworld PATH`: test a specific existing package instead of the checkout's
  `word_factori.apworld`.
- `--dependency-path PATH`: use an existing isolated dependency directory
  (equivalent to prepending it to the worker's Python import path).
- `--timeout SECONDS`: total worker deadline, including generation; default 180.

Exit code 0 means the complete scenario passed. Any failure returns nonzero;
read `report.json` and `worker.log`. Expected AP warnings about its optional
compiled speedups or intentional client disconnections are not test failures.

## Regression tests for the runner

The regular suite tests output protection, staging isolation, bounded waits and
report completeness. Real networking tests are opt-in to keep the normal suite
independent of an external AP source checkout:

```powershell
$env:WF_AP_SOURCE = "C:/src/Archipelago"
# Optional if dependencies are not installed in this Python environment:
# $env:WF_AP_DEPS = "C:/test-dependencies"
python -m unittest tests.test_connected_multiworld -v
```

This runs both the full successful room and a fault-injection test: a temporary
APWorld copy is deliberately altered to claim victory without completions. The
runner must reject that copy with `premature victory`. Neither the original
package nor production code is changed. Without `WF_AP_SOURCE`, those two tests
are explicitly skipped, not counted as connected-playthrough evidence.

## Recorded local verification — 2026-09-17

Windows, Python 3.12.14, official AP 0.6.7 core, v1.6.0 packaged APWorld.
The APWorld SHA-256 was
`2fb0dda1fda7d648574578477e58d97fed9a6f9db00fa5c72316cc3df33506cb`.

| Seed | Checks | Server goals | Tracker comparisons | Replay rounds | Cross-player deliveries |
| --- | --- | --- | --- | --- | --- |
| 160929 | 263/263 | 2/2 | 20 | 9 | 54 |
| 160930 | 263/263 | 2/2 | 20 | 9 | 52 |

The test-side page model deferred later-page completions 108 and 122 times,
respectively; these counts can include the same location across multiple steps.
The opt-in runner suite passed all seven tests, including the successful real
room and rejection of a deliberately premature-victory client. The complete
repository verification passed 748 tests with four explicit skips (two existing
platform-dependent skips and the two opt-in tests, which were run separately).
Release integrity verification passed; production APWorld and player ZIP hashes
remain identical to the published v1.6.0 artifacts. No gameplay code, installed
game, real save or public release was changed by this work.
