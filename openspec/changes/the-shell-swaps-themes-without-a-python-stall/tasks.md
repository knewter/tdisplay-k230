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
- [x] 3.1b The actual in-memory buffer swap on commit, on both receivers:
  - Rust chooser (`background_decode.rs`): `BackgroundCache` was a
    single-slot cache, so browsing a *different* candidate (task 3.2, or
    the Preview page's own background carousel) evicted an
    already-prepared one before its own commit landed, falling back to a
    `background.cache` file read. It is now a small bounded LRU
    (`CACHE_CAPACITY = 4`), so commit is a guaranteed in-memory hit for
    any of the last few prepared candidates, not just the single most
    recent. Verify with `cargo test --offline --test
    background_decode_module` (adds
    `multiple_recent_candidates_stay_warm_without_evicting_each_other`).
  - Compositor (`nix/card-shell/appearance.c`/`adapter.c`): `appearance.c`
    gained an advisory `card_appearance_prepare_fn` hook, called once per
    successfully validated `prepare`, before its ack (never able to affect
    prepare's own accept/reject decision). `adapter.c`'s
    `appearance_prepare` uses it to pre-build the deck's gradient
    (`card_brush_scene`) for the *candidate* generation, disabled/detached
    until a matching commit; `appearance_canvas_refresh` adopts it at
    commit (destroy old, promote pointer, enable+position) instead of
    repainting, falling back to today's inline build whenever nothing
    warm matches (dimension/brush/generation changed, or nothing was
    prepared ahead) -- purely advisory, like `background.cache` itself.
    Verify with `python3 -m unittest tests.test_card_shell_appearance`
    (extended for the new `PREPARE` hook line) and `nix build --no-link
    --print-out-paths --max-jobs 1 --cores 6 .#card-shell` (real
    wlroots/Sway types; this task's C changes cannot be host-unit-tested
    beyond the protocol-level hook).
- [x] 3.2 Call `prepare_only()` (3.1a) as a theme becomes the centred
  carousel item, before Apply. Implemented in `theme_ui.rs`
  (`ThemeView::poll_prepare_ahead`/`prepare_ahead_submitted`/
  `prepare_ahead_reply`) and wired from `main.rs`'s existing per-tick
  carousel-settle loop: once the centred index is unchanged for 220 ms
  with the carousel at rest (`!Carousel::is_animating()`), it submits the
  existing `ThemeRequest::Preview` (background id `None`) directly to the
  shared `ThemeWorker`, bounded to one in-flight warm-up at a time (the
  stricter half of "one or two"), and the very next settled index simply
  replaces the desired target rather than queuing a backlog --
  "cancelled on scroll-away" in the sense that a candidate passed through
  while still moving, or superseded before its debounce elapsed, is never
  submitted. Its reply is recognised by `prepare_ahead_reply` and
  discarded before `ThemeView::accept` ever sees it, so it can never
  navigate or repaint the chooser. Reuses the existing `preview` action
  (already calling `prepare_only()` per 3.1a) rather than adding a new
  verb or protocol. Verify with `cargo test --offline --lib theme_ui`.
- [x] 3.3a Defer `wvkbd` recolour/restart until after the visible swap
  commits and this response is otherwise ready, so it never blocks
  `activated: true`. `theme_catalog.py`'s `activate` action now reports
  `keyboard_appearance: {"state": "deferred"}` immediately and runs
  `keyboard_appearance.sync_and_restart` on a background (non-daemon)
  thread; `theme-helper.service`'s request loop sends its reply the
  moment `handle()` returns, independent of that thread, so the
  daemon-served path drops this cost entirely, while a bare CLI
  subprocess is unaffected (the interpreter already waits for a
  non-daemon thread at process exit, so its total wall-clock time is
  unchanged). Verify with `python3 -m unittest tests.test_theme_catalog`
  (adds `test_activate_reports_keyboard_sync_as_deferred_but_it_still_completes`).
- [ ] 3.3b Defer Foot recolour the same way. Not started -- `foot`'s own
  recolour (`tools/app_appearance.py`) is folded into
  `activate_generation()`'s own `app_sync` call (inside
  `theme_transaction.py`, not `theme_catalog.py`), whose return value
  (`app_appearance`'s `state`) is part of that function's existing,
  tested, synchronous return contract; deferring it needs either
  restructuring that contract or a second, separate deferred call, which
  this task deliberately left alone given the risk of touching a
  load-bearing two-phase-transaction return value under this task's
  budget. In practice its OSC recolour is opt-in and scoped to a caller
  invoked from within a Foot session (see `app_appearance.py`'s own doc),
  which `k230-theme activate` is not, so the config-file write this path
  actually does is small; still an open cost, not claimed fixed here.
- [ ] 3.4 Re-run `tools/analyze-theme-swap-jank.py`'s tap-to-visible metric
  against the board once 3.1b/3.2/3.3 land, and report against the ~100 ms
  target. Needs the reserved board; 3.1b/3.2/3.3a landed above, 3.3b is
  the one remaining piece of "3.3" left open.

Keep this change open (or split at review time into an explicit successor
per `AGENTS.md`) until 2.3 and 3.4 have board results; 3.3b is named here
so it is not silently dropped, not claimed as done.
