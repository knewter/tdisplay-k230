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
- [x] 5.4 Re-run the coordinator's own board commands once 5.1-5.3 are
  installed, and confirm the chooser's own Apply-to-visible time. **Board
  result (coordinator, system `phj9y4fggpb177b0hgaawbh510chhwil`, `master`
  `f4f75998`, `docs/evidence/omarchy-themes/instant-theme-swap/
  board-chooser-2026-09-25.md`):** `list` `path=socket` 166 ms, warm
  `preview` 206 ms, cold prepare-ahead (carousel opens) 4071 ms, tap
  Apply -> Rust `appearance-commit-accepted` 556 ms, `activate`
  `path=socket` 509 ms with helper breakdown `parse=65.0ms discover=2.0ms
  prepare_entry=90.6ms activate_generation=336.0ms` (handler total
  438.6 ms, helper total 504.1 ms). The direct socket removed essentially
  all of the ~1.0 s subprocess/Python start-up as predicted (roughly 8x
  faster than the pre-daemon baseline), but still misses the ~150 ms
  target: `activate_generation` re-runs the two-phase prepare exchange
  during Apply even though the chooser's own prepare-ahead already
  prepared that exact generation, and `parse`/`prepare_entry` cost more
  than a cache hit should. This is section 6's own starting point below.

Proof for 5.1-5.3: the tests named above, all passing on this host; proof
for 5.4 is the board run quoted above.

## 6. Skip the redundant re-prepare on Apply; cut per-request parse/hash cost; warm neighbours early

<!-- Grounding: coordinator's own board run above (system phj9y4fg...):
     activate_generation (336 ms) re-runs prepare against both receivers
     even when the chooser's own prepare-ahead already prepared that exact
     generation; parse costs 65 ms because theme_helperd.py rebuilt an
     argparse.ArgumentParser on every request; prepare_entry costs 91 ms
     partly from rehashing the theme's own source tree on every call even
     when nothing on disk changed since the last prepare. -->

- [x] 6.1 Root-cause: `theme_helperd.py`'s `Helperd.handle_line()` called
  `theme_catalog.build_parser()` (constructing a fresh `argparse.
  ArgumentParser`, with all its subparsers/actions) on *every* request,
  not once at daemon start -- the board's 65 ms `parse` phase was almost
  entirely this construction, not argument parsing itself. Fix: build the
  parser once in `Helperd.__init__()` and reuse it. Verify with
  `python3 -m unittest tests.test_theme_helper_daemon` (adds
  `test_the_argument_parser_is_built_once_not_once_per_request`, counting
  `build_parser` calls across several requests on one daemon instance).
- [x] 6.2 Root-cause (part of `prepare_entry`'s 91 ms): `theme_activate.
  prepare()` re-hashed the *theme's own* source tree
  (`source_digest(theme)`, a full content read/hash of every file) on
  every call, even for a generation prepared moments before by the same
  unchanged theme -- deliberately never cached before this task, because a
  person can edit their own theme's files while the daemon keeps running.
  Fix: `tools/theme_sources.py` gains `source_fingerprint(theme)`, a
  stat-only walk (name, size, `st_mtime_ns` per file, no content read) of
  exactly the same tree `source_digest()` walks; `theme_activate.
  theme_digest()` wraps `source_digest()` with a cache keyed by the
  theme's resolved path, invalidated only when `source_fingerprint()`
  itself changes -- so an edited file (which changes its size and/or
  mtime) is still re-hashed, and an unchanged theme is not. Verify with
  `python3 -m unittest tests.test_omarchy_theme_sources` (adds
  `test_fingerprint_matches_digest_sensitivity_without_reading_content`)
  and `tests.test_omarchy_theme_activation` (renames the existing digest-
  caching test to `test_theme_and_helper_digests_are_cached_across_
  repeated_preparations` and adds `test_theme_digest_cache_is_invalidated_
  by_an_edit_between_preparations`, editing a theme file between two
  `prepare()` calls and asserting a fresh digest/generation).
- [x] 6.3 Root-cause (the largest single piece, `activate_generation`'s
  336 ms): `tools/theme_transaction.py`'s `activate_generation()` always
  sent a fresh `prepare` to *both* receivers before `commit`, even when a
  receiver already held that exact generation staged from an earlier
  `exchange()` call (task 5's own prepare-ahead, or the chooser's own
  warm `preview`) -- there was no memory of which receiver was already
  warm for which generation. Fix: `exchange()` now records, per endpoint,
  the generation last successfully prepared for it
  (`_prepared_state: dict[Path, str]`, cleared on that endpoint's own
  commit or rollback); `activate_generation()` partitions its `targets`
  into `warm` (already holding this exact generation) and `to_prepare`,
  sends `prepare` only to `to_prepare`, and commits all `targets`
  unconditionally. If a "warm" receiver's commit is rejected anyway (the
  tracking was stale -- e.g. a concurrent caller reset that receiver
  without this process's knowledge), the code transparently falls back to
  a real `prepare` + `commit` for that one receiver before re-raising on
  any further failure, so a stale assumption degrades to exactly today's
  behaviour rather than a wrong commit, and full rollback correctness
  (all-or-nothing across receivers) is unchanged. Verify with `python3 -m
  unittest tests.test_omarchy_theme_transaction` (adds
  `test_activate_skips_a_prepare_already_warm_for_both_receivers`,
  `test_activate_prepares_only_the_receiver_that_was_not_already_warm`,
  `test_stale_warm_assumption_retries_with_a_real_prepare_and_still_
  succeeds`, `test_a_genuine_commit_failure_for_a_warm_receiver_still_
  rolls_back_fully`, and `test_exchange_tracks_prepared_state_across_
  prepare_commit_rollback`).
- [x] 6.4 Considered and explicitly **not implemented**: showing the new
  theme optimistically in the chooser UI on the tap frame, ahead of the
  durable two-phase commit finishing. This would mean the chooser's own
  displayed state could diverge from the receivers' actual committed
  state if the (now-mostly-skipped, but still real for a cold or stale
  generation) commit subsequently failed and rolled back -- exactly the
  "ack only after a real frame"/rollback-safety invariant task 1 and this
  change's own proposal treat as load-bearing. It is also unverifiable
  without the board (the whole point is perceived, on-glass timing), and
  6.1-6.3 already remove the *avoidable* cost 6.4 was aimed at (a warm
  Apply no longer re-prepares at all). Left as an explicit candidate
  follow-up, not attempted here; see this task's own evidence doc for the
  full reasoning.
- [x] 6.5 Extend task 3.2's prepare-ahead beyond the one centred/dwelled
  theme: `nix/rust-shell-client/src/theme_ui.rs`'s `ThemeView` gains
  `pending_neighbor_warms`, populated with the active theme's immediate
  list neighbours (one or two, whichever exist) every time a `list` reply
  is accepted -- covering both chooser-open and the return from Preview/
  Cancel back to List. `poll_prepare_ahead()` still prioritises a real
  dwell-driven warm-up (task 3.2's own 220 ms centred-and-at-rest debounce)
  every tick, and only drains the neighbour queue (one request per idle
  tick, still bounded to one in flight, still discarded before reaching
  `ThemeView::accept`) when nothing dwell-driven is due -- so a person
  actively browsing is never delayed behind a neighbour warm-up, but a
  static chooser (or one returning from Preview) starts warming the two
  themes a first swipe is most likely to land on without waiting on any
  dwell at all. Verify with `cargo test --offline --lib theme_ui` (adds
  `a_list_reply_queues_both_neighbours_of_a_mid_list_active_theme`,
  `a_list_reply_queues_only_the_one_neighbour_at_each_end_of_the_list`,
  `a_single_theme_list_queues_no_neighbours`,
  `the_neighbour_queue_drains_when_nothing_is_dwell_driven`, and
  `a_dwell_driven_request_takes_priority_over_the_neighbour_queue`).
- [ ] 6.6 Re-run the coordinator's own board commands once 6.1-6.5 are
  installed, and confirm Apply of an already-prepared generation is well
  under 150 ms end to end, with `journalctl` showing `activate_generation`
  skip the redundant `prepare` for both receivers (a `warm=2` -- or
  similar -- log line, or simply the absence of a second `appearance-
  prepare-accepted` between the chooser's own warm-up and its Apply) and
  `parse`/`prepare_entry` dropping close to their cache-hit floor. Also
  confirm the cold-open case: with 6.5 installed, the *second* theme a
  person previews after opening the chooser (having not touched the first
  one long enough to trigger its own dwell) should already be warm from
  the neighbour queue, not a fresh ~4 s `preview`. Needs the reserved
  board; not run by this task -- see this task's own evidence doc for the
  exact commands.

Proof for 6.1-6.5: the tests named above, all passing on this host; proof
for 6.6 is the reserved board, not run here.

## 7. Optimistic Apply: show an already-prepared generation ahead of the durable commit

<!-- Grounding: user decision (2026-09-25 coordinator message): "The user
     has explicitly approved the optimistic theme apply." Board evidence
     (docs/evidence/omarchy-themes/instant-theme-swap/
     board-chooser-2026-09-25.md, re-check after 6.1-6.3): tap-to-commit
     397 ms, still short of the ~100 ms target, with the remaining cost
     inside activate_generation's own durable pointer-swap/preference/
     app-sync work. See this change's design.md's own new section for the
     full design reasoning and openspec/changes/.../specs/runtime/
     shell-themes/spec.md's new "A warm Apply shows the new appearance
     ahead of the durable commit" requirement for the exact, narrow scope
     of what changed. -->

- [x] 7.1 `nix/rust-shell-client/src/main.rs` gains `should_apply_
  optimistically` (pure: is the just-submitted `Activate` request's own
  target generation exactly the local `AppearanceReceiver`'s own
  `prepared` snapshot) and `optimistic_apply_due` (pure: has this exact
  `pending_id` already been checked this Apply), checked once per fresh
  Apply right after Wayland event dispatch in `serve`'s own loop -- the
  same tick a touch-up calling `theme_action(ThemeIntent::Apply)` would
  have run in. When eligible, `show_theme_optimistically` renders the
  already-validated prepared snapshot through the same `draw_wallpaper`/
  `draw`/flush calls the real commit path already uses (skipping only for
  a video-backed selection, an unrenderable snapshot, or an overlay not
  immediately ready for a new frame -- each of which the real commit
  event's own existing readiness handling still covers correctly), and
  logs `rust-shell <ms>ms optimistic-apply shown ms=<tap-to-frame>`. This
  never touches `AppearanceReceiver`'s own `prepared`/`active` bookkeeping,
  the `Activate` request `submit_theme` already dispatched to `ThemeWorker`
  unchanged, or the wire acknowledgement contract in any way -- the real
  `AppearancePhase::Commit`/`Rollback` handling (unmodified) is what
  authoritatively settles both the receiver's own state and the visible
  appearance once the durable transaction actually completes, which is
  also what correctly reverts the display and (via `ThemeView::accept`'s
  existing, unmodified `Err` handling) surfaces a visible error on a
  durable commit failure. A cold/unprepared generation is unaffected: it
  is never prepared early to qualify, and Apply shows the pre-existing
  busy state exactly as before. Verify with `cargo test --offline`
  (`route_tests::optimistic_apply_fires_only_for_an_activate_matching_the_
  prepared_generation`, `route_tests::optimistic_apply_due_is_scoped_to_
  each_fresh_pending_id_for_a_rapid_double_apply`, and
  `theme_ui::tests::a_failed_activate_clears_pending_and_surfaces_a_
  visible_error`).
- [x] 7.2 `nix/card-shell/appearance.c` gains an additive `"show"` protocol
  phase: renders `service.candidate` immediately when it is already
  `service.prepared` and matches the requested id/path, exactly like the
  existing `commit` branch's own render call and with the same best-effort
  restore-on-failure as that branch, but never touches `service.prepared`/
  `service.candidate_path`/`service.current` -- so a real `commit` or
  `rollback` for the same candidate behaves identically whether or not
  `show` was ever sent. `main.rs`'s `show_appearance_optimistically` sends
  this best-effort, fire-and-forget (a short write deadline, no reply
  read -- any failure is silently ignored) to `K230_CARD_APPEARANCE_SOCKET`
  (defaulting to `nix/shell.nix`'s existing `SWAY_K230_CARD_APPEARANCE_
  SOCKET` production path), *after* its own local render/log so a slow or
  unreachable compositor never inflates the logged tap-to-frame latency.
  This channel is only reachable once the two-phase transaction's own
  `--rust-socket`/`--deck-socket` fanout is wired into `theme-helper.
  service` (a separate, not-yet-landed task -- see `proposal.md`'s own
  note); until then it is dormant, correct, and tested in isolation.
  Verify with `python3 -m unittest tests.test_card_shell_appearance`
  (adds `test_show_renders_a_prepared_candidate_without_disturbing_the_
  two_phase_state`, `test_show_is_rejected_for_a_generation_that_was_
  never_prepared`, and `test_show_never_blocks_a_later_rollback_from_
  restoring_the_previous_generation`, all against the real compiled
  `appearance.c` over a real socket).
- [x] 7.3 OpenSpec: the delta spec gains the new "A warm Apply shows the
  new appearance ahead of the durable commit" requirement (five
  scenarios: warm Apply shows next frame, durable success settles with no
  further visible change, durable failure rolls back visibly with an
  error, a cold theme is unaffected, a rapid second Apply is scoped
  independently). `proposal.md`'s "What This Does Not Do" section is
  revised: its former "Two-phase transaction reordering" bullet read as
  ruling out any such change permanently, which stopped being accurate
  once the user approved this; it now explains precisely what did and did
  not change (the chooser's own display timing, never the wire
  acknowledgement contract). `design.md` gains a new "Optimistic Apply"
  section recording why gating on "already prepared locally" is
  sufficient for correctness, why the compositor side is best-effort
  rather than a precondition, and the two alternatives rejected (relaxing
  the wire ack contract itself; a cross-process optimistic-shown flag).
  Verified with `openspec validate the-shell-swaps-themes-without-a-
  python-stall --strict`.
- [x] 7.4 Board re-check (coordinator, master `4b947d13`, installed as
  `i3dxi8y0...`): **the optimistic path did not fire.** No
  `optimistic-apply shown` line anywhere in the journal for an Apply of a
  neighbour-warmed, then explicitly confirmed, theme; the durable path
  alone still ran (`activate ... ms=441`, helper `activate_generation=
  356.6ms`). This is task 7.5's own starting point, below -- see its
  grounding comment for the exact log sequence and root cause.
- [x] 7.5 Root-cause and fix for 7.4: `ThemeView::poll_prepare_ahead`
  never checked `self.pending`, so while a real, explicit request (a
  confirm tap's own `Preview`, submitted via `submitted()`) was still
  awaiting its reply -- the page stays `List` until that reply lands, so
  `main.rs`'s own `page == ThemePage::List` gate did not stop it either --
  the same per-tick call could *also* drain `pending_neighbor_warms` and
  submit an unrelated neighbour's own warm-up `Preview`. `ThemeWorker`
  processes requests strictly in submission order on one thread, and each
  appearance receiver keeps only a single most-recently-`prepare`d
  candidate; the neighbour's later "prepare" therefore silently
  overwrote what the confirm's own "prepare" had just staged in
  `AppearanceReceiver::prepared` -- before its own reply was even back --
  so by the time Apply ran, `appearance.prepared()` named a different
  generation than the one just confirmed, and `optimistic_apply_skip_
  reason` correctly (if unhelpfully, before this task) returned
  `generation-mismatch`. Fix: `poll_prepare_ahead` now returns `None`
  unconditionally whenever `self.pending.is_some()` -- no dwell-driven
  warm-up, no neighbour-queue drain -- resuming on whatever tick `pending`
  next clears; the dwell clock keeps accumulating in the meantime, so
  nothing already waited out is lost. Also adds a debug log,
  `rust-shell <ms>ms optimistic-apply skipped reason=<reason>`, on every
  Apply tap that does not show optimistically (`not-prepared`,
  `generation-mismatch`, `commit-draw-in-flight`, `video-background`,
  `unrenderable-snapshot`, `not-ready-for-a-frame`, `draw-wallpaper-
  failed`, `draw-failed`, `flush-failed`), via the new pure
  `optimistic_apply_skip_reason` (`should_apply_optimistically` now
  delegates to it). Verify with `cargo test --offline` (adds
  `theme_ui::tests::a_pending_confirm_pauses_every_warm_up_until_its_own_
  reply_lands` -- reproduces the exact board sequence: warm neighbour A,
  swipe to and confirm neighbour B, assert nothing is emitted for any
  number of ticks while B's own Preview is pending, confirm Apply then
  targets exactly B's own reported generation; confirmed this test fails
  without the fix -- `left: Some((2, Preview {...}))  right: None` -- and
  passes with it -- and `route_tests::optimistic_apply_skip_reason_names_
  the_specific_cause`).

Proof for 7.1-7.3, 7.5: the tests named above, all passing on this host
(7.5's own regression test independently confirmed to fail against the
pre-fix code); 7.4 is the board result quoted above, negative before this
fix, not re-run since (board not touched by this task).

- [x] 7.6 Board re-check of 7.5 (coordinator, master `2b575dba`, installed
  as `nmdf96j1...`): the race is fixed and the decision is reached, but
  **two new problems**: (a) `optimistic-apply skipped reason=not-ready-
  for-a-frame` -- the same class of bug `cd36242b` fixed for
  `draw_wallpaper()`'s own entry guard and the durable commit path's
  `ready` predicate, but `draw()`'s own entry guard (the theme chooser's
  own overlay/settings surface) still gated on `self.frame_pending`, and
  so did `show_theme_optimistically`'s own separate readiness pre-check
  (copied from the durable path before this task noticed the durable
  path's own `overlay_ready` term had the identical gap); (b) about
  300 ms from the Apply touch-down to the optimistic decision, not yet
  root-caused with board timing data.
- [x] 7.7 Fix for 7.6(a): a new pure `redraw_entry_ready(appearance_
  pending, configured, layer_present)` (`main.rs`) is `draw()`'s entry
  guard now, with no parameter to gate on any surface's own outstanding
  frame callback -- structurally the same fix `cd36242b` already applied
  to `draw_wallpaper()`, extended to the overlay surface, whose own entry
  guard that earlier fix never touched. `show_theme_optimistically`'s own
  separate `overlay_ready`/`ready` pre-check is removed entirely: it now
  attempts `draw_wallpaper()`/`draw()` directly and reads their own
  return values, exactly like the durable commit path's `ready == true`
  branch already does (with no 1400 ms retry window, since unlike a
  durable commit, a missed optimistic frame costs only the optimism
  itself -- the real commit/rollback event still lands and settles
  correctly regardless). The durable commit path's own `overlay_ready`
  term (`serve`'s own `pending_appearance` handling) is fixed the same
  way, closing the identical latent gap there too (previously invisible
  behind its own 1400 ms retry loop). Verify with `cargo test --offline`
  (adds `route_tests::redraw_entry_never_gates_on_a_surfaces_own_
  outstanding_frame_callback`, whose signature -- no frame-pending
  parameter at all -- is itself the regression proof: this mistake cannot
  be reintroduced by accident).
- [ ] 7.8 Instrumentation for 7.6(b): every `optimistic-apply skipped
  reason=...`/`shown` log now carries `ms=<tap-to-decision-or-frame>`, so
  a board re-run can attribute the remaining latency precisely (input
  recognition before `submit_theme` sets `theme_apply_tapped_at` --
  already close to the existing `touch-up <id>` log, since `submit_theme`
  runs synchronously in the same call chain -- versus this task's own
  decision/draw/flush cost, which reading `main.rs`'s code found no
  blocking calls in: `try_submit` is `try_send` (never blocks),
  `AppearanceSnapshot::clone()` carries no pixel data, and (after 7.7) the
  draw calls no longer wait on any frame callback). Root-causing the
  remaining gap precisely needs this instrumentation's own board data;
  not claimed found or fixed by this task -- see this task's own evidence
  doc for the reasoning and what the new `ms=` fields will show.

Proof for 7.1-7.3, 7.5, 7.7: the tests named above, all passing on this
host; 7.4/7.6 are the board results quoted above; 7.8's own instrumentation
answered its own question on the very next board run -- see task 8 below,
which its board evidence directly motivates: `optimistic-apply shown
ms=222.7` is (almost) entirely the synchronous overlay-scene rebuild
Apply's own optimistic show pays inline, not event-loop or dispatch
latency.

## 8. Pre-render at prepare time; reuse the durable commit's own frame

<!-- Grounding: board re-run of 7.7 (coordinator, master `e2ba1d7e`,
     installed as `s376wb46...`): the optimistic path fires
     (`optimistic-apply shown ms=222.7`, 224 ms after touch-up), but (a)
     that 222.7 ms *is* the cost -- a full synchronous overlay-scene
     rebuild (Cairo, icon decode) triggered by `set_appearance`'s own
     `invalidate()` -- and (b) the optimistic draw left no free wallpaper
     buffer, so the durable commit's own `draw_wallpaper` failed
     ("appearance-commit-rejected draw-wallpaper-failed"), forcing a full
     prepare+commit retry that roughly doubled `activate_generation`'s own
     time (452.4 ms). Coordinator's own design: pre-render the wallpaper
     and panel/overlay frames ahead, at prepare time, into spare buffers;
     attach+commit only at Apply; invalidate on geometry/page/content
     change; bound to one pre-rendered candidate; a third buffer (or a
     reservation) so the durable commit never fails for lack of one; the
     durable commit accepts an already-shown generation instead of
     redrawing, while still acking only after a real frame. -->

- [x] 8.1 A third wallpaper buffer: `draw_wallpaper()`'s own buffer-pool
  exhaustion check raised from `>= 2` to `>= 3` (the overlay surface's own
  pool was already bounded to 3), and the SHM pool's own initial-size hint
  raised from `* 5` to `* 6` slots (568x1232x4 bytes each, ~2.8 MB, matching
  the coordinator's own figure) -- an estimate only, since `SlotPool`
  itself grows automatically on any further allocation regardless
  (confirmed by reading `smithay-client-toolkit`'s own `SlotPool::resize`
  doc: "the pool automatically resizes when you allocate new slots").
  This alone (independent of pre-rendering) is what stops the durable
  commit's own redraw from ever again failing merely because an
  optimistic draw is still holding a buffer the compositor has not yet
  released.
- [x] 8.2 `RendererCache` (`render.rs`) gains `content_generation: u64`
  (bumped by `set_theme_view`/`set_services`/a real `set_drawer_pressed`
  change/a `poll_theme_image`- or `poll_theme_thumbnails`-detected change
  -- every non-appearance input a scene render depends on -- and
  deliberately *not* by `set_appearance`/`set_icon_theme`, which a
  candidate pre-render is expected to differ from `self.theme` on, on
  purpose), `render_candidate_overlay(theme, route, width, height, apps)`
  (computes a full overlay-scene raster for an arbitrary `theme` using a
  *fresh*, isolated `IconCache` and every other input read live from
  `self` -- `services`/`chooser`/`pressed`/`preview_surface`/
  `preview_error`/`thumbnails` -- provably never touching `self.theme`/
  `self.icons`/`static_pixels`/`route`, so nothing can flash the wrong
  theme before Apply), and `adopt_prerendered_overlay(theme, route,
  width, height, pixels)` (seeds `self.theme`/`self.icons`/
  `static_pixels`/`route`/`width`/`height`/`scroll` directly from an
  already-computed raster, so `draw()`'s own next call sees a cache hit
  and takes its cheap shift-and-copy path instead of rebuilding). Verify
  with `cargo test --offline --lib render::tests` (adds
  `content_generation_bumps_on_content_changes_but_not_on_appearance_
  changes`, `render_candidate_overlay_never_mutates_the_live_cache`,
  `adopt_prerendered_overlay_is_a_cache_hit_with_the_candidates_own_
  pixels`).
- [x] 8.3 `main.rs`'s own event loop computes the pre-render once per
  (generation, route, geometry, `content_generation`) tuple whenever the
  Preview page's own currently-loaded candidate is already the receiver's
  own `prepare`d snapshot (the same precondition Optimistic Apply itself
  checks -- never a cold generation, never a merely-warmed neighbour still
  being browsed past), bounded to one slot (`ShellClient::
  prerendered_overlay: Option<PrerenderedOverlay>`), and only *after* that
  tick's own `queue.flush()` -- never earlier in the same iteration --
  so the real, synchronous Cairo cost this pays is never charged against
  flushing the very Preview-page frame that made it eligible. Skipped
  entirely while an Activate is already in flight. Verify with `cargo
  test --offline --lib route_tests`
  (`prerendered_overlay_matches_requires_every_field_to_agree`, the pure
  matching predicate this trigger and Apply-time consumption both share).
- [x] 8.4 `show_theme_optimistically` consumes the stored pre-render
  (always taking the one bounded slot, matching or not, so a stale one
  never lingers for a later Apply) when it matches this exact Apply's own
  generation, route, geometry, and `content_generation`; on a match it
  calls `adopt_prerendered_overlay` instead of `set_appearance` (skipping
  the rebuild entirely); on any mismatch it falls back to `set_appearance`
  exactly as before this task. The `optimistic-apply shown ms=...` log
  gains `prerendered=true/false`. Verify with the 8.2/8.3 tests above
  (the underlying primitives) plus `route_tests::
  optimistic_apply_fires_only_for_an_activate_matching_the_prepared_
  generation` and the existing Optimistic Apply suite, all still passing
  unmodified.
- [x] 8.5 The durable commit reuses an already-shown Optimistic Apply
  frame instead of redrawing it: `ShellClient::optimistic_active:
  Option<String>` records the generation a successful optimistic show
  just flushed; the very next `Commit`/`Rollback` event's own handling
  checks `may_reuse_optimistic_frame` (pure: true only for a `Commit`
  whose own generation matches exactly -- a `Rollback`'s own target is by
  definition the *previous* generation, never the one just shown) and
  clears `optimistic_active` unconditionally either way, so it can only
  ever be read by that one next event. A match skips `draw_wallpaper`/
  `draw`/`flush` entirely (`pending_appearance`'s own new
  `reuse_optimistic` element) and goes straight to the same video-state
  bookkeeping (`adopt_committed_video_state`, factored out of what was
  previously inline in the redraw-success branch so both paths share it)
  and the ack -- still sent only after a real, already-flushed frame,
  never before one. Verify with `cargo test --offline --lib route_tests`
  (`may_reuse_optimistic_frame_only_for_a_commit_matching_exactly`).
- [ ] 8.6 Board re-check: confirm `optimistic-apply shown ms=` drops close
  to the ~30 ms target (a cache-hit shift-and-copy plus an attach+commit,
  not a rebuild) with `prerendered=true` for a warm Apply; confirm no
  `appearance-commit-rejected draw-wallpaper-failed` on the success path
  (the third buffer); confirm the durable commit's own log shows
  `appearance-commit-accepted reused=optimistic` and `activate_generation`
  no longer carries a retry's own doubled cost; confirm a geometry, page,
  or content change between prepare and Apply correctly falls back to a
  full rebuild (`prerendered=false`) rather than showing stale content.
  Needs the reserved board; not run by this task.

Proof for 8.1-8.5: the tests named above, all passing on this host; proof
for 8.6 is the reserved board, not run here.

## 9. Split the footer/status from the cached body so a pre-render can actually match at Apply

<!-- Grounding: board re-run of task 8 (coordinator, master `c6f0237a`,
     installed as `vq6vkvqz...`): the pre-render computes
     (`optimistic-apply prerendered generation=...`, twice, ~150ms apart
     -- roughly one THEME_PULSE_INTERVAL), but at the Apply tap itself
     `optimistic-apply shown ms=224.0 prerendered=false` -- the exact
     same ~224ms full rebuild as before task 8, even though the durable
     commit's own reuse (task 8.5) still correctly fired
     ("appearance-commit-accepted reused=optimistic", no rejection).
     Root cause: `submit_theme`'s own `theme_dirty()` call (synchronous,
     in the same touch-up handling that submits the Activate) sets
     `theme_view.pending = Some(Activate{...})` *before* Optimistic
     Apply's own check ever runs, and `set_theme_view` bumped
     `content_generation` unconditionally on every call -- so the tap
     itself always invalidated the very pre-render it was about to need. -->

- [x] 9.1 The Preview page's dynamic Apply/Cancel footer (the pressed
  highlight, the Apply button's own text/color/busy spinner across idle/
  applying/applied, and the `Preparing…`/error/message status line below
  it) is extracted out of `paint_theme_chooser` into a new, standalone
  `paint_preview_footer_status` (`render.rs`) and painted live, by
  `RendererCache::draw()` itself, on every call -- whether that call just
  rebuilt `static_pixels` or reused it (including an adopted pre-render).
  `paint_theme_chooser` no longer paints any of it at all (for either
  page: the List page's own status line is unaffected, still baked into
  its cached body as before). This is what makes a pre-render computed
  before an Apply tap still correct *after* one: the tap's own `pending`
  transition changes only what the live overlay paints, never what the
  cached/pre-rendered body underneath it has to be rebuilt for. Verify
  with `cargo test --offline --lib render::tests` (adds
  `adopted_prerender_still_shows_the_live_pending_state_via_the_overlay`,
  independently confirmed to fail -- the exact stale-idle-button pixels
  -- with this task's fix temporarily disabled, and pass with it restored;
  all 25 pre-existing `render::tests` cases, which exercise the Apply
  footer's own pixels through the unchanged public `RendererCache::draw`,
  still pass byte-for-byte unmodified, proving the split is
  output-equivalent for every case that was already covered).
- [x] 9.2 `content_generation` (task 8.2) no longer bumps for a
  `set_theme_view` call that changes only `pending`/`pending_id`/
  `selection_error`/`error`/`message`/`pulse_phase` -- exactly the fields
  9.1 moved to the live overlay -- via a new pure `theme_view_cache_key_
  differs` (comparing `page`/`list`/`preview`/`theme_pressed`/
  `background_pressed` exactly, `theme_position`/`background_position`
  with the same small tolerance `RendererCache::draw`'s own `scroll`
  check already uses). `invalidate()` itself stays unconditional on every
  `set_theme_view` call, so a live (non-optimistic) `draw()` still
  rebuilds on every theme_view change exactly as before this task;
  `content_generation` is now a narrower, pre-render-specific freshness
  signal, decoupled from that. This also closes the coordinator's own
  third observation (double pre-render computation ~150ms apart, a full
  `THEME_PULSE_INTERVAL`): a pulse-only tick can no longer churn
  `content_generation` either. Verify with `cargo test --offline --lib
  render::tests` (adds `a_pending_only_theme_view_change_does_not_bump_
  content_generation`, proving both that pending/pulse changes are now
  excluded and that a genuine content change -- a different preview --
  still bumps it as before).
- [x] 9.3 The pre-render trigger (task 8.3) now requires `theme_view.
  pending.is_none()` outright, not just "not an Activate": the background
  carousel's own busy spinner (a `Preview{background_id: Some(_)}`
  request in flight) is baked into the cached body the same as anything
  else `content_generation` does not track, and 9.1's live overlay does
  not cover it (only the Apply/Cancel footer and status line) -- so
  computing a pre-render while a background selection is still pending
  risked caching a stale busy indicator no later live paint would ever
  correct. Requiring nothing at all pending closes that gap by
  construction rather than adding a second live overlay for it.
- [x] 9.4 `optimistic-apply shown ms=... prerendered=false` now carries
  `reason=<field>` (`no-prerender-computed`, `generation`, `route`,
  `geometry`, `content-changed`, or `not-on-settings-route`) naming
  exactly which check failed, via a new `prerendered_overlay_mismatch_
  reason` that `prerendered_overlay_matches` (task 8.3's own pure
  predicate) now delegates to, so the two can never drift apart. Verify
  with `cargo test --offline --lib route_tests`
  (`prerendered_overlay_mismatch_reason_names_the_specific_field`).
- [ ] 9.5 Board re-check: confirm `optimistic-apply shown ms=<N>
  prerendered=true` for a warm Apply, with `<N>` close to the ~30 ms
  target; confirm the earlier double-prerender-computation symptom is
  gone (at most one `optimistic-apply prerendered` line per genuine
  content change while dwelling on the Preview page); confirm the
  screen's own footer text still reads `Applying…` then `Theme applied`/
  `Apply again` correctly across the transaction, never stuck on a stale
  `Apply`; if `prerendered=false` still occurs, its own `reason=` field
  states why directly. Needs the reserved board; not run by this task.

Proof for 9.1-9.4: the tests named above, all passing on this host
(9.1's own regression test independently confirmed to fail against the
pre-fix code); proof for 9.5 is the reserved board, not run here.

## 10. Tap-to-apply: no separate Preview page, no Apply/Cancel step

<!-- Grounding: user decision (2026-09-25, verbatim): "i don't really think
     we need an 'apply' window for themes at all. tap theme in the theme
     picker, apply immediately, so i can compare them easily." Also folds
     in a second coordinator message, board re-check of task 9 (master
     `644cd061`, installed `n44hk9js...`): a *matched* pre-render still
     took 161ms touch-up-to-commit on the K230 (target ~30ms), and
     `optimistic-apply prerendered` was still computed twice, ~154ms
     apart, for the same generation. -->

- [x] 10.1 `theme_ui.rs` rewritten: `ThemePage::Preview` removed (only
  `Controls`/`List` remain -- the theme carousel, the active theme's own
  background carousel below it, and a plain "Current theme"/"Current
  background" label under whichever slice of each is centred and durably
  active, all on one page). A new `Desired`/`ThemeView::advance` state
  machine (`desired`, private-but-`pub`-for-struct-update, same convention
  as `prepare_ahead_watch`) coalesces rapid taps: a fresh tap always
  overwrites `desired`; `advance()` submits the next step toward it only
  when nothing is already in flight; a reply that no longer matches
  `desired` is discarded, and the caller's own follow-up `advance()` call
  immediately moves on to whatever is now desired -- bounding in-flight
  work to one request, with the documented tradeoff that a second rapid
  tap's own visible effect is bounded by the first tap's own in-flight
  round trip, not instantaneous (proven directly:
  `rapid_taps_across_themes_coalesce_onto_the_last_one`). New `ThemeView::
  tap_theme`/`tap_background` replace `preview_request`/`background_request`/
  `apply_request`; `ThemeIntent::Apply` and `ThemeView::selection_error`/
  `selection_failed` are removed. A background tap already knows its own
  theme's generation (loaded alongside the backgrounds themselves), so it
  goes straight to `Activate`, no `Preview` step; a theme tap does not
  (the target theme's own generation is not necessarily known), so it
  always previews first. New `known_generations: HashMap<String, String>`
  remembers a warm-up reply's own `(theme_id, generation)` (via
  `record_known_generation`, wired from `main.rs`'s `theme_reply` on a
  `prepare_ahead_reply` hit) so the pre-render trigger (10.3) can target a
  centred-but-not-tapped theme without its own fresh round trip. New
  `ThemeView::applying_theme_index`/`applying_background_index` drive a
  brief, in-place busy spinner on the tapped slice (`render.rs::
  paint_carousel`'s existing `busy: Option<usize>` parameter, unchanged)
  instead of blocking the carousel. Verify with `cargo test --offline
  --lib theme_ui::tests` (24 tests, all passing, including tap-apply of a
  cold theme, tap-apply of the already-active theme, background tap-apply,
  the video/already-selected background no-ops, rapid-tap coalescing, and
  rollback-on-failure with a visible error).
- [x] 10.2 `render.rs`'s `paint_theme_chooser` merges the old List and
  Preview branches into one: the theme carousel, its "Current theme"/
  origin label, the "Backgrounds" heading, the background carousel, its
  own "Current background"/"Tap to apply" label, then one pending/error/
  message line -- all on the fixed layout `theme_ui::THEME_CAROUSEL_TOP`
  (moved from `204.0` to `132.0`) and `BACKGROUND_CAROUSEL_TOP` (now a
  const-expr `THEME_CAROUSEL_TOP + THEME_GEOMETRY.expanded_h + 100.0` =
  `872.0`, not board-verified for fit/spacing -- see this task's own
  evidence). `paint_preview_footer_status` (the Preview page's own live
  Apply/Cancel footer overlay, task 9.1) and `RendererCache::draw`'s own
  call to it are removed outright: with no Apply button, nothing needs a
  second, live paint pass any more -- `set_theme_view`'s own unconditional
  `invalidate()` (task 9.2's own doc) already forces the ordinary rebuild
  path to repaint the busy spinner and pending/error/message line fresh on
  every `ThemeView` change, and the one case that skips a fresh rebuild
  (an *adopted* pre-render) is correct exactly because, at the moment it
  is shown, the applied theme already looks done -- proven by
  `a_theme_view_change_after_adopting_still_rebuilds_and_shows_pending`
  (renamed/re-reasoned from 9.1's own regression test) and
  `a_pending_only_theme_view_change_does_not_bump_content_generation`
  (re-targeted to the one List page, doc updated). The single large
  "screen crop" still-image preview (`RendererCache::poll_theme_image`/
  `preview_surface`, `theme_preview_image_pending`) is now a deliberate,
  documented permanent no-op -- both carousels already show their own
  thumbnails via `ThemeThumbnailCache`, so nothing paints a decoded still
  any more; `ThemeImageWorker`/`ThemeImageKey` and the worker's own two
  tests are kept, unused, as a named follow-up to prune rather than a
  silent removal. Verify with `cargo test --offline --lib render::tests`
  (all passing, including the fixed
  `list_and_background_rows_paint_their_own_thumbnail_once_decoded`,
  which caught a real bug this task introduced and fixed in the same
  commit: the merged `poll_theme_thumbnails` match arm used to `return`
  early when `chooser.list` was `None`, skipping the background carousel's
  own thumbnail requests whenever its own detail loaded without a list --
  the two are now requested independently).
- [x] 10.3 `main.rs`'s touch-down/motion/up/tick handlers no longer branch
  on `ThemePage::List`/`Preview` to pick a carousel: both carousels are
  probed independently now that both are visible at once --
  `Carousel::down`/`motion`/`tick` are called unconditionally (each is
  keyed by its own armed `contact.id` internally, safe to call on both;
  `tick` has no touch-ownership concept at all and always advances both),
  and `Carousel::up` is tried on the theme carousel first, falling
  through to the background carousel only on `None` (a touch id it never
  armed), which correctly finds whichever one, if either, owns a given
  touch. `theme_reply` now compares `theme_position`/`background_position`
  before and after `accept()` to decide which physics carousel (if
  either) to re-index, instead of branching on page -- precise, since
  only `accept()`'s own List/settling-Preview handling ever changes those
  fields, never a concurrent drag. The pre-render trigger (task 8.3) is
  retargeted from the removed Preview page's own loaded candidate to the
  theme carousel's own *centred* candidate on the List page, using
  `known_generations` (10.1) rather than a fresh Preview round trip, so
  pre-rendering the very next likely tap-apply never itself costs a round
  trip. `show_theme_optimistically` gained per-stage `ms=` instrumentation
  (`optimistic-apply stage adopt_ms=... wallpaper_ms=... overlay_ms=...
  flush_ms=...`, logged alongside the existing summary line) -- the
  coordinator's own ask, board evidence 2026-09-28: a *matched*
  pre-render still took 161ms touch-up-to-commit, target ~30ms. This
  instrumentation is coarse (one line per `draw_wallpaper`/`draw` call,
  since attach/damage/`wl_surface::commit` all happen inside those calls
  and are not separately timed); a finer breakdown inside `draw`/
  `draw_wallpaper` themselves, and the wallpaper-buffer-attach
  optimization the same board evidence asked for (pre-build the actual
  `wl_buffer` at prepare time so adopting is attach-only, no pixel copy),
  are **not attempted this task** -- named as deferred follow-up work in
  this task's own evidence doc, since implementing and tuning either
  without a way to measure them on the actual board (this task did not
  touch the board) risks a change that looks right in a diff and is
  wrong, or merely neutral, in practice. Verify with `cargo test --offline`
  (`route_tests`, 14 tests, unchanged and passing -- `should_apply_
  optimistically`/`optimistic_apply_due`/`may_reuse_optimistic_frame`/
  `prerendered_overlay_matches` are pure functions this task did not
  touch, confirming the optimistic-apply/pre-render machinery's own
  correctness is intact under the new single-page model).
- [x] 10.4 Investigated the coordinator's third observation (the same
  generation's own pre-render computed twice, ~154ms apart) by code
  review rather than board access. On master `644cd061` (before this
  task), the Preview page's own `RendererCache::poll_theme_image` was
  actively decoding the selected background's "screen crop" still image
  asynchronously; that decode completing bumps `content_generation` (its
  own `changed` branch) independently of `theme_view_cache_key_differs`
  (task 9.2's fix only excludes `ThemeView` fields, not this separate
  decode-completion signal) -- a ~150ms async decode completing shortly
  after the Preview page loads exactly matches the reported ~154ms gap
  and a "computed twice for the same generation" symptom (the second
  compute reacting to the image arriving, not a fresh tap). This task's
  own 10.2 makes `poll_theme_image` a permanent no-op (nothing paints a
  decoded still any more, both carousels use `ThemeThumbnailCache`
  instead), which removes this specific trigger structurally: there is no
  longer an asynchronous decode running that could bump `content_
  generation` a second time while a person dwells on an unchanged
  candidate. This is reasoned from the code, not re-verified against
  fresh board evidence this session (the reserved board was not used, per
  this task's own constraint); 10.6's board re-check is where that gets
  confirmed or refuted.
- [x] 10.5 OpenSpec: added "Tapping a theme or background applies it
  immediately, with no separate preview-then-Apply step" to `specs/
  runtime/shell-themes/spec.md` (this change's own delta -- the capability
  has not been archived into `openspec/specs/` yet, so every requirement
  here, including this one, is still `ADDED`), with the user's verbatim
  decision as its grounding, and lightly reworded "A warm Apply shows..."
  to note that "Apply tap" now means a tap on either carousel's own
  centred slice, not a since-removed button -- the mechanism that
  requirement describes is unchanged. `openspec validate
  the-shell-swaps-themes-without-a-python-stall --strict` passes.
- [ ] 10.6 `tests/rust_theme_chooser_qemu.py` rewritten for the one-page
  flow: opens the chooser, waits for the active theme's own detail to
  auto-load (no tap needed), browses the theme carousel by drag and by a
  side-slice recentre-tap (still never applies), confirms a warmed theme
  applies on a single centred tap with no further tap (screen repaints,
  exactly one `activate` for it, `--expected-generation` correct),
  browses and tap-applies a background of that theme directly (`activate`
  with `--background`, and specifically asserts no `preview` call was
  needed for it), then proves rapid-tap coalescing: `THEME_COMMAND` sleeps
  1.5s before answering a `preview` call for one designated theme
  (`K230_TEST_THEME_SLOW_ID`), giving a reliable window to tap a
  *different* theme while the first is in flight; asserts the superseded
  theme's own request was genuinely sent but never activates, and the
  second tap's theme does. Run (real QEMU, synthetic theme command, no
  physical touch -- see this task's own evidence doc for the exact
  command and result).
- [ ] 10.7 Board re-check: confirm the one-page tap-to-apply flow reads
  and behaves correctly in dark and light themes on the actual panel;
  confirm `optimistic-apply stage adopt_ms=... wallpaper_ms=...
  overlay_ms=... flush_ms=...` for a warm tap-apply, and whether the
  total (`optimistic-apply shown ms=...`) has moved from the 161ms board
  baseline toward the ~30ms target now that the double-pre-render trigger
  is structurally removed (10.4); confirm the new
  `THEME_CAROUSEL_TOP`/`BACKGROUND_CAROUSEL_TOP` layout (10.2) actually
  fits the 1232px panel without clipping or crowding. Needs the reserved
  board; not run by this task.

Proof for 10.1-10.3, 10.5-10.6: the tests and commands named above, all
passing/PASS on this host; proof for 10.4 is code review, named as such,
not board evidence; proof for 10.7 is the reserved board, not run here.
The wallpaper-buffer-attach optimization and a finer per-stage
attach/damage/commit breakdown (both asked for alongside 10.3) are
deferred follow-up work, not attempted this task -- see 10.3's own doc.

Keep this change open (or split at review time into an explicit successor
per `AGENTS.md`) until 2.3, 3.4, 6.6, 9.5, and 10.7 have board results;
3.3b is named here so it is not silently dropped or claimed done without
a board result. Task 5.4's board result is recorded above
(board-chooser-2026-09-25.md).
