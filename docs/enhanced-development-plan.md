# Enhanced campaign implementation — 9 September 2026

Approved continuation, implemented inline on the nonlinear branch.

1. Add an explicitly opted-in enhanced room contract. Shuffle first-page
   membership and positions: I/C plus two early-solvable starter levels, plus
   two deferrable non-challenge targets. Preserve balanced later pages and
   stable check IDs. All six buttons independent; four completions advance.
2. Publish room/layout-bound atomic machine snapshots. Native factory entry
   reads the newest valid snapshot without reselecting a save. Preserve
   challenge caps and route restrictions; ignore stale or wrong-room data.
3. Provide a reversible exact-original-hash development installer. Never
   distribute original/transformed game code or game binaries. Keep the
   supported installation and existing saves untouched.
4. Verify unit tests, actual AP generation, native compilation/reopening,
   packaging, and isolated native behavior where the environment permits.
   Report live acceptance separately from automated checks.

Enhanced mode remains opt-in until live acceptance. Supported mode retains
the game's six sequential tutorials and its reload requirement.
