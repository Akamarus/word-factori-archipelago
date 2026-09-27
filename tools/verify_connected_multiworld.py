"""Opt-in AP 0.6.7 connected acceptance. No game, GUI, public server or real saves.

The controller stages trusted AP source and a packaged world into a NEW directory.
The worker runs real generation, MultiServer, CommonClient and WordFactoriContext.
Only the proprietary game boundary (installation bytes, acknowledgment, completions)
is simulated. Never import this worker into the normal mocked unit-test process.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import functools
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = {"offline_completion", "client_restart", "duplicate_checks", "item_replay",
            "tracker_reconstruction", "page_gates", "victory", "cross_player_delivery"}


def create_run_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)
    (path / ".wf-connected-test").write_text("isolated acceptance workspace\n", encoding="utf-8")


def stage_core(source: Path, target: Path) -> None:
    for name in ("Utils.py", "Generate.py", "Main.py", "MultiServer.py", "CommonClient.py"):
        if not (source / name).is_file():
            raise ValueError(f"AP source is missing {name}")
    target.mkdir()
    # Explicit core allowlist by file type/directory: no settings, installed worlds,
    # caches, user patches or saves. The source checkout is never modified/imported.
    for path in source.glob("*.py"):
        shutil.copyfile(path, target / path.name)
    (target / "worlds").mkdir()
    for path in (source / "worlds").glob("*.py"):
        shutil.copyfile(path, target / "worlds" / path.name)
    for relative in ("worlds/generic", "rule_builder"):
        shutil.copytree(source / relative, target / relative,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


async def wait_until(predicate, description: str, timeout: float = 15) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(description)
        await asyncio.sleep(.02)


def validate_report(report: dict) -> None:
    players = report.get("players", [])
    if (report.get("status") != "pass" or not COVERAGE <= set(report.get("coverage", [])) or len(players) != 2
            or not all(p.get("expected", 0) > 0 and p.get("checked") == p.get("expected") and p.get("goal") for p in players)
            or report.get("cross_player_deliveries", 0) < 1
            or report.get("tracker_comparisons", 0) < 3
            or report.get("page_gate_observations", 0) < 1
            or report.get("replay_rounds", 0) < 1):
        raise ValueError("incomplete connected acceptance coverage")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def player_yaml(name: str, progressive: bool) -> str:
    return f"""name: {name}
game: Word Factori
Word Factori:
  accessibility: full
  custom_level_set: {'discovery_labs' if progressive else 'core_campaign'}
  goal: {'final_factory' if progressive else 'campaign_count'}
  campaign_count: 25
  recipe_checks: {str(progressive).lower()}
  progressive_machines: {str(progressive).lower()}
  type_a_word_checks: true
  type_a_word_count: 3
  type_a_word_words: ['JACK', 'ISLAND', 'AP', 'WORD', '99']
"""


def worker_setup(run: Path, dependency_path: str | None, seed: int):
    # Configure isolated paths before importing any AP/client code.
    if dependency_path:
        sys.path.insert(0, dependency_path)
    sys.path.insert(0, str(run / "ap"))
    os.chdir(run)
    os.environ["SKIP_REQUIREMENTS_UPDATE"] = "1"
    os.environ["KIVY_NO_ARGS"] = "1"
    import Utils
    if Utils.__version__ != "0.6.7":
        raise ValueError("This acceptance runner requires official AP 0.6.7 source")
    for func, folder in ((Utils.user_path, "ap-user"), (Utils.home_path, "ap-user"),
                         (Utils.cache_path, "cache")):
        func.cached_path = str(run / folder)
        (run / folder).mkdir(exist_ok=True)
    world_dir = run / "ap-user" / "worlds"
    world_dir.mkdir()
    shutil.copyfile(run / "word_factori.apworld", world_dir / "word_factori.apworld")
    (run / "ap-user" / "host.yaml").write_text("{}\n", encoding="utf-8")
    import logging
    logging.basicConfig(level=logging.WARNING)
    import Generate
    import Main
    players = run / "players"
    players.mkdir()
    for number, (name, progressive) in enumerate((("NormalFactory", False), ("ProgressiveFactory", True)), 1):
        (players / f"{number}.yaml").write_text(player_yaml(name, progressive), encoding="utf-8")
    args = Generate.mystery_argparse(["--player_files_path", str(players), "--seed", str(seed),
                                    "--outputpath", str(run / "generated"), "--spoiler", "3"])
    rolled, seed = Generate.main(args)
    world = Main.main(rolled, seed)
    import worlds.word_factori as wf
    if ".apworld" not in wf.__file__:
        raise AssertionError("acceptance must exercise the packaged APWorld")
    return world, wf


class SimulatedGame:
    """Files at the verified game/client boundary, not a puzzle solver or game emulator."""
    def __init__(self, run: Path, player: int, wf, game_root: Path):
        from worlds.word_factori import enhanced_runtime as runtime
        from worlds.word_factori.platform_paths import InstallationPaths, save_installation
        self.wf = wf
        base = game_root / str(player)
        prefix = base / "pfx"
        self.factori = (prefix / "drive_c/users/steamuser/AppData/Local/factori"
                        if sys.platform.startswith("linux") else base / "factori")
        self.factori.mkdir(parents=True)
        game = base / "game/data.win"
        game.parent.mkdir()
        game.write_bytes(b"simulated patched game - never executable")
        backup = game.with_name("data.wf-ap-original.win")
        backup.write_bytes(b"simulated original game - never executable")
        self.paths = InstallationPaths(game, prefix, self.factori)
        self.config = base / "installation.json"
        if sys.platform.startswith("linux"):
            save_installation(self.paths, self.config)
        self.mod = self.paths.mod_folder
        self.mod.mkdir(parents=True)
        self.save = self.factori / "test-account/mods/word factori archipelago/save.json"
        self.slot = {"slot_is_active": 1, "random_id": f"connected-test-{player}",
                     "beaten_levels": {}, "recipes": {}, "words": {}}
        self.completed_codes = set()
        self.flush()
        write_json(self.factori / "user_ref.json", {"most_recent_steam": "test-account"})
        write_json(self.factori / "mods.json", {"folder": "mods\\word factori archipelago"})
        write_json(self.mod / runtime.RECEIPT_NAME, {
            "protocol": runtime.PATCH_PROTOCOL, "capability": runtime.ENFORCEMENT_CAPABILITY,
            "original_sha256": runtime.ORIGINAL_SHA256, "patched_sha256": runtime.PATCHED_SHA256,
            "game_data": str(game), "platform": "linux", "prefix": str(prefix),
            "factori_root": str(self.factori), "ap_worlds": str(run / "ap-user/worlds"),
        })

    def flush(self):
        write_json(self.save, {"slots": {"0": self.slot}})

    def acknowledge(self, ctx):
        from worlds.word_factori.enhanced_runtime import runtime_context
        from worlds.word_factori.word_orders import checks_contract_digest
        write_json(self.mod / "archipelago_native_status.json", runtime_context(
            hashlib.sha256(ctx.current_identity().encode()).hexdigest(), ctx.slot_data["layout_digest"],
            checks_contract_digest(ctx.slot_data), progressive=ctx.slot_data.get("progressive_machines") is True))

    def complete(self, ctx, codes):
        from worlds.word_factori.recipe_checks import RECIPE_CHECKS
        campaign = {loc.code: loc for loc in ctx.active_locations()}
        recipes = {check.code: check for check in RECIPE_CHECKS}
        words = {order.code: order for order in ctx.selected_campaign().word_orders}
        for code in codes:
            if code in campaign:
                self.slot["beaten_levels"][str(campaign[code].slot_index)] = 1
            elif code in words:
                self.slot["words"][words[code].word] = {"buildings": 1, "cycles": 1, "extra_letters": 0}
            elif code in recipes:
                recipe = recipes[code]
                self.slot["recipes"].setdefault(recipe.machine, {})[" ".join(recipe.inputs)] = recipe.output
            else:
                raise AssertionError(f"unknown completion {code}")
            self.completed_codes.add(code)
        self.flush()

    def page_open(self, location) -> bool:
        # Test-side physical page model. Real native UI/page handling is not run.
        beaten = {int(i) for i in self.slot["beaten_levels"]}
        return all(sum(i in beaten for i in range(page * 6, page * 6 + 6)) >= 4
                   for page in range(location.page_index))


def restore_tracker(original, wf):
    from BaseClasses import CollectionState, MultiWorld
    multi = MultiWorld(1)
    multi.set_seed(900001)
    multi.game[1] = wf.GAME
    multi.player_name = {1: "Tracker"}
    multi.re_gen_passthrough = {wf.GAME: wf.WordFactoriWorld.interpret_slot_data(original.fill_slot_data())}
    world = wf.WordFactoriWorld(multi, 1)
    multi.worlds[1] = world
    world.options = copy.deepcopy(original.options)
    multi.state = CollectionState(multi)
    world.generate_early()
    world.create_regions()
    world.set_rules()
    if original.fill_slot_data() != world.fill_slot_data():
        raise AssertionError("tracker reconstructed a different room contract")
    return multi


def delivered_state(world, clients, *, tracker_player=None):
    from BaseClasses import CollectionState
    state = CollectionState(world)
    # Initial items also arrive through ReceivedItems; do not count them twice.
    for counts in state.prog_items.values():
        counts.clear()
    for player, ctx in clients.items():
        if tracker_player is not None and player != tracker_player:
            continue
        target = 1 if tracker_player is not None else player
        for received in ctx.items_received:
            name = ctx.item_names.lookup_in_game(received.item)
            state.collect(world.worlds[target].create_item(name), True)
    return state


async def connected_run(run, generated, wf, game_root, seed):
    import MultiServer
    from NetUtils import ClientStatus
    from worlds.word_factori.client import WordFactoriContext
    from worlds.word_factori.overlay_preferences import OverlayPreferences
    from worlds.word_factori import enhanced_runtime as runtime
    from unittest.mock import patch

    class ObservedClient(WordFactoriContext):
        # Observe completion of the REAL async reconciliation, not merely packet
        # arrival. No message handling or state transitions are replaced.
        reconciled_item_packets = 0

        async def _received_items_reconcile(self, *args, **kwargs):
            await super()._received_items_reconcile(*args, **kwargs)
            self.reconciled_item_packets += 1

    report = {"status": "running", "ap_version": "0.6.7", "seed": seed,
              "apworld_sha256": hashlib.sha256((run / "word_factori.apworld").read_bytes()).hexdigest(),
              "coverage": [], "tracker_comparisons": 0, "page_gate_observations": 0, "replay_rounds": 0,
              "simulation": ["installation fixture", "native acknowledgment", "completion journals", "physical page model"],
              "not_tested": ["native puzzle solving", "GUI/Proton", "Universal Tracker UI", "sustained performance"],
              "spheres": []}
    server = MultiServer.Context("127.0.0.1", 0, "", "", 1, 10, False)
    archives = list((run / "generated").glob("*.zip"))
    if len(archives) != 1:
        raise AssertionError("expected one generated room")
    server.load(str(archives[0]))
    server.init_save(False)
    trackers = {p: restore_tracker(generated.worlds[p], wf) for p in (1, 2)}
    listener = await MultiServer.websockets.serve(functools.partial(MultiServer.server, ctx=server), "127.0.0.1", 0)
    address = f"ws://127.0.0.1:{listener.sockets[0].getsockname()[1]}"
    clients, games = {}, {}
    errors = []
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: errors.append(str(context.get("exception", context))))
    # Only the unavailable game's binary identity is replaced. Receipt validation,
    # room binding, scan/reconciliation, socket traffic and state persistence stay real.
    with patch.object(runtime, "ORIGINAL_SHA256", hashlib.sha256(b"simulated original game - never executable").hexdigest()), \
         patch.object(runtime, "PATCHED_SHA256", hashlib.sha256(b"simulated patched game - never executable").hexdigest()):
        try:
            for player in (1, 2):
                games[player] = SimulatedGame(run, player, wf, game_root)

            async def connect(player):
                game = games[player]
                # LOCALAPPDATA is isolated BEFORE construction on Windows; Linux
                # receives an explicit isolated installation configuration.
                os.environ["LOCALAPPDATA"] = str(game.factori.parent)
                ctx = ObservedClient(address, None, installation_config=game.config)
                ctx.overlay_preferences = OverlayPreferences(enabled=False)
                clients[player] = ctx
                ctx.username = generated.player_name[player]
                await ctx.connect(address)
                await wait_until(lambda: ctx.slot == player and ctx.connected_identity is not None
                                 and ctx.compatible_campaign() and bool(ctx.items_received), "client authentication")
                game.acknowledge(ctx)
                await ctx.scan_once()
                return ctx

            for player in (1, 2):
                await connect(player)

            async def settled():
                try:
                    await wait_until(lambda: all(
                        set(ctx.checked_locations) == server.location_checks[0, p]
                        and games[p].completed_codes <= server.location_checks[0, p]
                        and list(ctx.items_received) == server.start_inventory[p] + server.received_items[0, p, True]
                        and len([i for i in ctx.bridge_state.applied if i >= 0]) == len(ctx.items_received)
                        and not ctx.bridge_state.pending_checks for p, ctx in clients.items()), "check/item reconciliation")
                except TimeoutError:
                    print("Reconciliation state:", {p: {"client_items": len(c.items_received),
                          "server_items": len(server.received_items[0,p,True]), "applied": c.bridge_state.applied,
                          "pending": list(c.bridge_state.pending_checks), "error": c.last_bridge_error}
                          for p,c in clients.items()}, flush=True)
                    raise
                if errors:
                    raise AssertionError(f"background task errors: {errors}")
                if any(ctx.last_overlay_persistence_error or ctx.last_bridge_error for ctx in clients.values()):
                    raise AssertionError("client reported a bridge or persistence error")
                for p, ctx in clients.items():
                    completed = games[p].completed_codes
                    campaign = ctx.active_locations()
                    # Independently check the two configured goals against actual
                    # fixture completions, never against merely reachable checks.
                    earned = (sum(loc.code in completed for loc in campaign if loc.kind != "discovery") >= 25
                              if p == 1 else any(loc.code in completed for loc in campaign
                                                 if loc.stable_key == "pitchfork-final"))
                    if server.client_game_state[0, p] == ClientStatus.CLIENT_GOAL and not earned:
                        raise AssertionError(f"premature victory for player {p}")

            await settled()
            offline_done = False
            for sphere in range(100):
                state = delivered_state(generated, clients)
                batches = {}
                for p, ctx in clients.items():
                    original_reachable = {loc.address for loc in generated.get_locations(p)
                                          if loc.address is not None and loc.can_reach(state)}
                    tracker_state = delivered_state(trackers[p], clients, tracker_player=p)
                    tracker_reachable = {loc.address for loc in trackers[p].get_locations(1)
                                         if loc.address is not None and loc.can_reach(tracker_state)}
                    if original_reachable != tracker_reachable:
                        raise AssertionError(f"tracker reachability mismatch in sphere {sphere}, player {p}")
                    report["tracker_comparisons"] += 1
                    campaign = {loc.code: loc for loc in ctx.active_locations()}
                    allowed = original_reachable - set(ctx.checked_locations)
                    blocked = {code for code in allowed if code in campaign and not games[p].page_open(campaign[code])}
                    report["page_gate_observations"] += len(blocked)
                    batches[p] = allowed - blocked
                if not any(batches.values()):
                    if all(not ctx.missing_locations for ctx in clients.values()):
                        break
                    raise AssertionError(f"progression deadlock: remaining {[len(c.missing_locations) for c in clients.values()]}")
                report["spheres"].append({str(p): sorted(codes) for p, codes in batches.items()})
                # Complete reachable checks with the second client offline; submit
                # player one's checks while that client is away as well.
                if not offline_done and batches[2]:
                    old = clients[2]
                    old_identity = old.connected_identity
                    old_binding = old.bridge_state.game_slot_id
                    await old.shutdown()
                    clients.pop(2)
                    games[2].complete(old, batches[2])
                    games[1].complete(clients[1], batches[1])
                    await clients[1].scan_once()
                    new = await connect(2)
                    if new.connected_identity != old_identity or new.bridge_state.game_slot_id != old_binding:
                        raise AssertionError("client restart lost room/save binding")
                    offline_done = True
                    report["coverage"] += ["offline_completion", "client_restart"]
                else:
                    for p, codes in batches.items():
                        games[p].complete(clients[p], codes)
                        await clients[p].scan_once()
                await settled()
                before = {p: tuple(ctx.items_received) for p, ctx in clients.items()}
                applied_before = {p: dict(ctx.bridge_state.applied) for p, ctx in clients.items()}
                allowances_before = {p: json.loads((games[p].mod / runtime.RUNTIME_NAME).read_text())["machine_counts"]
                                     for p in clients}
                packet_counts = {p: ctx.reconciled_item_packets for p, ctx in clients.items()}
                for p, ctx in clients.items():
                    # Duplicate real network packets plus a full ReceivedItems
                    # replay from the real server (Sync); no fabricated item list.
                    await ctx.scan_once()
                    await ctx.send_msgs([{"cmd": "LocationChecks", "locations": sorted(batches[p])}, {"cmd": "Sync"}])
                await wait_until(lambda: all(ctx.reconciled_item_packets > packet_counts[p]
                                             for p, ctx in clients.items()), "full item replay acknowledgment")
                await settled()
                if any(tuple(ctx.items_received) != before[p] or dict(ctx.bridge_state.applied) != applied_before[p]
                       or json.loads((games[p].mod / runtime.RUNTIME_NAME).read_text())["machine_counts"] != allowances_before[p]
                       for p, ctx in clients.items()):
                    raise AssertionError("duplicate checks/replay changed inventory")
                report["replay_rounds"] += 1
            else:
                raise AssertionError("sphere limit exceeded")
            await wait_until(lambda: all(server.client_game_state[0, p] == ClientStatus.CLIENT_GOAL for p in clients), "server victory")
            report["players"] = [{"player": p, "checked": len(server.location_checks[0, p]),
                                  "expected": len(ctx.active_check_codes()), "goal": True,
                                  "received": len(ctx.items_received)} for p, ctx in sorted(clients.items())]
            report["cross_player_deliveries"] = sum(item.player not in (0, p) for p, ctx in clients.items() for item in ctx.items_received)
            report["coverage"] += ["duplicate_checks", "item_replay", "tracker_reconstruction",
                                   "page_gates", "victory", "cross_player_delivery"]
            report["status"] = "pass"
            validate_report(report)
            return report
        finally:
            for ctx in clients.values():
                ctx.exit_event.set()
                await ctx.shutdown()
            listener.close()
            await listener.wait_closed()
            loop.set_exception_handler(previous_handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ap-source", type=Path)
    parser.add_argument("--apworld", type=Path, default=ROOT / "word_factori.apworld")
    parser.add_argument("--output", type=Path, required=True, help="NEW directory; never reuses existing output")
    parser.add_argument("--dependency-path", help="optional directory with already installed AP dependencies")
    parser.add_argument("--seed", type=int, default=160929)
    parser.add_argument("--timeout", type=int, default=180, help="worker deadline in seconds")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fixture-root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    run = args.output.resolve()
    if args.worker:
        try:
            if not (run / ".wf-connected-test").is_file() or args.fixture_root is None:
                raise ValueError("worker requires a controller-created workspace")
            generated, wf = worker_setup(run, args.dependency_path, args.seed)
            report = asyncio.run(connected_run(run, generated, wf, args.fixture_root.resolve(), args.seed))
            write_json(run / "report.json", report)
            return 0
        except Exception as error:
            traceback.print_exc()
            write_json(run / "report.json", {"status": "fail", "error": str(error)})
            return 1
    if args.ap_source is None or not args.apworld.is_file() or args.timeout <= 0:
        parser.error("provide AP source, an existing packaged APWorld, and a positive timeout")
    create_run_directory(run)
    stage_core(args.ap_source.resolve(), run / "ap")
    shutil.copyfile(args.apworld, run / "word_factori.apworld")
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--output", str(run), "--seed", str(args.seed)]
    if args.dependency_path:
        command += ["--dependency-path", str(Path(args.dependency_path).resolve())]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
                       SKIP_REQUIREMENTS_UPDATE="1", AP_NO_PROMPT="1")
    # The controller owns cleanup even if it has to terminate a timed-out worker.
    # Short fixture paths also avoid Windows' legacy path-length limit.
    with tempfile.TemporaryDirectory(prefix="wf-c-") as game_temp, \
         (run / "worker.log").open("w", encoding="utf-8") as log:
        command += ["--fixture-root", str(Path(game_temp).resolve())]
        try:
            result = subprocess.run(command, cwd=run, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=args.timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            write_json(run / "report.json", {"status": "fail", "error": "worker deadline exceeded"})
            print(f"FAIL: timed out; see {run / 'worker.log'}")
            return 1
    if result.returncode:
        print(f"FAIL: see {run / 'worker.log'}")
        return 1
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    validate_report(report)
    print(f"PASS: {sum(p['checked'] for p in report['players'])} checks, two server-confirmed goals; {run / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
