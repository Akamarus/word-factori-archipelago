# Linux Proton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Install from Linux and run the native AP client alongside Word Factori through Proton, without changing the gameplay contract.

**Architecture:** Shared platform paths underpin a native Python installer and client. Existing verified delta and Windows setup remain unchanged. Linux overlay is disabled with regular-client fallback.

**Tech Stack:** Python 3.12+ standard library, bash entry point, existing AP 0.6.7 client.

**Spec:** docs/superpowers/specs/2026-09-14-linux-proton-design.md

## Global Constraints

- No game saves are written; no telemetry or automatic diagnostic upload.
- Keep one player ZIP, one delta, same stable IDs and 1.4.0 campaign contract.
- Do not change installed game/client, push, merge, or publish.
- Linux uses the regular Archipelago client for items/chat.
- Preserve backup/hash validation; unknown binaries and unsafe targets are refused.
- Real Proton gameplay acceptance is separate and remains unverified.

### Task 1: Shared installation paths and discovery

**Files:** create word_factori/platform_paths.py and tests/test_platform_paths.py.

**Interfaces:** frozen InstallationPaths(game_data: Path, prefix: Path, factori_root: Path).
Properties mod_folder and local_app_data. Expose validate_installation(paths) -> InstallationPaths,
config_path(environ=None, home=None) -> Path, load_installation(path=None) -> InstallationPaths,
save_installation(paths, path=None) -> None, discover_installations(steam_roots=None) -> list[InstallationPaths],
resolve_proton_path(value: str, prefix: Path) -> Path, selected_proton_mod(payload, paths) -> bool.
Use local configuration schema 1 at XDG_CONFIG_HOME/word-factori-archipelago/installation.json
(absolute XDG only, otherwise ~/.config). Config contains absolute game_data, prefix, factori_root.

- [ ] Write filesystem tests first, including:

  ```python
  def test_relative_xdg_does_not_redirect_config(self):
      actual = config_path({"XDG_CONFIG_HOME": "relative"}, self.home)
      self.assertEqual(actual, self.home / ".config/word-factori-archipelago/installation.json")
  ```

  Cover round-trip descriptor validation, native/Flatpak roots, VDF additional libraries,
  app ID 2072840, spaced paths, absent/ambiguous users and prefixes, duplicates,
  malformed VDF, explicit descriptor, C:/ paths and drive mappings, traversal refusal,
  selected mod matching and unrelated paths. Tests create owned directories, not real Steam files.
- [ ] Run python -m unittest tests.test_platform_paths -v; record missing-feature failure.
- [ ] Implement dataclass, bounded VDF parser/discovery, validated configuration and path translation.
  Reject nonabsolute descriptors and game names other than data.win; validate on-disk
  prefix/drive_c/users/.../AppData/Local/factori relationship. Discovery returns all candidates,
  never silently chooses between users/installations. Mod relative paths are limited to
  this integration's mod name or mods/name; absolute Windows paths resolve inside the prefix
  and must match the selected mod. Unknown mappings and traversal are rejected.
- [ ] Run focused tests, self-review, commit only task files, write RED/GREEN report.

### Task 2: Linux transaction installer and local entry point

**Files:** create tools/install_linux.py, tools/linux_transaction.py, tests/test_linux_installer.py,
root Install Word Factori Archipelago.sh; reuse tools/enhanced_delta.py.

**Consumes:** Task 1 APIs verbatim. **Produces:** bash-invoked Python CLI with install (default),
verify, restore, uninstall, recover operations; explicit --game-data, --prefix, --factori-root,
--ap-worlds, --config, and --yes overrides. Python imports paths without requiring AP runtime.

- [ ] Write real temporary-file tests first. In fixture scope only, patch pinned hashes to
  small independently constructed original/patched byte strings and delta, leaving production
  safety code active. Assert outputs and actual file bytes, never just mock calls.

  ```python
  def test_bad_original_preserves_all_targets(self):
      self.game.write_bytes(b"unknown")
      before = self.snapshot()
      with self.assertRaises(ValueError):
          self.install()
      self.assertEqual(self.snapshot(), before)
  ```

  Cover first install, update, original restoration, uninstall preserving saves/backups,
  invalid hashes/receipt/config pairing, bad delta, permission errors, ambiguous discovery,
  running game, unavailable process inspection, failures between replacements and recovery
  after interruption. Include CLI subprocess verify/help/error behavior.
- [ ] Run focused tests and record missing-feature failure.
- [ ] Implement local interactive discovery/selection and explicit path overrides. Require
  existing native AP custom_worlds directory selection; never guess system install locations.
  Show destinations and confirm locally unless --yes; do not invoke sudo or package managers.
- [ ] Implement pinned compressed delta verification, full reconstruction/hash preflight,
  backup verification and native receipt. Record transaction journal/backups outside scanned mods;
  use same-filesystem staging, rollback on errors and explicit recovery of interrupted operations.
  Validate journal paths against selected descriptor before touching files. Restore before removing
  receipt/APWorld/mod; preserve saves, original and earlier backups. Refuse symlinked owned targets,
  hash changes, active processes, or uncertainty; never kill a game. Recheck before replacement.
- [ ] Run focused tests, self-review, commit task files, report evidence and exact CLI.

### Task 3: Client integration and honest readiness errors

**Files:** modify word_factori/client.py, enhanced_runtime.py, save.py; create
tests/test_linux_client.py; extend tests/test_enhanced_runtime.py and test_save_discovery.py.

**Consumes:** Task 1 descriptor and path functions. **Produces:** native Linux setup selection,
structured patch readiness and safe selected mod/save lookup; no Windows overlay spawn on Linux.

- [ ] Write regression tests against real client methods using existing AP test scaffolding.

  ```python
  def test_missing_patch_is_not_campaign_mismatch(self):
      # Use a valid bundled room and a missing installation receipt.
      self.prepare_room()
      self.ctx.prepare_selected_campaign()
      self.assertIn("patch", self.ctx.last_bridge_error.lower())
      self.assertNotIn("Campaign mismatch:", self.ctx.last_bridge_error)
  ```

  Also test missing config causes no guessed-directory writes, Linux receipt path validation,
  selected mod and active account containment, items/checks/reconnect/victory with configured
  fixture paths, and regular-client fallback without renderer launch.
- [ ] Run focused tests and record expected regressions.
- [ ] Integrate descriptor with Linux only; retain Windows LOCALAPPDATA default and interfaces.
  Add structured patch readiness with boolean compatibility wrapper for existing callers.
  Separate setup/patch errors from genuine manifest mismatches in all check/reporting paths.
  Disable Windows overlay before spawning on Linux, without impairing networking.
  Resolve native game metadata paths with selected prefix; enforce account/save containment.
- [ ] Run focused client/save/runtime tests, self-review, commit and report evidence.

### Task 4: Package, documentation, cross-platform checks

**Files:** modify tools/build_release.py, tools/verify_release.py if needed,
.github/workflows/verify.yml, README.md, word_factori/docs/setup_en.md;
create docs/linux-proton.md; extend tests/test_unified_distribution.py.

- [ ] Write package behavior tests that open built ZIP/APWorld and verify Linux entry point,
  helper dependencies, shared path module, and existing Windows files are present; prove failure
  before extending the allowlists.
- [ ] Include Python installer, transaction helper, decoder and shared path module in the same
  archive; installer loads the module from bundled APWorld without requiring Archipelago imports.
  Version stays a local 1.4.0 development artifact; never replace published ZIP.
- [ ] Document bash invocation, Python/native AP requirements, local selection, standard client,
  read-only verification, recovery/restore/uninstall, and experimental/unverified Proton status.
- [ ] Add Ubuntu CI for portable and Linux-specific tests; explicitly scope only genuinely
  Windows-only tests. Preserve Windows full suite; do not silently skip portable coverage.
- [ ] Run build, full Windows suite, release verifier, and available Linux runtime checks.
  Attempt a private original-game delta reconstruction test without installing or publishing bytes.
  Record unavailable Proton evidence honestly. Review whole branch, fix findings, leave local branch
  and archive for the user; no push/publish/install.
