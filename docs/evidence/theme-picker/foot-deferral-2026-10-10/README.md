# Foot update deferral: task 3.3b

Observed 2026-10-10T20:04:25.821694+00:00. Source `bcdb485080b43351ad9b9e28b873b6045467b539`, based on
`ef5b3ae872534c2147b0953bbd47fa4a4821865e`, branch
`closeout/theme-admission-2026-10-10`, worktree
`/home/jadams/tmp/k230-theme-admission-closeout-2026-10-10`.
Owned paths: `tools/theme_transaction.py`, `tools/theme_catalog.py`, their four
Python test files, Rust `theme_catalog.rs`/`theme_ui.rs` and transport test,
this evidence, and this change's planning/work-board records.
The guarded Nix build slot was used; no board or serial port was reserved.

## Behavior and contract

The catalogue opts into deferred app refresh after both receiver commits,
durable pointer/preference publication and activation-lock release. It returns
`activated: true` with `app_appearance: {"state": "deferred"}`. Direct
`activate_generation()` callers keep their synchronous applied/failed/superseded
result. Failed prepare, commit or preference publication dispatches no update.
A named non-daemon thread performs the existing adapter call; direct CLI/fallback
process exit waits for it. The adapter checks the expected generation under the
activation lock, so an old completion cannot overwrite a newer theme.

The shared adapter writes Foot terminal/monitor configs and its GTK keyfile.
This does not add terminal OSC broadcasts; the existing terminal follower is
separate. Completion/failure/supersession goes through the existing
`THEME_TIMING app_deferred` syslog channel. Background failure cannot roll back
an acknowledged shell or contaminate the JSON streams. The Rust parser accepts
`deferred` through both helper/socket and CLI fallback, and keeps the ordinary
Theme/Background applied confirmation; genuine app failures remain visible.

## Narrow proof

All commands ran in the owned worktree and exited zero:

```sh
python3 -m unittest tests.test_omarchy_theme_transaction tests.test_theme_catalog tests.test_theme_helper_daemon tests.test_handheld_app_themes
CARGO_TARGET_DIR=/home/jadams/tmp/k230-admission-host-target cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --test theme_catalog_module
CARGO_TARGET_DIR=/home/jadams/tmp/k230-admission-host-target cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib theme_ui
flock -n /tmp/k230-nix-build.lock nix build .#handheld-shell-rust .#handheld-theme-command --out-link /home/jadams/.local/state/tdisplay-k230/retained-builds/theme-foot-2026-10-10/candidate --print-out-paths --max-jobs 1 --cores 2
```

- Python: **70 tests pass**. The actual host helper socket returns activation
  and answers a subsequent list while the app adapter remains blocked behind
  an event. Releasing it writes both real Foot configs. Separate tests retain a
  newer theme against a delayed old update, log an adapter failure without shell
  rollback, and prevent dispatch after each of three activation failure stages.
  Existing synchronous-result, ACK, rollback and keyboard tests still pass.
- Rust transport: **6 tests pass**, including deferred activation through both
  socket and subprocess routes. Theme state: **28 tests pass**, including the
  existing failure message and new deferred-success case. These are host tests.
- Nix: the actual RISC-V Rust client and theme-command package are constructed.
  Installed Python module bytes and both native/cross Rust input files match the
  committed source. This is package proof, not execution on the physical board.

Rust client: `/nix/store/d187p77c4kilqbaakp2vzvy2c0smz973-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
Theme command: `/nix/store/nv2jwci4x38ip09yz2818wjm2rbbwcan-handheld-theme-command-0.1`.
[proof.json](proof.json) records all four outputs/derivations and source hashes.
Logs: [Python](python-tests.log), [Rust transport](rust-catalog-tests.log),
[theme state](rust-ui-tests.log), [package build](package-build.log).
The initial build was deliberately stopped before completion when the Rust
consumer's strict state allowlist was found; only the compatible final build
above qualifies this task.

## Build reuse and retention

The final plan builds four derivations: changed native and cross Rust clients,
bundled theme thumbnail/default generation, and the theme command. It rebuilds
no kernel, image or graphics stack. The parser compatibility source change
invalidates both Rust packages; the native one generates bundled thumbnails.
Its internal Cargo compilation still rebuilds locked crates as part of that
changed derivation. This is distinct from losing unchanged realized Nix outputs.

The verified previous farm's 10,357 paths are retained
and extended to **10,402**, adding
**45**. The union includes recursive sources and
all currently realized outputs in the selected two-package graph; unrealized
outputs are omitted, never built just for retention. `builtins.storePath`
registers real store dependencies in the link farm. Actual GC-root queries,
not symlink existence alone, prove the selected packages, native Rust and
vendor input are protected by the durable farm. All retained paths pass
`nix-store --check-validity`; global GC policy is unchanged.
[retention.json](retention.json) records the manifest hash and root checks.

A repeat `nix build .#handheld-shell-rust .#handheld-theme-command --dry-run
--no-link --max-jobs 1 --cores 2` exits zero with **0 builds and 0 fetches**.
[repeat-build.log](repeat-build.log) is its complete output (the dirty-tree
notice, if present, is not a build/fetch request).

## Remaining evidence gate

This closes task 3.3b's source/host/package work only. Deploy a coherent system
containing both the compatible Rust client and theme helper together; the helper
must not be updated alone while an older chooser still rejects `deferred`.
The standalone package built here is not a claim that the normal system closure
was built, installed or booted. Build that closure with
`nix build .#nixosConfigurations.k230.config.system.build.toplevel`, then use the
existing guarded coherent-shell board trial/qualification/install workflow.
No install, flash, new finger acceptance, camera observation or swap latency
measurement was obtained here. User acceptance of the previously installed
system does not identify these new artifacts.

After a coordinated deployment, the reserved operator can inspect identities
and the eventual app update without repeating a timing workload:

```sh
./tools/console.py /dev/ttyACM0 --wait=3 "systemctl show theme-helper.service -p ExecStart; pgrep -a k230-shell-rust; journalctl -u theme-helper.service -n 60 --no-pager"
```

Task 3.4 and the proposal's other named physical/profiling requirements remain
unchecked. The user deferred latency measurement; no timing run is requested or
claimed by this closeout. The proposal remains open.
