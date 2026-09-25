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

## 4. The board number was not instant either: `prepare()`'s own cost

<!-- Grounding: coordinator's own board run, 2026-09-24, system `766yhn3l...`
     (master `d87728a4` + this change's earlier commits installed),
     `theme-helper.service` confirmed reachable
     (`/run/shell/theme-helper.sock` exists, owned by `shell`). This is a
     board observation, the strongest grounding this project recognises. -->

Once 3.1b/3.2/3.3a were on the board, `k230-theme preview`/`activate` of an
*already-prepared* `catppuccin`/`catppuccin-latte` (a generation that
already existed, with its own `background.cache`) still took 3.95-4.26 s
each -- slower than the pre-daemon 2.8-3.5 s baseline, and
`journalctl -u theme-helper` showed no entries at all, because nothing on
this path had ever logged anything.

- [x] 4.1 Root-cause: `theme_activate.py`'s `prepare()` checked whether the
  destination generation already existed only at the very end of the
  function -- after staging every asset (a byte-for-byte copy of every
  background image), invoking `omarchy-theme-color --all` and
  `omarchy-theme-set-templates` (each itself spawning several `awk`/`sed`
  subprocesses), and (for a still background) building the wallpaper
  cache. All of that ran, and was discarded, on *every* call, even for a
  generation prepared thousands of times before. `theme_client.py`'s own
  `--helper-timeout-s` compounded this: its `0.3` s default was sized for
  the daemon's own Python-import savings, not for this real (if
  unnecessary) `prepare()` cost, so almost every `preview`/`activate`
  timed out waiting on a *working* daemon reply and fell back to the full
  in-process path -- paying the wasted timeout, the ~1.2 s import chain,
  and `prepare()`'s cost a second time. Confirmed on this host: a repeat
  `prepare()` for the same generation dropped from ~250-370 ms to ~2-3 ms
  once the identity check moved first; the daemon-vs-fallback confusion is
  fixed by widening the client timeout to `10.0` s (see `theme_client.py`'s
  own comment for the exact reasoning) and by `theme_helperd.py`'s new
  per-request timing making the daemon's own answer time directly visible
  instead of inferred.
- [x] 4.2 Fix: `theme_activate.py`'s `prepare()` now computes the
  generation identity (two content hashes plus a cheap background-name
  listing, no asset bytes copied and no external helper spawned) and
  checks for an existing destination *before* staging, invoking any
  `omarchy-theme-*` helper, or building a wallpaper cache. A cache hit
  returns the on-disk `report.json` (patched only for the one genuinely
  request-specific field, a since-removed remembered background) without
  touching `checked_copy`/`invoke`. Verify with `python3 -m unittest
  tests.test_omarchy_theme_activation` (adds
  `test_repeated_preparation_of_an_existing_generation_skips_staging_and_helpers`
  and `test_repeated_preparation_reports_a_newly_missing_remembered_background`,
  both asserting `checked_copy`/`invoke` raise if called on a cache hit).
- [x] 4.3 Fix: `theme_client.py`'s `DEFAULT_TIMEOUT_S` raised from `0.3` to
  `10.0`. Verify with `python3 -m unittest tests.test_theme_helper_daemon`
  (adds `test_client_stays_on_the_daemon_for_a_legitimately_slow_but_working_reply`,
  a daemon reply mocked to take 0.6 s -- past the old default, comfortably
  inside the new one -- asserting `theme_client.fallback` is never called).
- [x] 4.4 Instrumentation: a new `tools/theme_timing.py` (`Stopwatch` +
  `log()`) emits one `THEME_TIMING <component> <action> phase=Xms ...`
  line per request via `syslog` (never stdout/stderr, which
  `theme_catalog.rs`'s `command_error()` parses byte-for-byte as JSON on a
  nonzero exit -- seeing this in `journalctl` needs no code reading, only
  the exact commands in this change's evidence doc). Wired into
  `theme_activate.prepare()` (per-phase: hashes, background listing,
  cache hit/miss/race, staging, each external helper invocation, publish),
  `theme_transaction.exchange()` (per prepare/commit/rollback round trip,
  by endpoint), `theme_catalog.handle()` (per action, plus the deferred
  keyboard thread's own eventual completion), `theme_helperd.handle_line()`
  (request parse time and `self.lock` wait, separate from `handle()`'s own
  breakdown), and `theme_client.py` (which path was taken -- daemon or
  fallback -- and why a daemon attempt was abandoned, if it was). Also adds
  a `rust-shell <ms>ms theme-command <action> <id> duration=<ms>ms` line
  to `theme_catalog.rs`'s `execute()`, in the same shape
  `tools/theme-swap-jank.py`'s existing `RUST_LOG_RE` already parses, timing
  the chooser's own wait on the `k230-theme` subprocess. Verify with
  `python3 -m unittest tests.test_theme_timing` and `cargo test --offline`.
- [x] 4.5 Re-run the coordinator's own board commands (see this change's
  evidence doc) once 4.1-4.4 are installed, and confirm `activate` of an
  already-prepared theme is now well under 500 ms end to end, with
  `journalctl` showing the daemon path taken and `prepare()` reporting
  `cache=hit`. **Board result (coordinator, system `46vdy1dy...`):**
  `activate` 1.27-1.38 s (was ~4.2 s), `preview` warm 1.06-1.08 s;
  `THEME_TIMING` showed `handle activate` total 245 ms (`discover` 42,
  `prepare_entry` 73, `activate_generation` 128, keyboard-deferred
  dispatch 3.6), `helperd` total 265 ms, `client socket_round_trip` 270 ms
  `path=daemon`, `exchange` prepare 10-20 ms/commit 7-14 ms per receiver,
  `keyboard_deferred sync_and_restart` 300 ms off the critical path. This
  confirmed the daemon path itself is fast (~250-270 ms); the ~1.0 s
  remaining per call is the `theme_client.py` Python-interpreter-plus-
  `runuser` subprocess start-up the Rust chooser still pays for every
  request -- named explicitly as task 5's own starting point below.

Proof for 4.1-4.5: the tests named above (host), plus the board run above.

## 5. Talk to the daemon directly from the chooser; cut the remaining daemon cost

<!-- Grounding: coordinator's own board run above (system 46vdy1dy...):
     the daemon path itself already answers in ~250-270 ms; what remained
     was the Rust chooser's own subprocess-and-Python-interpreter cost to
     *reach* that daemon at all. -->

- [x] 5.1 `nix/rust-shell-client/src/theme_catalog.rs`'s `ThemeWorker`
  speaks `theme-helper.service`'s own line protocol directly over
  `K230_THEME_HELPER_SOCKET` (`/run/shell/theme-helper.sock`, matching
  `theme_client.py`'s `DEFAULT_SOCKET`; set explicitly in `nix/shell.nix`)
  -- the exact same JSON-line request/reply shape
  `tools/theme_client.py`/`tools/theme_helperd.py` already speak to each
  other, so there is no second, drifting protocol. On any socket problem
  (missing, refused, timed out, malformed reply) it falls back to the
  existing `k230-theme` subprocess unchanged, which itself still tries the
  same daemon and falls back further, so a socket that is merely slow to
  *start* still degrades no worse than before this task. An empty
  `K230_THEME_HELPER_SOCKET` disables the direct path entirely, matching
  `K230_THEME_COMMAND`'s own unset-env convention. Verify with `cargo
  test --offline --test theme_catalog_module` (5 new cases: a working
  socket reply is used without ever invoking the subprocess; a
  daemon-reported error is returned without retrying via the subprocess;
  a missing socket, and a malformed reply, both fall back to the
  subprocess; an empty socket path disables the direct attempt entirely
  -- each proven by a "poison" fake subprocess that marks a file if it
  ever actually runs).
- [x] 5.2 Cut `discover`'s ~42 ms: `theme_catalog.discover()` is now a
  cached wrapper (`_discover_uncached` does the real walk) keyed by
  `(user_themes, builtins)`, invalidated by a cheap stat-only fingerprint
  of exactly the directory levels `discover()` itself reads (each root's
  top level, and one level under a user entry's own `themes/` collection)
  -- never a content read or the identity-hashing/`find_preview()`/
  `resolve()` work `discover()` itself does. A bare CLI process only ever
  calls this once per invocation (empty cache, no behaviour change); the
  daemon serves many requests against a catalog that, in the normal
  preview-then-activate chooser flow, has not changed. Verify with
  `python3 -m unittest tests.test_theme_catalog` (adds
  `test_discover_is_cached_until_the_catalog_directory_actually_changes`,
  proving an unchanged catalog is not re-walked and that adding or
  removing a theme is still noticed on the very next call).
- [x] 5.3 Cut part of `prepare_entry`'s ~73 ms: `theme_activate.py`'s
  `helper_digest()` caches `source_digest(tools)` indefinitely, keyed by
  the tools directory's own resolved path. `tools` is
  `theme_helperd.py`'s own fixed `--tools` startup flag (a Nix store path
  in production), immutable for the daemon's whole lifetime, unlike the
  theme's own `source_hash` (deliberately left uncached: a person can edit
  their own theme's files while the daemon keeps running). Verify with
  `python3 -m unittest tests.test_omarchy_theme_activation` (adds
  `test_helper_digest_is_cached_across_repeated_preparations`, counting
  `source_digest` calls across two `prepare()` calls for the same tools
  path).
- [ ] 5.4 Re-run the coordinator's own board commands once 5.1-5.3 are
  installed, and confirm the chooser's own Apply-to-visible time. Expected,
  from the numbers above: `discover`/`prepare_entry` reduced by roughly
  their `helper_hash`/catalog-walk share (the theme's own `source_hash`
  and `activate_generation`'s 128 ms -- the two-phase exchange plus
  `app_appearance`/preference-commit filesystem work -- are unchanged by
  this task, deliberately: `activate_generation` is the part *load-bearing*
  for correctness, not a caching candidate), plus the direct socket
  removing essentially all of the ~1.0 s subprocess/Python start-up
  the coordinator's own board run isolated. This worktree's own honest
  estimate is close to, and may not fully clear, the ~150 ms target
  purely from `activate_generation`'s own remaining cost; the board run is
  what actually answers it. Needs the reserved board; not run by this task.

Proof for 5.1-5.3: the tests named above, all passing on this host; proof
for 5.4 is the reserved board, not run here.

Keep this change open (or split at review time into an explicit successor
per `AGENTS.md`) until 2.3, 3.4, and 5.4 have board results; 3.3b and 5.4
are named here so neither is silently dropped or claimed done without a
board result.
