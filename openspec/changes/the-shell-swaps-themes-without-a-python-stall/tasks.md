## 1. Persistent theme-catalog helper

- [x] 1.1 Split `tools/theme_catalog.py`'s `main()` into a reusable
  `build_parser()`/`handle(args)` with no behavior change; verify with the
  existing `python3 -m unittest tests.test_theme_catalog` (10 cases, all
  still passing) and `tests/test_theme_commit_under_occlusion_runtime.py`'s
  subprocess invocation still working unmodified.
- [x] 1.2 Add `tools/theme_helperd.py`: a private-socket daemon that calls
  that exact parser/handler per request, survives a malformed request
  without wedging, and shuts down cleanly on SIGTERM. Verify with
  `python3 -m unittest tests.test_theme_helper_daemon`.
- [x] 1.3 Add `tools/theme_client.py`: an argv-compatible front end that
  tries the daemon first without importing `theme_catalog` eagerly, and
  falls back to the unmodified in-process path otherwise. Verify the
  import-avoidance itself with the `-X importtime` subprocess case in
  `tests/test_theme_helper_daemon.py`, and correctness/fallback with the
  rest of that file.
- [x] 1.4 Wire `nix/shell.nix`'s `theme-helper.service` (guarded by
  `cfg.coherentShell`, same posture as `shell-ui.service`) and point
  `nix/handheld-theme-command.nix`'s `k230-theme` wrapper at
  `theme_client.py`. Verify with `nix build --no-link --print-out-paths
  --max-jobs 1 --cores 6 .#handheld-theme-command` and a manual run of the
  built `k230-theme-helperd`/`k230-theme` pair under `qemu-riscv64-static`
  (see `docs/evidence/omarchy-themes/theme-swap-jank/README.md`).

Proof: `python3 -m unittest tests.test_theme_catalog tests.test_theme_helper_daemon`
and the `nix build` above.

## 2. Measure jank, not just latency

- [x] 2.1 Add `tools/theme-swap-jank.py`, a root board-side capture tool:
  triggers a swap, samples per-process CPU from `/proc`, and collects a
  merged wall-clock timeline from the Rust shell's own `commit`/
  `wallpaper-commit`/`frame-done` log lines and `K230_CARD_SHELL` sway_log
  lines via `journalctl -o json`. Verify with `python3
  tools/theme-swap-jank.py --self-test`.
- [x] 2.2 Add `tools/analyze-theme-swap-jank.py`: frame-interval histogram,
  gaps over 33/50/100 ms with bounding-event context, the longest stall and
  its surrounding events, tap-to-visible latency against a configurable
  target, and per-process CPU. Verify with `python3
  tools/analyze-theme-swap-jank.py --self-test`.
- [ ] 2.3 Run the capture tool on the reserved board across a
  representative swap (a bundled dark theme, a bundled light theme, and one
  community theme with a still background), before and after this change's
  `theme-helper.service` lands on an installed system. Record
  `docs/evidence/omarchy-themes/theme-swap-jank/README.md` with the exact
  `journalctl`/board commands and both reports. **Needs the reserved
  board; not run by this change.**

Proof for 2.1/2.2: the two tools' own `--self-test`. Proof for 2.3: the
committed before/after JSON reports and the exact board commands that
produced them.

## 3. Explicit remainder (successor work, partially started here)

- [x] 3.1a Expose the clean prepare-ahead API: `tools/theme_transaction.py`'s
  `prepare_only(generation, ...)` sends the two-phase protocol's existing
  "prepare" message (the same one `activate_generation()` already sends
  immediately before every commit -- `appearance.rs`'s Prepare handling
  already decodes/caches the wallpaper there) without committing, taking
  no lock, safe to call repeatedly for different candidates. Wired into
  `theme_catalog.py`'s `preview` action so browsing already warms both
  receivers when `--rust-socket`/`--deck-socket` are configured. Verify
  with `python3 -m unittest tests.test_omarchy_theme_transaction
  tests.test_theme_catalog`.
- [ ] 3.1b The actual in-memory buffer swap on commit: even with 3.1a's
  warm-up, `activate`'s commit still calls `BackgroundCache::render` in
  the Rust event loop, which is a cache-hit file read, not a zero-copy
  pointer swap of an already-in-process buffer. Owned by the wallpaper/
  appearance-apply path (this change's lane), not started.
- [ ] 3.2 Call `prepare_only()` (3.1a) as a theme becomes the centred
  carousel item, before Apply. Owned by the chooser UI
  (`theme_carousel.rs`/`theme_ui.rs`), explicitly out of this change's
  owned paths -- 3.1a is the "clean API" left for that hook.
- [ ] 3.3 Defer `wvkbd`/Foot recolour until after the visible swap commits,
  so neither blocks `activated: true`. Not started.
- [ ] 3.4 Re-run `tools/analyze-theme-swap-jank.py`'s tap-to-visible metric
  against the board once 3.1b/3.2/3.3 land, and report against the ~100 ms
  target. Needs the reserved board and 3.1b/3.2/3.3.

Keep this change open (or split at review time into an explicit successor
per `AGENTS.md`) until 2.3 has a board result; 3.1b-3.4 are named here so
they are not silently dropped, not claimed as this change's own scope.
