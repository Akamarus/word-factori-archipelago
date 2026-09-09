# Enhanced r3: first connected playthrough corrections

## Machine refresh: reproduced and corrected

Jack completed C and I and received Merger2 and Rotation. The client runtime
snapshot contained the correct unlocks, but the game retained its initial
machine limits on factory entry.

An isolated runner loaded a copy of that campaign. A separate process then
atomically replaced the runtime JSON while the runner stayed open. The hook
rejected the revision guard: Python's integer epoch token parsed as GameMaker
`int64`, for which `is_real` is false. Native JSON writing had converted the
same value to a floating-point literal, hiding this boundary in earlier tests.

The hook now accepts either native numeric representation, retaining integer,
nonnegative, and monotonic checks. A permanent raw-JSON regression failed
before the fix and passed afterward. The full native harness passed 38 checks
with exit 0. The external-process test then showed Merger2 changing from zero
to unrestricted without reloading the campaign or runner.

Patched SHA-256:
`5a964d5155f8f7acc63fd90bc81882a0559c4586f5de4fd9a0657badd8594194`

## Mail activation: candidate correction

Jack reported that a mail click needed a subsequent outside click, and the
panel did not reliably remain open. The renderer forwarded WM_MOUSEACTIVATE
to SDL even for its passive items window. The game-focus visibility policy
can hide a passive window if that window takes foreground focus.

The hook now explicitly returns MA_NOACTIVATE for passive clicks, preserving
delivery of the mouse event without activation. Keyboard-enabled chat and
connection views continue to use normal activation. The passive-click test
failed before the change; keyboard routing is separately covered.

Reference: [Microsoft WM_MOUSEACTIVATE contract](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-mouseactivate).
The click symptom still requires confirmation on the normal game screen.
The initial two-second-polling hypothesis was rejected: action processing
already uses its own 100 ms loop.

## Installation safety

Keep the same AP room, server save, client state, and game Slot 3. Restore r2
using its matching installer before applying r3. Do not delete game saves or
generate a replacement room to test this hotfix.
