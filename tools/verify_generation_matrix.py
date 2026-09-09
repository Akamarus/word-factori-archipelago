from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import io
import json
import pickle
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from word_factori.campaign import campaign_for_level_set
from word_factori.capabilities import requirements_for_record
from word_factori.data import locations_for_level_set
from word_factori.layout import PAGE_SIZE, PAGE_UNLOCK_COUNT, TUTORIAL_PAGE_UNLOCK_COUNT

MAX_MULTIDATA_MEMBER_BYTES = 16 * 1024 * 1024
MAX_MULTIDATA_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_SPOILER_MEMBER_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class SphereSummary:
    total_pre_goal_spheres: int
    multi_location_pre_goal_spheres: int
    location_counts: tuple[int, ...]


@dataclass(frozen=True)
class SphereEntry:
    location: str | None
    item: str


@dataclass(frozen=True)
class ProgressionSphere:
    number: int
    entries: tuple[SphereEntry, ...]


@dataclass(frozen=True)
class GenerationIdentity:
    level_order: tuple[str, ...]
    layout_digest: str
    stable_keys: frozenset[str]
    ap_ids: frozenset[int]
    implementation_version: str = ""
    level_set: str = ""
    location_names: tuple[str, ...] = ()
    goal: int | None = None
    campaign_count: int | None = None
    level_count: int | None = None
    layout_algorithm: str = ""
    location_projection: tuple[tuple[str, str, int], ...] = ()


@dataclass(frozen=True)
class MatrixCase:
    key: str
    level_set: str
    goal: str
    campaign_layout: str = "shuffled_pages"


@dataclass(frozen=True)
class GenerationRun:
    archive_path: Path
    identity: GenerationIdentity
    playthrough: tuple[ProgressionSphere, ...]
    ap_version: str


MATRIX_CASES = (
    MatrixCase("core-count", "core_campaign", "campaign_count"),
    MatrixCase("core-final", "core_campaign", "final_factory"),
    MatrixCase("discovery-count", "discovery_labs", "campaign_count"),
    MatrixCase("discovery-final", "discovery_labs", "final_factory"),
)


_SPHERE_HEADER = re.compile(r"^(\d+): \{$")
_AP_VERSION = re.compile(r"^Archipelago Version ([0-9.]+)\s+-", re.MULTILINE)


def render_player_yaml(case: MatrixCase, player_name: str) -> str:
    return f"""name: {player_name}
description: AP 0.6.7 nonlinear progression acceptance
game: Word Factori
requires:
  version: 0.6.7
Word Factori:
  progression_balancing: 50
  accessibility: items
  goal: {case.goal}
  campaign_count: 25
  custom_level_set: {case.level_set}
  campaign_layout: {case.campaign_layout}
"""


class _NetworkSlot(tuple):
    def __new__(cls, *values):
        return tuple.__new__(cls, values)


class _SlotType(int):
    pass


class _RestrictedUnpickler(pickle.Unpickler):
    _ALLOWED = {
        ("NetUtils", "NetworkSlot"): _NetworkSlot,
        ("NetUtils", "SlotType"): _SlotType,
    }

    def find_class(self, module: str, name: str):
        try:
            return self._ALLOWED[(module, name)]
        except KeyError as error:
            raise pickle.UnpicklingError(
                f"forbidden multidata global: {module}.{name}"
            ) from error


def _decode_multidata(encoded: bytes) -> dict:
    if not encoded or encoded[0] != 3:
        raise ValueError("unsupported Archipelago multidata format")
    decompressor = zlib.decompressobj()
    decoded = decompressor.decompress(
        encoded[1:], MAX_MULTIDATA_PAYLOAD_BYTES + 1
    )
    if len(decoded) > MAX_MULTIDATA_PAYLOAD_BYTES or decompressor.unconsumed_tail:
        raise ValueError("decompressed multidata payload is too large")
    decoded += decompressor.flush(MAX_MULTIDATA_PAYLOAD_BYTES + 1 - len(decoded))
    if len(decoded) > MAX_MULTIDATA_PAYLOAD_BYTES:
        raise ValueError("decompressed multidata payload is too large")
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("invalid compressed multidata payload")
    payload = _RestrictedUnpickler(io.BytesIO(decoded)).load()
    if not isinstance(payload, dict):
        raise ValueError("Archipelago multidata root is not a dictionary")
    return payload


def _read_zip_member_bounded(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    *,
    limit: int,
    label: str,
) -> bytes:
    if member.file_size > limit:
        raise ValueError(
            f"{label} ZIP member is too large: {member.file_size} bytes, limit {limit}"
        )
    with archive.open(member) as stream:
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise ValueError(f"{label} ZIP member is too large: limit {limit} bytes")
    return payload


def _required_slot_field(slot_data: dict, name: str, expected_type: type):
    if name not in slot_data:
        raise ValueError(f"slot data has no {name}")
    value = slot_data[name]
    if type(value) is not expected_type:
        raise ValueError(
            f"slot data {name} must be {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def _required_string_sequence(slot_data: dict, name: str) -> tuple[str, ...]:
    if name not in slot_data:
        raise ValueError(f"slot data has no {name}")
    value = slot_data[name]
    if type(value) not in (list, tuple) or any(type(item) is not str for item in value):
        raise ValueError(f"slot data {name} must be a list or tuple of strings")
    return tuple(value)


def parse_progression_playthrough(spoiler: str) -> tuple[ProgressionSphere, ...]:
    try:
        playthrough_index = next(
            index for index, line in enumerate(spoiler.splitlines())
            if line.strip() == "Playthrough:"
        )
    except StopIteration as error:
        raise ValueError("spoiler has no Playthrough section") from error

    spheres: list[ProgressionSphere] = []
    current_number: int | None = None
    current: list[SphereEntry] | None = None
    found_victory = False
    for raw_line in spoiler.splitlines()[playthrough_index + 1:]:
        line = raw_line.rstrip()
        header = _SPHERE_HEADER.fullmatch(line)
        if header:
            number = int(header.group(1))
            if current is not None or (spheres and number <= spheres[-1].number):
                raise ValueError("spoiler Playthrough has invalid sphere ordering")
            current_number = number
            current = []
        elif current is not None and line == "}":
            if any(entry.item == "Victory" for entry in current):
                found_victory = True
                break
            if current_number is None:
                raise ValueError("spoiler Playthrough sphere has no number")
            spheres.append(ProgressionSphere(current_number, tuple(current)))
            current_number = None
            current = None
        elif current is not None and line.startswith("  "):
            entry = line.strip()
            if not entry:
                continue
            if ": " in entry:
                location, item = entry.rsplit(": ", 1)
                current.append(SphereEntry(location, item))
            else:
                current.append(SphereEntry(None, entry))

    if not found_victory:
        raise ValueError("spoiler Playthrough has no Victory sphere")
    return tuple(spheres)


def replay_progression_choices(
    playthrough: tuple[ProgressionSphere, ...],
    identity: GenerationIdentity,
) -> SphereSummary:
    manifest = campaign_for_level_set(identity.level_set)
    records = {record.stable_key: record for record in manifest.levels}
    if len(identity.level_order) != len(identity.location_names):
        raise ValueError("generated layout order and location names differ in length")
    if set(identity.level_order) != set(records):
        raise ValueError("generated layout stable keys do not match its level set")

    ordered = tuple(records[key] for key in identity.level_order)
    expected_names = tuple(record.name for record in ordered)
    if identity.location_names != expected_names:
        raise ValueError("generated layout location names do not match stable keys")
    locations_by_name = dict(zip(identity.location_names, ordered))

    inventory: Counter[str] = Counter()
    used_locations: set[str] = set()
    counts: list[int] = []

    def reachable_locations() -> set[str]:
        reachable: set[str] = set()
        item_names = {name for name, count in inventory.items() if count > 0}
        world_access = inventory["Progressive World Access"]
        previous_page_reachable = PAGE_UNLOCK_COUNT
        for page_start in range(0, len(ordered), PAGE_SIZE):
            page = ordered[page_start:page_start + PAGE_SIZE]
            threshold = TUTORIAL_PAGE_UNLOCK_COUNT if page_start == PAGE_SIZE else PAGE_UNLOCK_COUNT
            if page_start and previous_page_reachable < threshold:
                previous_page_reachable = 0
                continue
            page_reachable = 0
            for record in page:
                if record.world_tier > world_access:
                    if page_start == 0:
                        break
                    continue
                if any(
                    requirements <= item_names
                    for requirements in requirements_for_record(record)
                ):
                    reachable.add(record.name)
                    page_reachable += 1
                elif page_start == 0:
                    break
            previous_page_reachable = page_reachable
        return reachable

    for sphere in playthrough:
        sphere_locations = tuple(
            entry.location for entry in sphere.entries if entry.location is not None
        )
        if sphere_locations:
            unknown = set(sphere_locations) - set(locations_by_name)
            if unknown:
                raise ValueError(
                    "spoiler location is not in the generated layout: "
                    + ", ".join(sorted(unknown))
                )
            reused = set(sphere_locations) & used_locations
            if reused:
                raise ValueError(
                    "spoiler reuses a playthrough location: "
                    + ", ".join(sorted(reused))
                )
            reachable = reachable_locations()
            unreachable = set(sphere_locations) - reachable
            if unreachable:
                raise ValueError(
                    "spoiler location is unreachable in reconstructed state: "
                    + ", ".join(sorted(unreachable))
                )
            counts.append(len(reachable - used_locations))
            used_locations.update(sphere_locations)
        for entry in sphere.entries:
            inventory[entry.item] += 1

    return SphereSummary(
        total_pre_goal_spheres=len(counts),
        multi_location_pre_goal_spheres=sum(count >= 2 for count in counts),
        location_counts=tuple(counts),
    )


def validate_progression_choices(summary: SphereSummary) -> int:
    if summary.total_pre_goal_spheres == 0:
        raise AssertionError("playthrough has no pre-goal replay state")
    required = min(3, summary.total_pre_goal_spheres)
    if summary.multi_location_pre_goal_spheres < required:
        raise AssertionError(
            "broad pre-goal replay states: "
            f"{summary.multi_location_pre_goal_spheres} of {required} required; "
            f"reachable unused counts: {summary.location_counts}"
        )
    return required


def extract_generation_identity(archive_path: Path, *, player: int) -> GenerationIdentity:
    with zipfile.ZipFile(archive_path) as archive:
        multidata_members = [
            member for member in archive.infolist()
            if member.filename.endswith(".archipelago")
        ]
        if len(multidata_members) != 1:
            raise ValueError(f"expected one multidata file in {archive_path}")
        encoded = _read_zip_member_bounded(
            archive,
            multidata_members[0],
            limit=MAX_MULTIDATA_MEMBER_BYTES,
            label="multidata",
        )
    payload = _decode_multidata(encoded)
    slot_data = payload["slot_data"][player]
    locations = slot_data["locations"]
    location_projection = tuple(
        (location["stable_key"], location.get("name", ""), location["id"])
        for location in locations
    )
    return GenerationIdentity(
        level_order=_required_string_sequence(slot_data, "level_order"),
        layout_digest=_required_slot_field(slot_data, "layout_digest", str),
        stable_keys=frozenset(location["stable_key"] for location in locations),
        ap_ids=frozenset(location["id"] for location in locations),
        implementation_version=_required_slot_field(
            slot_data, "implementation_version", str
        ),
        level_set=_required_slot_field(slot_data, "level_set", str),
        location_names=tuple(location.get("name", "") for location in locations),
        goal=_required_slot_field(slot_data, "goal", int),
        campaign_count=_required_slot_field(slot_data, "campaign_count", int),
        level_count=_required_slot_field(slot_data, "level_count", int),
        layout_algorithm=_required_slot_field(slot_data, "layout_algorithm", str),
        location_projection=location_projection,
    )


def _requested_identity(case: MatrixCase) -> dict:
    level_count = {"core_campaign": 30, "discovery_labs": 40}[case.level_set]
    return {
        "level_set": case.level_set,
        "goal": {"campaign_count": 0, "final_factory": 1}[case.goal],
        "campaign_count": 25,
        "level_count": level_count,
        "level_order_count": level_count,
        "layout_algorithm": "fixed_pages_v1" if case.campaign_layout == "fixed_pages" else "balanced_pages_v2",
        "implementation_version": "1.3.0",
    }


def _generated_identity(identity: GenerationIdentity) -> dict:
    return {
        "level_set": identity.level_set,
        "goal": identity.goal,
        "campaign_count": identity.campaign_count,
        "level_count": identity.level_count,
        "level_order_count": len(identity.level_order),
        "layout_algorithm": identity.layout_algorithm,
        "implementation_version": identity.implementation_version,
    }


def _validate_requested_generation_identity(
    identity: GenerationIdentity, case: MatrixCase,
) -> None:
    expected = _requested_identity(case)
    generated = _generated_identity(identity)
    for field, expected_value in expected.items():
        actual = generated[field]
        if type(actual) is not type(expected_value) or actual != expected_value:
            raise AssertionError(
                f"generated {field} {actual!r}, expected {expected_value!r} "
                f"for {case.key}"
            )


def validate_canonical_location_projection(
    identity: GenerationIdentity, case: MatrixCase,
) -> None:
    canonical = tuple(
        (location.stable_key, location.name, location.code)
        for location in locations_for_level_set(case.level_set)
    )
    generated_projection = ()
    try:
        generated_projection = tuple(identity.location_projection)
        matches = (
            len(generated_projection) == len(canonical)
            and sorted(generated_projection, key=lambda row: row[0])
            == sorted(canonical, key=lambda row: row[0])
        )
    except (IndexError, TypeError, ValueError):
        matches = False
    if not matches:
        raise AssertionError(
            f"generated canonical location projection does not exactly match "
            f"{case.level_set} ({len(generated_projection)} rows, expected {len(canonical)})"
        )


def validate_generation_identity(
    identity: GenerationIdentity, case: MatrixCase
) -> None:
    _validate_requested_generation_identity(identity, case)
    validate_canonical_location_projection(identity, case)


def run_generation(
    generator_command: tuple[str, ...],
    player_files_path: Path,
    seed: int,
    output_path: Path,
) -> GenerationRun:
    command = [
        *generator_command,
        "--player_files_path",
        str(player_files_path),
        "--seed",
        str(seed),
        "--outputpath",
        str(output_path),
        "--spoiler",
        "3",
        "--skip_prog_balancing",
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        details = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        raise RuntimeError(
            f"generator exited {completed.returncode} for seed {seed}:\n{details}"
        )
    archives = list(output_path.glob("*.zip"))
    if len(archives) != 1:
        raise RuntimeError(f"expected one output ZIP for seed {seed}, found {len(archives)}")
    archive_path = archives[0]
    with zipfile.ZipFile(archive_path) as archive:
        spoilers = [
            member for member in archive.infolist()
            if member.filename.endswith("_Spoiler.txt")
        ]
        if len(spoilers) != 1:
            raise RuntimeError(f"expected one spoiler in {archive_path}")
        spoiler = _read_zip_member_bounded(
            archive,
            spoilers[0],
            limit=MAX_SPOILER_MEMBER_BYTES,
            label="spoiler",
        ).decode("utf-8-sig")
    version_match = _AP_VERSION.search(spoiler)
    if version_match is None:
        raise ValueError("spoiler has no Archipelago version header")
    return GenerationRun(
        archive_path=archive_path,
        identity=extract_generation_identity(archive_path, player=1),
        playthrough=parse_progression_playthrough(spoiler),
        ap_version=version_match.group(1),
    )


def _concise_error(error: Exception) -> str:
    lines = [line for line in str(error).splitlines() if line.strip()]
    return "\n".join(lines[-20:])


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, default=list) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _checkpoint_matrix(path: Path, rows: list[dict], total: int) -> None:
    failures = sum(row["status"] == "Fail" for row in rows)
    _write_json_atomic(
        path,
        {
            "status": "stopped_on_failure" if failures else "matrix_in_progress",
            "matrix_summary": {
                "expected": total,
                "completed": len(rows),
                "passed": len(rows) - failures,
                "failed": failures,
            },
            "matrix_rows": rows,
            "deterministic_identity": {"status": "Pending"},
            "live_room": {"status": "Pending live test"},
        },
    )


def execute_matrix(
    generator_command: tuple[str, ...],
    *,
    cases: tuple[MatrixCase, ...] = MATRIX_CASES,
    seeds=range(13000, 13050),
    temporary_parent: Path | None = None,
    evidence_output: Path | None = None,
    sphere_evaluator: Callable[
        [tuple[ProgressionSphere, ...], GenerationIdentity], SphereSummary
    ] = replay_progression_choices,
) -> list[dict]:
    matrix_root = Path(
        tempfile.mkdtemp(
            prefix="word-factori-ap067-matrix-",
            dir=temporary_parent,
        )
    )
    rows: list[dict] = []
    total = len(cases) * len(seeds)
    completed_count = 0
    try:
        for case in cases:
            players = matrix_root / case.key / "players"
            players.mkdir(parents=True)
            player_name = f"WF_Matrix_{case.key.replace('-', '_')}"
            (players / "player.yaml").write_text(
                render_player_yaml(case, player_name), encoding="utf-8"
            )
            for seed in seeds:
                completed_count += 1
                output = matrix_root / case.key / f"output-{seed}"
                output.mkdir()
                requested_identity = _requested_identity(case)
                row = {
                    "case": case.key,
                    "player": player_name,
                    "seed": seed,
                    **{
                        f"requested_{field}": value
                        for field, value in requested_identity.items()
                    },
                    "identity_validation": "Not run",
                    "canonical_identity_validation": "Not run",
                }
                try:
                    result = run_generation(generator_command, players, seed, output)
                    row.update(
                        {
                            f"generated_{field}": value
                            for field, value in _generated_identity(
                                result.identity
                            ).items()
                        }
                    )
                    try:
                        validate_canonical_location_projection(result.identity, case)
                    except Exception:
                        row["identity_validation"] = "Fail"
                        row["canonical_identity_validation"] = "Fail"
                        raise
                    row["canonical_identity_validation"] = "Pass"
                    try:
                        _validate_requested_generation_identity(result.identity, case)
                    except Exception:
                        row["identity_validation"] = "Fail"
                        raise
                    row["identity_validation"] = "Pass"
                    if result.ap_version != "0.6.7":
                        raise AssertionError(
                            f"expected AP 0.6.7, spoiler reports {result.ap_version}"
                        )
                    spheres = sphere_evaluator(result.playthrough, result.identity)
                    required_broad_states = validate_progression_choices(spheres)
                    row.update(
                        status="Pass",
                        ap_version=result.ap_version,
                        layout_digest=result.identity.layout_digest,
                        total_pre_goal_states=spheres.total_pre_goal_spheres,
                        broad_pre_goal_states=(
                            spheres.multi_location_pre_goal_spheres
                        ),
                        required_broad_pre_goal_states=required_broad_states,
                        reachable_unused_counts=spheres.location_counts,
                    )
                except Exception as error:
                    row.update(status="Fail", error=_concise_error(error))
                rows.append(row)
                if evidence_output is not None:
                    _checkpoint_matrix(evidence_output, rows, total)
                print(
                    f"[{completed_count}/{total}] {row['status']} "
                    f"{case.key} seed {seed}",
                    flush=True,
                )
                if row["status"] == "Fail":
                    return rows
    finally:
        shutil.rmtree(matrix_root)
    return rows


def verify_deterministic_identity(
    generator_command: tuple[str, ...],
    case: MatrixCase,
    *,
    temporary_parent: Path | None = None,
) -> dict:
    identity_root = Path(
        tempfile.mkdtemp(
            prefix="word-factori-ap067-identity-",
            dir=temporary_parent,
        )
    )
    try:
        players = identity_root / "players"
        players.mkdir()
        (players / "player.yaml").write_text(
            render_player_yaml(case, "WF_Identity_Discovery_Count"),
            encoding="utf-8",
        )
        runs = []
        for label, seed in (("repeat-a", 13000), ("repeat-b", 13000), ("different", 13001)):
            output = identity_root / label
            output.mkdir()
            run = run_generation(generator_command, players, seed, output)
            validate_generation_identity(run.identity, case)
            runs.append(run)
        compare_generation_identities(
            runs[0].identity,
            runs[1].identity,
            runs[2].identity,
        )
        return {
            "status": "Pass",
            "case": case.key,
            "repeat_seed": 13000,
            "different_seed": 13001,
            "repeat_layout_digest": runs[0].identity.layout_digest,
            "different_layout_digest": runs[2].identity.layout_digest,
            "repeat_level_order": runs[0].identity.level_order,
            "different_level_order": runs[2].identity.level_order,
            "stable_key_count": len(runs[0].identity.stable_keys),
            "ap_id_count": len(runs[0].identity.ap_ids),
        }
    finally:
        shutil.rmtree(identity_root)


def prepare_live_room(
    generator_command: tuple[str, ...],
    case: MatrixCase,
    *,
    seed: int,
    temporary_parent: Path | None = None,
) -> dict:
    live_root = Path(
        tempfile.mkdtemp(
            prefix="word-factori-ap067-live-",
            dir=temporary_parent,
        )
    )
    try:
        players = live_root / "players"
        output = live_root / "output"
        players.mkdir()
        output.mkdir()
        player_name = f"WF_Live_Discovery_Count_{seed}"
        yaml_path = players / "player.yaml"
        yaml_path.write_text(render_player_yaml(case, player_name), encoding="utf-8")
        result = run_generation(generator_command, players, seed, output)
        if result.ap_version != "0.6.7":
            raise AssertionError(f"live room used AP {result.ap_version}, not 0.6.7")
        validate_generation_identity(result.identity, case)
        return {
            "status": "Prepared; live gameplay pending",
            "seed": seed,
            "case": case.key,
            "player": player_name,
            "room_root": str(live_root.resolve()),
            "player_yaml": str(yaml_path.resolve()),
            "archive_path": str(result.archive_path.resolve()),
            "layout_digest": result.identity.layout_digest,
            "page_one_targets": list(result.identity.location_names[:6]),
        }
    except Exception:
        shutil.rmtree(live_root)
        raise


def compare_generation_identities(
    first: GenerationIdentity,
    repeat: GenerationIdentity,
    different_seed: GenerationIdentity,
) -> None:
    if (first.level_order, first.layout_digest) != (
        repeat.level_order,
        repeat.layout_digest,
    ):
        raise AssertionError("same-seed level order or layout digest changed")
    if first.level_order == different_seed.level_order:
        raise AssertionError("different seed did not change any page position")
    if first.stable_keys != different_seed.stable_keys:
        raise AssertionError("different seed changed the stable-key set")
    if first.ap_ids != different_seed.ap_ids:
        raise AssertionError("different seed changed the AP-ID set")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the Word Factori AP 0.6.7 generation matrix."
    )
    parser.add_argument(
        "--generator",
        type=Path,
        default=Path(r"C:\ProgramData\Archipelago\ArchipelagoGenerate.exe"),
    )
    parser.add_argument("--evidence-output", type=Path)
    parser.add_argument("--seed-start", type=int, default=13000)
    parser.add_argument("--seed-end", type=int, default=13049)
    parser.add_argument("--live-seed", type=int, default=13050)
    parser.add_argument("--inspect-archive", type=Path)
    args = parser.parse_args()

    if args.inspect_archive is not None:
        identity = extract_generation_identity(args.inspect_archive, player=1)
        print(json.dumps(dataclasses.asdict(identity), indent=2, default=list))
        return 0
    if args.evidence_output is None:
        parser.error("--evidence-output is required unless --inspect-archive is used")
    if args.seed_end < args.seed_start:
        parser.error("--seed-end must be at least --seed-start")
    if not args.generator.is_file():
        parser.error(f"generator does not exist: {args.generator}")

    command = (str(args.generator.resolve()),)
    started = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    rows = execute_matrix(
        command,
        seeds=range(args.seed_start, args.seed_end + 1),
        evidence_output=args.evidence_output,
    )
    failures = sum(row["status"] == "Fail" for row in rows)
    expected_rows = len(MATRIX_CASES) * (args.seed_end - args.seed_start + 1)
    if failures or len(rows) != expected_rows:
        deterministic = {"status": "Pending; matrix stopped"}
        live = {"status": "Pending live test; matrix stopped", "seed": args.live_seed}
    else:
        try:
            deterministic = verify_deterministic_identity(command, MATRIX_CASES[2])
        except Exception as error:
            deterministic = {"status": "Fail", "error": _concise_error(error)}
        try:
            live = prepare_live_room(command, MATRIX_CASES[2], seed=args.live_seed)
        except Exception as error:
            live = {
                "status": "Blocked", "seed": args.live_seed,
                "error": _concise_error(error),
            }
    payload = {
        "started_at": started,
        "completed_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generator": str(args.generator.resolve()),
        "expected_ap_version": "0.6.7",
        "expected_word_factori_version": "1.3.0",
        "seed_range": [args.seed_start, args.seed_end],
        "matrix_summary": {
            "cases": len(rows),
            "passed": len(rows) - failures,
            "failed": failures,
        },
        "matrix_rows": rows,
        "deterministic_identity": deterministic,
        "live_room": live,
    }
    _write_json_atomic(args.evidence_output, payload)
    print(f"Evidence: {args.evidence_output.resolve()}")
    print(
        f"Matrix: {len(rows) - failures} pass, {failures} fail; "
        f"identity: {deterministic['status']}; live: {live['status']}"
    )
    return int(
        failures > 0
        or deterministic["status"] != "Pass"
        or live["status"] != "Prepared; live gameplay pending"
        or len(rows) != expected_rows
    )


if __name__ == "__main__":
    raise SystemExit(main())
