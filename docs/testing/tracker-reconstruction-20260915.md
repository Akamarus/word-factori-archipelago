# Universal Tracker reconstruction fix — 2026-09-15

Status: local source fix; not part of the published 1.4.2 player package.

## Confirmed defect and change

The world randomized its page layout in `generate_early` without providing
Universal Tracker's room-data reconstruction hook. A different tracker seed
could therefore produce a different page membership/order from the server.
The fix implements static `interpret_slot_data`, supports YAML-less tracker
generation, and restores the validated room layout and game-specific options
from `multiworld.re_gen_passthrough` before creating regions and rules.

The implementation follows the [upstream UT reconstruction contract](https://github.com/FarisTheAncient/Archipelago/blob/tracker/worlds/tracker/docs/re-gen-passthrough.md).
Only the current enhanced machine-only room contract is accepted. Incomplete,
tampered or unsupported room data raises an error instead of falling back to a
new shuffle. The normal generation path, location names/IDs, game patch and
save handling are unchanged.

## Automated evidence

- Red: added tracker tests failed with the missing `interpret_slot_data` hook
  before implementation.
- Green: 13 world-layout tests pass, including both level sets and both goals,
  conflicting tracker settings, a different tracker RNG, preserved location
  mappings, campaign-count goal restoration and invalid-data rejection.
- All machine inventory subsets produce the same location reachability in the
  original and reconstructed world for each tested campaign.
- Every later page requires four locations from its own preceding page, not
  four arbitrary locations. Tests include all four-of-six predecessor choices
  and the partial final page in the 40-location campaign.
- Full Windows suite: 477 tests run, 476 passed, one platform-specific skip.
- Package build and release verifier pass (source parity, index/JSON integrity,
  fresh recipe derivation and excluded-data checks). This locally rebuilt
  development package has not been published or installed into the live game.

Commands, using Python from the project root:

```text
python -m unittest discover -s tests -p test_world_layout.py -v
python tools/build_release.py
python -m unittest discover -s tests -q
python tools/verify_release.py
git diff --check
```

## Remaining live acceptance

The tests use lightweight Archipelago API fixtures; they do not establish a
connected UT session or reproduce the tester's specific room.

1. Load the fixed APWorld into a test installation of UT and connect to an
   existing matching 1.4.x room. Check both a YAML-less connection and a
   conflicting local YAML to confirm the room's layout and goal win.
2. Compare first-page targets and later-page membership with the game. Check
   starter machines, a received progression machine, and a reconnect.
3. Complete four factories on one page and confirm the native arrow opens.
   UT may show later checks in logic before those four are actually completed:
   logic represents the ability to solve them, not current save completion.
4. Complete the named C Bending Lab and confirm its check. Producing C in an
   unrelated factory is not the trigger.
5. In a disposable test room, manually send a check and confirm AP acknowledges
   it without changing game-save completion. This does not open native pages.
6. Verify both victory modes. Keep any remaining mismatch open for diagnosis;
   the reconstruction defect alone is not proof that every reported discrepancy
   is resolved.
