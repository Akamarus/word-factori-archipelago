from __future__ import annotations

import json
import pickle
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

from tools.verify_generation_matrix import (
    MATRIX_CASES,
    GenerationIdentity,
    SphereSummary,
    compare_generation_identities,
    execute_matrix,
    extract_generation_identity,
    parse_progression_playthrough,
    prepare_live_room,
    replay_progression_choices,
    render_player_yaml,
    run_generation,
    validate_progression_choices,
    verify_deterministic_identity,
)


SPOILER = """Archipelago Version 0.6.7  -  Seed: 13000

Playthrough:

0: {
  Bender Access
}
1: {
  CAT — First: Rotation Access
  OWL — Second: Progressive World Access
}
2: {
  DRAGON — Third: Merger2 Access
  CATS — Fourth: Reflection Access
  RAT — Fifth: Merger3 Access
}
3: {
  STAR — Sixth: Progressive World Access
  MOON — Seventh: Merger4 Access
}
4: {
  Victory: Victory
}
"""


class SpoilerParsingTests(unittest.TestCase):
    def test_parses_items_and_locations_by_sphere_before_victory(self):
        result = parse_progression_playthrough(SPOILER)

        self.assertEqual([sphere.number for sphere in result], [0, 1, 2, 3])
        self.assertEqual(result[0].entries[0].location, None)
        self.assertEqual(result[0].entries[0].item, "Bender Access")
        self.assertEqual(result[1].entries[0].location, "CAT — First")
        self.assertEqual(result[1].entries[0].item, "Rotation Access")
        self.assertFalse(any(entry.item == "Victory" for sphere in result for entry in sphere.entries))

    def test_accepts_archipelago_windows_line_endings(self):
        # Splitting only on a literal LF marker rejects real AP 0.6.7 spoilers.
        result = parse_progression_playthrough(SPOILER.replace("\n", "\r\n"))

        self.assertEqual(result[2].entries[2].item, "Merger3 Access")

    def test_rejects_spoilers_without_a_victory_sphere(self):
        # Silently accepting a partial/truncated spoiler would invalidate evidence.
        with self.assertRaisesRegex(ValueError, "Victory"):
            parse_progression_playthrough(SPOILER.replace("  Victory: Victory\n", ""))


class ProgressionReplayTests(unittest.TestCase):
    @staticmethod
    def core_identity() -> GenerationIdentity:
        from word_factori.campaign import campaign_for_level_set

        manifest = campaign_for_level_set("core_campaign")
        return GenerationIdentity(
            level_order=tuple(record.stable_key for record in manifest.levels),
            layout_digest="a" * 64,
            stable_keys=frozenset(record.stable_key for record in manifest.levels),
            ap_ids=frozenset(),
            level_set="core_campaign",
            location_names=tuple(record.name for record in manifest.levels),
        )

    def test_replays_items_over_recipes_world_tiers_and_page_frontier(self):
        spoiler = """Playthrough:
0: {
  Bender Access
}
1: {
  Complete I: Merger2 Access
  Complete C: Rotation Access
}
2: {
  Complete V: Progressive World Access
}
3: {
  Complete AX: Progressive World Access
}
4: {
  Victory: Victory
}
"""

        result = replay_progression_choices(
            parse_progression_playthrough(spoiler), self.core_identity()
        )

        self.assertEqual((2, 4, 9), result.location_counts)
        self.assertEqual(3, result.multi_location_pre_goal_spheres)

    def test_subtracts_used_checks_and_keeps_next_page_closed_below_four(self):
        spoiler = """Playthrough:
0: {
  Bender Access
}
1: {
  Complete I: Progressive World Access
}
2: {
  Complete C: Rotation Access
}
3: {
  Victory: Victory
}
"""

        result = replay_progression_choices(
            parse_progression_playthrough(spoiler), self.core_identity()
        )

        self.assertEqual((2, 1), result.location_counts)

    def test_rejects_unknown_or_reused_playthrough_locations(self):
        unknown = """Playthrough:
1: {
  Unknown Factory: Merger2 Access
}
2: {
  Victory: Victory
}
"""
        reused = """Playthrough:
0: {
  Bender Access
}
1: {
  Complete I: Merger2 Access
}
2: {
  Complete I: Rotation Access
}
3: {
  Victory: Victory
}
"""

        with self.assertRaisesRegex(ValueError, "generated layout"):
            replay_progression_choices(
                parse_progression_playthrough(unknown), self.core_identity()
            )
        with self.assertRaisesRegex(ValueError, "reuses"):
            replay_progression_choices(
                parse_progression_playthrough(reused), self.core_identity()
            )

    def test_proportional_threshold_accepts_short_broad_playthrough_only(self):
        self.assertEqual(2, validate_progression_choices(SphereSummary(2, 2, (2, 4))))

        with self.assertRaisesRegex(AssertionError, "1 of 2 required"):
            validate_progression_choices(SphereSummary(2, 1, (2, 1)))
        with self.assertRaisesRegex(AssertionError, "no pre-goal"):
            validate_progression_choices(SphereSummary(0, 0, ()))


class IdentityExtractionTests(unittest.TestCase):
    def test_extracts_layout_order_digest_and_canonical_sets(self):
        # Omitting locations or confusing slot order with canonical identity breaks this.
        slot_data = {
            "level_order": ["owl-second", "cat-first"],
            "layout_digest": "a" * 64,
            "implementation_version": "1.3.0",
            "level_set": "core_campaign",
            "locations": [
                {"slot_index": 0, "stable_key": "owl-second", "name": "OWL — Second", "id": 975301002},
                {"slot_index": 1, "stable_key": "cat-first", "name": "CAT — First", "id": 975301001},
            ],
        }
        payload = {"slot_data": {1: slot_data}}
        encoded = bytes((3,)) + zlib.compress(pickle.dumps(payload, protocol=4))

        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "AP_13000.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("AP_13000.archipelago", encoded)

            identity = extract_generation_identity(archive_path, player=1)

        self.assertEqual(identity.level_order, ("owl-second", "cat-first"))
        self.assertEqual(identity.layout_digest, "a" * 64)
        self.assertEqual(identity.stable_keys, frozenset({"owl-second", "cat-first"}))
        self.assertEqual(identity.ap_ids, frozenset({975301001, 975301002}))
        self.assertEqual(identity.implementation_version, "1.3.0")
        self.assertEqual(identity.level_set, "core_campaign")
        self.assertEqual(identity.location_names, ("OWL — Second", "CAT — First"))

    def test_rejects_multidata_that_requests_arbitrary_python_globals(self):
        # Replacing the restricted decoder with pickle.loads makes this unsafe input load.
        encoded = bytes((3,)) + zlib.compress(pickle.dumps(eval, protocol=4))
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "AP_unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("AP_unsafe.archipelago", encoded)

            with self.assertRaisesRegex(pickle.UnpicklingError, "forbidden"):
                extract_generation_identity(archive_path, player=1)

    def test_comparison_requires_repeat_identity_and_cross_seed_canonical_sets(self):
        # Accepting a same-seed drift or a cross-seed canonical-ID drift breaks this.
        first = GenerationIdentity(
            level_order=("cat", "owl"),
            layout_digest="a" * 64,
            stable_keys=frozenset({"cat", "owl"}),
            ap_ids=frozenset({1, 2}),
        )
        repeat = GenerationIdentity(
            level_order=("cat", "owl"),
            layout_digest="a" * 64,
            stable_keys=frozenset({"cat", "owl"}),
            ap_ids=frozenset({1, 2}),
        )
        different = GenerationIdentity(
            level_order=("owl", "cat"),
            layout_digest="b" * 64,
            stable_keys=frozenset({"cat", "owl"}),
            ap_ids=frozenset({1, 2}),
        )

        compare_generation_identities(first, repeat, different)

        changed_ids = GenerationIdentity(
            level_order=("owl", "cat"),
            layout_digest="c" * 64,
            stable_keys=frozenset({"cat", "owl"}),
            ap_ids=frozenset({1, 3}),
        )
        with self.assertRaisesRegex(AssertionError, "AP-ID"):
            compare_generation_identities(first, repeat, changed_ids)


class PlayerYamlTests(unittest.TestCase):
    def test_matrix_crosses_both_level_sets_and_goals_with_shuffled_pages(self):
        # Dropping or duplicating an option pairing breaks the required 2x2 matrix.
        self.assertEqual(
            {(case.level_set, case.goal) for case in MATRIX_CASES},
            {
                ("core_campaign", "campaign_count"),
                ("core_campaign", "final_factory"),
                ("discovery_labs", "campaign_count"),
                ("discovery_labs", "final_factory"),
            },
        )
        rendered = render_player_yaml(MATRIX_CASES[0], "WF_Matrix_core_count_13000")
        self.assertIn("name: WF_Matrix_core_count_13000\n", rendered)
        self.assertIn("requires:\n  version: 0.6.7\n", rendered)
        self.assertIn("  campaign_layout: shuffled_pages\n", rendered)
        self.assertIn(f"  goal: {MATRIX_CASES[0].goal}\n", rendered)
        self.assertIn(f"  custom_level_set: {MATRIX_CASES[0].level_set}\n", rendered)


class GeneratorInvocationTests(unittest.TestCase):
    def _write_varying_generator(self, root: Path) -> Path:
        script = root / "varying_generator.py"
        script.write_text(r'''
import argparse, pickle, zipfile, zlib
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--player_files_path", required=True)
p.add_argument("--seed", required=True, type=int)
p.add_argument("--outputpath", required=True)
p.add_argument("--spoiler", required=True)
p.add_argument("--skip_prog_balancing", action="store_true")
a = p.parse_args()
order = ["cat", "owl"] if a.seed != 13001 else ["owl", "cat"]
names = {"cat": "CAT — First", "owl": "OWL — Second"}
ids = {"cat": 1, "owl": 2}
slot = {"level_order": order, "layout_digest": ("a" if a.seed != 13001 else "b") * 64,
        "implementation_version": "1.3.0",
        "locations": [{"stable_key": key, "name": names[key], "id": ids[key]} for key in order]}
encoded = bytes((3,)) + zlib.compress(pickle.dumps({"slot_data": {1: slot}}, protocol=4))
spoiler = """Archipelago Version 0.6.7  -  Seed: 13000

Playthrough:
1: {
  A: Item
  B: Item
}
2: {
  C: Item
  D: Item
}
3: {
  E: Item
  F: Item
}
4: {
  Victory: Victory
}
"""
out = Path(a.outputpath); out.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out / "AP_fake.zip", "w") as z:
    z.writestr("AP_fake.archipelago", encoded)
    z.writestr("AP_fake_Spoiler.txt", spoiler)
''', encoding="utf-8")
        return script

    def test_runs_generator_with_required_flags_and_reads_real_archive(self):
        # Omitting a required CLI flag or parsing a different output breaks this subprocess test.
        fake_generator = r'''
import argparse, pickle, zipfile, zlib
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--player_files_path", required=True)
p.add_argument("--seed", required=True, type=int)
p.add_argument("--outputpath", required=True)
p.add_argument("--spoiler", required=True, type=int)
p.add_argument("--skip_prog_balancing", action="store_true")
a = p.parse_args()
assert a.spoiler == 3 and a.skip_prog_balancing
assert list(Path(a.player_files_path).glob("*.yaml"))
slot = {"level_order": ["cat", "owl"], "layout_digest": "d" * 64,
        "locations": [{"stable_key": "cat", "id": 1},
                      {"stable_key": "owl", "id": 2}]}
encoded = bytes((3,)) + zlib.compress(pickle.dumps({"slot_data": {1: slot}}, protocol=4))
spoiler = """Archipelago Version 0.6.7  -  Seed: 13000

Playthrough:

1: {
  A: Item
  B: Item
}
2: {
  C: Item
  D: Item
}
3: {
  E: Item
  F: Item
}
4: {
  Victory: Victory
}
"""
out = Path(a.outputpath)
out.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out / "AP_fake.zip", "w") as z:
    z.writestr("AP_fake.archipelago", encoded)
    z.writestr("AP_fake_Spoiler.txt", spoiler)
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "fake_generator.py"
            script.write_text(fake_generator, encoding="utf-8")
            players = root / "players"
            output = root / "output"
            players.mkdir()
            output.mkdir()
            (players / "player.yaml").write_text("name: Test\n", encoding="utf-8")

            result = run_generation(
                (sys.executable, str(script)), players, 13000, output
            )

        self.assertEqual(result.identity.layout_digest, "d" * 64)
        self.assertEqual(len(result.playthrough), 3)
        self.assertEqual(result.ap_version, "0.6.7")

    def test_matrix_records_each_case_and_seed_then_removes_owned_workspace(self):
        # A leaked matrix workspace or skipped successful row breaks this contract.
        fake_generator = r'''
import argparse, pickle, zipfile, zlib
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--player_files_path", required=True)
p.add_argument("--seed", required=True, type=int)
p.add_argument("--outputpath", required=True)
p.add_argument("--spoiler", required=True)
p.add_argument("--skip_prog_balancing", action="store_true")
a = p.parse_args()
slot = {"level_order": ["cat", "owl"], "layout_digest": ("a" if a.seed == 13000 else "b") * 64,
        "locations": [{"stable_key": "cat", "id": 1}, {"stable_key": "owl", "id": 2}]}
encoded = bytes((3,)) + zlib.compress(pickle.dumps({"slot_data": {1: slot}}, protocol=4))
spoiler = """Archipelago Version 0.6.7  -  Seed: 13000

Playthrough:
1: {
  A: Item
  B: Item
}
2: {
  C: Item
  D: Item
}
3: {
  E: Item
  F: Item
}
4: {
  Victory: Victory
}
"""
out = Path(a.outputpath); out.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out / "AP_fake.zip", "w") as z:
    z.writestr("AP_fake.archipelago", encoded)
    z.writestr("AP_fake_Spoiler.txt", spoiler)
'''
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            script = parent / "fake_matrix_generator.py"
            script.write_text(fake_generator, encoding="utf-8")
            rows = execute_matrix(
                (sys.executable, str(script)),
                cases=MATRIX_CASES[:2],
                seeds=range(13000, 13002),
                temporary_parent=parent,
                sphere_evaluator=lambda *_: SphereSummary(3, 3, (2, 2, 2)),
            )

            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row["status"] == "Pass" for row in rows))
            self.assertFalse(any(parent.glob("word-factori-ap067-matrix-*")))

    def test_matrix_checkpoints_each_row_and_stops_on_first_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            script = self._write_varying_generator(parent)
            checkpoint = parent / "checkpoint.json"

            rows = execute_matrix(
                (sys.executable, str(script)),
                cases=MATRIX_CASES[:1],
                seeds=range(13000, 13003),
                temporary_parent=parent,
                evidence_output=checkpoint,
                sphere_evaluator=lambda _, identity: (
                    SphereSummary(1, 0, (1,))
                    if identity.layout_digest.startswith("b")
                    else SphereSummary(3, 3, (2, 2, 2))
                ),
            )

            self.assertEqual(["Pass", "Fail"], [row["status"] for row in rows])
            payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual("stopped_on_failure", payload["status"])
            self.assertEqual(
                [(row["seed"], row["status"]) for row in rows],
                [(row["seed"], row["status"]) for row in payload["matrix_rows"]],
            )
            self.assertEqual(2, payload["matrix_summary"]["completed"])
            self.assertFalse(any(parent.glob("word-factori-ap067-matrix-*")))

    def test_determinism_check_cleans_workspace_and_live_prep_preserves_room(self):
        # Reusing one output directory or deleting the prepared live room breaks this.
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            script = self._write_varying_generator(parent)
            command = (sys.executable, str(script))

            deterministic = verify_deterministic_identity(
                command, MATRIX_CASES[2], temporary_parent=parent
            )
            live = prepare_live_room(
                command, MATRIX_CASES[2], seed=13050, temporary_parent=parent,
                expected_levels=2,
            )

            self.assertEqual(deterministic["status"], "Pass")
            self.assertFalse(any(parent.glob("word-factori-ap067-identity-*")))
            live_root = Path(live["room_root"])
            self.assertTrue(Path(live["archive_path"]).is_file())
            self.assertTrue((live_root / "players" / "player.yaml").is_file())
            self.assertEqual(live["page_one_targets"], ["CAT — First", "OWL — Second"])

    def test_script_entrypoint_defines_identity_comparison_before_running_main(self):
        # Moving the __main__ block above a function used by main reproduces the real NameError.
        tool = Path(__file__).parents[1] / "tools" / "verify_generation_matrix.py"
        source = tool.read_text(encoding="utf-8")

        self.assertLess(
            source.index("def compare_generation_identities("),
            source.index('if __name__ == "__main__":'),
        )


if __name__ == "__main__":
    unittest.main()
