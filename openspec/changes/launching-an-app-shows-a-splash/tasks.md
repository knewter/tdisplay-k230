## 1. Decisions

- [x] 1.1 Decide where the splash lives (client-owned overlay vs. a
  card-shell/`adapter.c` placeholder) and how a launched window is matched
  without relying on `app_id`; record both in `design.md`. Verify: the
  decisions are written down with the rejected alternative and why.

## 2. Splash state model and sway IPC (host-testable, no board)

- [x] 2.1 Implement `nix/rust-shell-client/src/splash.rs`: `Splash`/
  `SplashTarget`/`SplashStatus`, `fade_alpha`, `should_time_out`,
  `should_auto_dismiss_failed`, `pid_or_ancestor`, `window_event_matches`.
  Verify: `cargo test` in `nix/rust-shell-client` (this module's own tests
  cover launch->mapped, launch->timeout, launch->process-exit,
  already-running-needs-no-target, exact/bounded-descendant/cycle-safe pid
  matching, and monotonic fade easing).
- [x] 2.2 Implement `nix/rust-shell-client/src/sway_ipc.rs`: a minimal
  hand-rolled i3-ipc client (`write_message`, `try_parse_frame`,
  `watch_window_events`, `parse_window_event`, `parent_pid`,
  `process_alive`) matching the wire format
  `tests/card_shell_runtime.py`'s own `ipc()` helper already uses against a
  live sway. Verify: `cargo test` (frame parsing on partial/complete/
  malformed input, a real local Unix-socket round trip against a fake
  "sway", and `parent_pid`/`process_alive` against this host's own real
  `/proc`).

## 3. Rust client integration

- [x] 3.1 Capture the spawned process's pid via `gio::AppLaunchContext`'s
  `launched` signal in `launch_selected`; change `launch_selected`/
  `focus_or_launch` to return a `LaunchOutcome` (`Focused` vs.
  `Spawned(Option<pid>)`) instead of `()`. Verify: `cargo test` --
  `route_tests::launch_selected_captures_the_real_spawned_pid_with_no_glib_main_loop_running`
  proves the pid is captured from the real spawned process with no glib
  main loop running on this thread (the riskiest assumption this task
  makes, proven rather than assumed).
- [x] 3.2 Replace `launch_app`'s `self.hide()` with `start_splash`, which
  keeps an already-mapped overlay mapped (drawer taps) or maps it fresh
  (`launch_home_app`, Home/dock taps) and repaints it as the splash
  immediately; remove the old blind 3-second "reopen the drawer" timeout
  in favor of the splash's own `SplashStatus` transitions. Verify: `cargo
  test` (`route_tests::*`, unchanged existing tests plus the new ones)
  and `cargo clippy --all-targets` with no new warnings.
- [x] 3.3 Wire a `spawn_splash_watcher` background thread (started once
  `LaunchOutcome::Spawned`'s pid is known, not at the tap itself) that
  subscribes to `window` events and reports `SplashSignal::Matched`/
  `ProcessExited` back through an attempt-tagged channel, mirroring the
  existing `launch_sender`/`launch_results` staleness pattern. Verify:
  `cargo test` (`spawn_splash_watcher_ignores_events_with_no_swaysock_and_
  never_signals`, `splash_window_event_matches_by_pid_through_the_real_
  thin_wrapper`).
- [x] 3.4 Add `render::SplashParams`/`ensure_splash_bake`/`draw_splash`/
  `RendererCache::draw_splash`: an opaque, name/geometry/status-keyed
  cached backdrop plus a per-frame icon composite through the existing
  `IconCache`, and raise `icon.rs`'s decode size cap (128px -> 192px) to
  admit the splash's 176px icon. Verify: `cargo test` (bake-rebuilds-only-
  on-key-change, backdrop-opaque-on-first-frame, mismatched-canvas-
  rejected, failed-message-baked-distinctly, plus `icon.rs`'s own new
  176px-admits/oversize-rejects test).
- [x] 3.5 Make the splash dismissable by touch only while `TimedOut`/
  `Failed` (`input_region`/`down`/`up` special-cases), auto-dismiss
  `Failed` after `FAILED_AUTO_DISMISS`, and force a fast (~16ms) poll
  cadence while the icon is still fading in. Verify: `cargo test` passes
  with the full existing suite unchanged in behavior for every route this
  did not touch.

## 4. Host verification

- [x] 4.1 `cargo test` in `nix/rust-shell-client` -- verify: all 274 tests
  pass (221 lib + 18 `route_tests` (main.rs) + 14 appearance + 8
  background_decode + 8 service_data + 5 theme_catalog), including every
  new test this change adds.
- [x] 4.2 `cargo clippy --all-targets` in `nix/rust-shell-client` -- verify:
  no new warnings; every warning present afterward (`theme_ui.rs`,
  `wifi_ui.rs`, `theme_catalog.rs`, `service_data.rs`, and one pre-existing
  `main.rs:950` redundant-closure) is in a file/line this change did not
  touch.
- [x] 4.3 `nix build .#handheld-shell-rust --max-jobs 1 --cores 6` --
  verify: cross-builds to
  `/nix/store/71v0ssqfkp89yaw8ssxs2d08ysg97rbv-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
- [x] 4.4 `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`
  -- verify: builds to
  `/nix/store/xig229wz0brq1arjj35478gfr3kwcpcq-nixos-system-nixos-26.11.20260919.20b1ddd`.
- [x] 4.5 `python3 tools/blob-scan.py` -- verify: exits 0 (`every binary is
  accounted for`; this change adds only source files).

## 5. QEMU evidence (proves wiring under headless Pixman, not real glass)

- [ ] 5.1 Adapt a `tests/*qemu*.py`-style harness (following
  `tests/rust_home_screen_qemu.py`'s pattern: the unwrapped sway from
  `nix-store -qR` of the built `card-shell`/`sway` package, a private
  fixture desktop-entry catalog, `card_shell test-touch` synthetic
  input) to launch a fixture app, capture the splash within the first
  frame after the tap, and capture the hand-off once a fixture Wayland
  client (matching `tests/card_shell_runtime.py`'s `start_client` pattern)
  maps its window. Verify: a committed splash screenshot under
  `docs/evidence/launch-splash/qemu/` with the exact command and blob-
  inventory row, or this task stays open with the specific blocker
  recorded here if a real mapped-window fixture proves impractical under
  this harness in one sitting.

## 6. Board acceptance (hardware-only; stays open)

- [ ] 6.1 On the physical board, record a native capture of the splash
  appearing within one frame of a real finger tap (drawer, Home, and
  dock), with no visible flash of the previously active app -- verify with
  `python3 tools/capture-feature.py launch-splash --provenance real-touch
  --output-dir docs/evidence/launch-splash/real-touch` (or the equivalent
  current capture tool), reviewed against native state, not camera
  impression alone.
- [ ] 6.2 On the physical board, record a real `Terminal=true` launch
  (e.g. the existing Terminal entry) mapping as `foot` and the splash
  correctly handing off despite the `app_id` mismatch -- verify with a
  console/native capture showing the matched pid and the resulting focused
  `foot` window.
- [ ] 6.3 On the physical board, record the `TimedOut` and `Failed` states:
  an artificially slow/failing launch (e.g. a fixture desktop entry
  pointing at a sleeping or immediately-exiting command) reaching each
  state, and a real finger dismissing `TimedOut` by tap -- verify with a
  native capture and console log of the resulting `SplashStatus`
  transitions.

## 7. Proposal validation

- [x] 7.1 Validate this change -- verify: `openspec validate
  launching-an-app-shows-a-splash --strict` passes.
