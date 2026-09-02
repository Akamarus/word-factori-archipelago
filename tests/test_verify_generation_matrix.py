from __future__ import annotations

import json
import pickle
import sys
import tempfile
import types
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock

from tools import verify_generation_matrix as matrix_tool

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
    validate_generation_identity,
    validate_progression_choices,
    verify_deterministic_identity,
)
from word_factori.data import locations_for_level_set


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
            # AP 0.6.7 materializes this sequence as a tuple in real multidata.
            "level_order": ("owl-second", "cat-first"),
            "layout_digest": "a" * 64,
            "implementation_version": "1.3.0",
            "level_set": "core_campaign",
            "goal": 0,
            "campaign_count": 25,
            "level_count": 2,
            "layout_algorithm": "balanced_pages_v1",
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
        self.assertEqual(getattr(identity, "goal", None), 0)
        self.assertEqual(getattr(identity, "campaign_count", None), 25)
        self.assertEqual(getattr(identity, "level_count", None), 2)
        self.assertEqual(getattr(identity, "layout_algorithm", None), "balanced_pages_v1")
        self.assertEqual(identity.location_names, ("OWL — Second", "CAT — First"))
        self.assertEqual(
            identity.location_projection,
            (
                ("owl-second", "OWL — Second", 975301002),
                ("cat-first", "CAT — First", 975301001),
            ),
        )

    def test_canonical_location_projection_rejects_every_row_mutation_and_cardinality_change(self):
        case = MATRIX_CASES[0]
        canonical_locations = locations_for_level_set(case.level_set)
        canonical = tuple(
            (location.stable_key, location.name, location.code)
            for location in canonical_locations
        )
        base = dict(
            level_order=tuple(location.stable_key for location in canonical_locations),
            layout_digest="a" * 64,
            stable_keys=frozenset(location.stable_key for location in canonical_locations),
            ap_ids=frozenset(location.code for location in canonical_locations),
            implementation_version="1.3.0",
            level_set=case.level_set,
            location_names=tuple(location.name for location in canonical_locations),
            goal=0,
            campaign_count=25,
            level_count=len(canonical_locations),
            layout_algorithm="balanced_pages_v1",
        )
        mutations = {
            "duplicate and omission": canonical[:-1] + (canonical[0],),
            "wrong stable key": (("wrong-key", canonical[0][1], canonical[0][2]),) + canonical[1:],
            "wrong name": ((canonical[0][0], "Wrong Name", canonical[0][2]),) + canonical[1:],
            "wrong ID": ((canonical[0][0], canonical[0][1], -1),) + canonical[1:],
            "omission": canonical[:-1],
            "extra row": canonical + (canonical[0],),
        }

        validate_generation_identity(GenerationIdentity(**base, location_projection=canonical), case)
        for label, projection in mutations.items():
            with self.subTest(label=label):
                with self.assertRaisesRegex(AssertionError, "canonical location projection"):
                    validate_generation_identity(
                        GenerationIdentity(**base, location_projection=projection), case,
                    )

    def test_rejects_multidata_that_requests_arbitrary_python_globals(self):
        # Replacing the restricted decoder with pickle.loads makes this unsafe input load.
        encoded = bytes((3,)) + zlib.compress(pickle.dumps(eval, protocol=4))
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "AP_unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("AP_unsafe.archipelago", encoded)

            with self.assertRaisesRegex(pickle.UnpicklingError, "forbidden"):
                extract_generation_identity(archive_path, player=1)

    def test_rejects_oversized_multidata_zip_member_before_reading_it(self):
        slot_data = {
            "level_order": ["cat-first"],
            "layout_digest": "a" * 64,
            "implementation_version": "1.3.0",
            "level_set": "core_campaign",
            "goal": 0,
            "campaign_count": 25,
            "level_count": 1,
            "layout_algorithm": "balanced_pages_v1",
            "locations": [
                {"stable_key": "cat-first", "name": "CAT — First", "id": 1},
            ],
        }
        encoded = bytes((3,)) + zlib.compress(
            pickle.dumps({"slot_data": {1: slot_data}}, protocol=4)
        )
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "AP_oversized.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("AP_oversized.archipelago", encoded)

            with mock.patch.object(
                matrix_tool, "MAX_MULTIDATA_MEMBER_BYTES", len(encoded) - 1,
                create=True,
            ):
                with self.assertRaisesRegex(ValueError, "multidata.*too large"):
                    extract_generation_identity(archive_path, player=1)

    def test_bounded_zip_reader_rejects_declared_size_before_open(self):
        # Moving the size check after archive.open would trigger the sentinel.
        opened: list[str] = []

        class InstrumentedArchive:
            def open(self, member):
                opened.append(member.filename)
                raise AssertionError("oversized member was opened")

        member = zipfile.ZipInfo("AP_oversized.archipelago")
        member.file_size = 65

        with self.assertRaisesRegex(ValueError, "multidata.*too large"):
            matrix_tool._read_zip_member_bounded(
                InstrumentedArchive(), member, limit=64, label="multidata"
            )

        self.assertEqual(opened, [])

    def test_rejects_multidata_whose_nested_zlib_payload_exceeds_limit(self):
        slot_data = {
            "level_order": ["cat-first"],
            "layout_digest": "a" * 64,
            "implementation_version": "1.3.0",
            "level_set": "core_campaign",
            "goal": 0,
            "campaign_count": 25,
            "level_count": 1,
            "layout_algorithm": "balanced_pages_v1",
            "locations": [
                {"stable_key": "cat-first", "name": "CAT — First", "id": 1},
            ],
        }
        encoded = bytes((3,)) + zlib.compress(
            pickle.dumps({"slot_data": {1: slot_data}}, protocol=4)
        )
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "AP_nested.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("AP_nested.archipelago", encoded)

            with mock.patch.object(
                matrix_tool, "MAX_MULTIDATA_PAYLOAD_BYTES", 64, create=True,
            ):
                with self.assertRaisesRegex(ValueError, "decompressed multidata.*too large"):
                    extract_generation_identity(archive_path, player=1)

    def test_multidata_decompression_receives_a_bounded_output_limit(self):
        # Removing max_length would record zero and allow the fake to overproduce.
        requested_limits: list[int] = []
        produced_lengths: list[int] = []

        class InstrumentedDecompressor:
            unconsumed_tail = b"compressed-data-remains"
            unused_data = b""
            eof = False

            def decompress(self, _payload, max_length=0):
                requested_limits.append(max_length)
                produced = b"x" * (max_length if max_length else 128)
                produced_lengths.append(len(produced))
                return produced

            def flush(self, _length):
                raise AssertionError("oversized output must be rejected before flush")

        with (
            mock.patch.object(matrix_tool, "MAX_MULTIDATA_PAYLOAD_BYTES", 7),
            mock.patch.object(
                matrix_tool.zlib,
                "decompressobj",
                return_value=InstrumentedDecompressor(),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "decompressed multidata.*too large"):
                matrix_tool._decode_multidata(b"\x03compressed")

        self.assertEqual(requested_limits, [8])
        self.assertEqual(produced_lengths, [8])

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
import argparse, pickle, sys, zipfile, zlib
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from word_factori.data import locations_for_level_set
p = argparse.ArgumentParser()
p.add_argument("--player_files_path", required=True)
p.add_argument("--seed", required=True, type=int)
p.add_argument("--outputpath", required=True)
p.add_argument("--spoiler", required=True)
p.add_argument("--skip_prog_balancing", action="store_true")
a = p.parse_args()
yaml = next(Path(a.player_files_path).glob("*.yaml")).read_text(encoding="utf-8")
level_set = "discovery_labs" if "custom_level_set: discovery_labs" in yaml else "core_campaign"
goal = 1 if "goal: final_factory" in yaml else 0
canonical = list(locations_for_level_set(level_set))
level_count = len(canonical)
order = [location.stable_key for location in canonical]
if a.seed == 13001:
    order[:2] = list(reversed(order[:2]))
by_key = {location.stable_key: location for location in canonical}
slot = {"level_order": order, "layout_digest": ("a" if a.seed != 13001 else "b") * 64,
        "implementation_version": "1.3.0",
        "level_set": level_set, "goal": goal, "campaign_count": 25,
        "level_count": level_count, "layout_algorithm": "balanced_pages_v1",
        "locations": [{"stable_key": key, "name": by_key[key].name, "id": by_key[key].code} for key in order]}
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
        "implementation_version": "1.3.0", "level_set": "core_campaign",
        "goal": 0, "campaign_count": 25, "level_count": 2,
        "layout_algorithm": "balanced_pages_v1",
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

    def test_matrix_rejects_every_requested_slot_option_mismatch(self):
        case = MATRIX_CASES[3]
        canonical_locations = locations_for_level_set(case.level_set)
        valid = {
            "level_order": tuple(location.stable_key for location in canonical_locations),
            "layout_digest": "a" * 64,
            "stable_keys": frozenset(location.stable_key for location in canonical_locations),
            "ap_ids": frozenset(location.code for location in canonical_locations),
            "implementation_version": "1.3.0",
            "level_set": "discovery_labs",
            "location_names": tuple(location.name for location in canonical_locations),
            "goal": 1,
            "campaign_count": 25,
            "level_count": 40,
            "layout_algorithm": "balanced_pages_v1",
            "location_projection": tuple(
                (location.stable_key, location.name, location.code)
                for location in canonical_locations
            ),
        }
        mismatches = {
            "level_set": "core_campaign",
            "goal": 0,
            "campaign_count": 24,
            "level_count": 30,
            "layout_algorithm": "fixed_pages_v1",
            "implementation_version": "",
            "level_order": tuple(location.stable_key for location in canonical_locations[:-1]),
        }
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            for field, wrong_value in mismatches.items():
                with self.subTest(field=field):
                    identity_values = dict(valid)
                    identity_values[field] = wrong_value
                    identity = types.SimpleNamespace(**identity_values)
                    generation = matrix_tool.GenerationRun(
                        archive_path=parent / "unused.zip",
                        identity=identity,
                        playthrough=(),
                        ap_version="0.6.7",
                    )
                    with mock.patch.object(
                        matrix_tool, "run_generation", return_value=generation,
                    ):
                        rows = execute_matrix(
                            ("unused-generator",),
                            cases=(case,),
                            seeds=range(13000, 13001),
                            temporary_parent=parent,
                            sphere_evaluator=lambda *_: SphereSummary(3, 3, (2, 2, 2)),
                        )

                    self.assertEqual(rows[0]["status"], "Fail")
                    self.assertEqual(rows[0].get("identity_validation"), "Fail")
                    self.assertEqual(rows[0].get("canonical_identity_validation"), "Pass")
                    self.assertEqual(rows[0].get("requested_level_set"), "discovery_labs")
                    self.assertEqual(rows[0].get("requested_goal"), 1)
                    self.assertEqual(rows[0].get("generated_level_set"), identity.level_set)
                    self.assertEqual(rows[0].get("generated_goal"), identity.goal)
                    self.assertEqual(
                        rows[0].get("generated_level_order_count"),
                        len(identity.level_order),
                    )
                    self.assertIn(field, rows[0]["error"])

    def test_matrix_rejects_fake_generator_that_ignores_requested_options(self):
        fake_generator = r'''
import argparse, pickle, zipfile, zlib
from pathlib import Path
from word_factori.data import locations_for_level_set
p = argparse.ArgumentParser()
p.add_argument("--player_files_path", required=True)
p.add_argument("--seed", required=True, type=int)
p.add_argument("--outputpath", required=True)
p.add_argument("--spoiler", required=True)
p.add_argument("--skip_prog_balancing", action="store_true")
a = p.parse_args()
order = [f"core-{index}" for index in range(30)]
slot = {
    "level_order": order,
    "layout_digest": "a" * 64,
    "implementation_version": "1.3.0",
    "level_set": "core_campaign",
    "goal": 0,
    "campaign_count": 25,
    "level_count": 30,
    "layout_algorithm": "balanced_pages_v1",
    "locations": [
        {"stable_key": key, "name": key, "id": index}
        for index, key in enumerate(order)
    ],
}
encoded = bytes((3,)) + zlib.compress(pickle.dumps({"slot_data": {1: slot}}, protocol=4))
spoiler = """Archipelago Version 0.6.7  -  Seed: 13000

Playthrough:
1: {
  A: Item
  B: Item
}
2: {
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
            script = parent / "ignores_options.py"
            script.write_text(fake_generator, encoding="utf-8")
            rows = execute_matrix(
                (sys.executable, str(script)),
                cases=(MATRIX_CASES[3],),
                seeds=range(13000, 13001),
                temporary_parent=parent,
                sphere_evaluator=lambda *_: SphereSummary(1, 1, (2,)),
            )

        self.assertEqual(rows[0]["status"], "Fail")
        self.assertIn("level_set", rows[0]["error"])

    def test_run_generation_rejects_oversized_spoiler_zip_member(self):
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
slot = {
    "level_order": ["cat"],
    "layout_digest": "a" * 64,
    "implementation_version": "1.3.0",
    "level_set": "core_campaign",
    "goal": 0,
    "campaign_count": 25,
    "level_count": 1,
    "layout_algorithm": "balanced_pages_v1",
    "locations": [{"stable_key": "cat", "name": "CAT", "id": 1}],
}
encoded = bytes((3,)) + zlib.compress(pickle.dumps({"slot_data": {1: slot}}, protocol=4))
spoiler = """Archipelago Version 0.6.7  -  Seed: 13000

Playthrough:
1: {
  A: Item
}
2: {
  Victory: Victory
}
""" + (" " * 256)
out = Path(a.outputpath); out.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out / "AP_fake.zip", "w") as z:
    z.writestr("AP_fake.archipelago", encoded)
    z.writestr("AP_fake_Spoiler.txt", spoiler)
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "oversized_spoiler.py"
            script.write_text(fake_generator, encoding="utf-8")
            players = root / "players"
            output = root / "output"
            players.mkdir()
            output.mkdir()
            (players / "player.yaml").write_text("name: Test\n", encoding="utf-8")

            with mock.patch.object(
                matrix_tool, "MAX_SPOILER_MEMBER_BYTES", 128, create=True,
            ):
                with self.assertRaisesRegex(ValueError, "spoiler.*too large"):
                    run_generation(
                        (sys.executable, str(script)), players, 13000, output
                    )

    def test_matrix_records_each_case_and_seed_then_removes_owned_workspace(self):
        # A leaked matrix workspace or skipped successful row breaks this contract.
        fake_generator = r'''
import argparse, pickle, sys, zipfile, zlib
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from word_factori.data import locations_for_level_set
p = argparse.ArgumentParser()
p.add_argument("--player_files_path", required=True)
p.add_argument("--seed", required=True, type=int)
p.add_argument("--outputpath", required=True)
p.add_argument("--spoiler", required=True)
p.add_argument("--skip_prog_balancing", action="store_true")
a = p.parse_args()
yaml = next(Path(a.player_files_path).glob("*.yaml")).read_text(encoding="utf-8")
goal = 1 if "goal: final_factory" in yaml else 0
canonical = list(locations_for_level_set("core_campaign"))
order = [location.stable_key for location in canonical]
slot = {"level_order": order, "layout_digest": ("a" if a.seed == 13000 else "b") * 64,
        "implementation_version": "1.3.0", "level_set": "core_campaign",
        "goal": goal, "campaign_count": 25, "level_count": 30,
        "layout_algorithm": "balanced_pages_v1",
        "locations": [{"stable_key": location.stable_key, "name": location.name,
                       "id": location.code} for location in canonical]}
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
            self.assertEqual(
                {
                    key: rows[0].get(key)
                    for key in (
                        "requested_level_set",
                        "requested_goal",
                        "requested_campaign_count",
                        "requested_level_count",
                        "requested_level_order_count",
                        "requested_layout_algorithm",
                        "requested_implementation_version",
                        "generated_level_set",
                        "generated_goal",
                        "generated_campaign_count",
                        "generated_level_count",
                        "generated_level_order_count",
                        "generated_layout_algorithm",
                        "generated_implementation_version",
                        "identity_validation",
                        "canonical_identity_validation",
                    )
                },
                {
                    "requested_level_set": "core_campaign",
                    "requested_goal": 0,
                    "requested_campaign_count": 25,
                    "requested_level_count": 30,
                    "requested_level_order_count": 30,
                    "requested_layout_algorithm": "balanced_pages_v1",
                    "requested_implementation_version": "1.3.0",
                    "generated_level_set": "core_campaign",
                    "generated_goal": 0,
                    "generated_campaign_count": 25,
                    "generated_level_count": 30,
                    "generated_level_order_count": 30,
                    "generated_layout_algorithm": "balanced_pages_v1",
                    "generated_implementation_version": "1.3.0",
                    "identity_validation": "Pass",
                    "canonical_identity_validation": "Pass",
                },
            )
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
            )

            self.assertEqual(deterministic["status"], "Pass")
            self.assertFalse(any(parent.glob("word-factori-ap067-identity-*")))
            live_root = Path(live["room_root"])
            self.assertTrue(Path(live["archive_path"]).is_file())
            self.assertTrue((live_root / "players" / "player.yaml").is_file())
            self.assertEqual(
                live["page_one_targets"],
                [
                    "Complete I", "Complete C", "Complete V",
                    "Complete L", "Complete O", "Complete A",
                ],
            )

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
