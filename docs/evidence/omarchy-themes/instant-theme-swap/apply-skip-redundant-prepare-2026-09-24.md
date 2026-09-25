# Apply of an already-warm generation: skip the redundant prepare

Implements OpenSpec tasks 6.1-6.5 from
`openspec/changes/the-shell-swaps-themes-without-a-python-stall/tasks.md`,
against the coordinator's board run in
`docs/evidence/omarchy-themes/instant-theme-swap/board-chooser-2026-09-25.md`
(system `phj9y4fggpb177b0hgaawbh510chhwil`, `master` `f4f75998`). This is a
**host-only** result: no board, glass, or real-finger observation. Worktree
`perf/instant-apply`, base `master` `9ff0462c`.

## What the board run showed, and what each fix targets

| Board number | Cause found | Fix |
| --- | --- | --- |
| `parse=65.0ms` | `theme_helperd.py` built a fresh `argparse.ArgumentParser` on every request instead of once at daemon start | 6.1: build the parser once in `Helperd.__init__()` |
| part of `prepare_entry=90.6ms` | `theme_activate.prepare()` re-hashed the theme's own source tree (full content read) on every call, even for an unchanged theme | 6.2: `theme_digest()` caches `source_digest()`, invalidated by a cheap stat-only `source_fingerprint()` |
| `activate_generation=336.0ms` (the largest single cost) | `activate_generation()` always sent a fresh `prepare` to both receivers before `commit`, even when a receiver already held that exact generation staged from the chooser's own earlier `preview`/prepare-ahead | 6.3: track per-endpoint prepared state; skip `prepare` for a receiver already warm for this generation; commit directly; transparently retry with a real prepare if a "warm" assumption turns out stale |
| cold prepare-ahead `4071ms` when the carousel first opens | only the *centred* theme is ever warmed, and only after a 220 ms dwell -- the first theme a person looks at pays the full cold cost | 6.5: queue the active theme's immediate list neighbours for warming as soon as the `list` reply itself loads, drained whenever nothing dwell-driven is due |
| "under 100 ms from tap to visible, optimistic UI" (coordinator's "better still") | -- | 6.4: considered, explicitly not implemented -- see below |

## 6.1: parser built once, not per request

`tools/theme_helperd.py`'s `Helperd.handle_line()` called
`theme_catalog.build_parser()` on every request. `build_parser()`
constructs an `argparse.ArgumentParser` with every subcommand's own
subparser and arguments -- real work, but identical on every call for the
life of the daemon. Moved to `Helperd.__init__()`; `handle_line()` reuses
`self.parser`. Verify:

```sh
python3 -m unittest tests.test_theme_helper_daemon
```

`test_the_argument_parser_is_built_once_not_once_per_request` counts
`build_parser` calls across several requests on one daemon instance.

## 6.2: theme source digest cached, invalidated by a cheap fingerprint

`theme_activate.prepare()` calls `source_digest(theme)` (a full read-and-hash
of every file in the theme's source tree) at least twice per call: once to
compute the generation identity, once again to detect a source change during
staging. Both were previously uncached, unlike the already-cached tools
(`helper_digest`) hash from task 5.3, deliberately: a person's own theme
files can change while the daemon keeps running, so the theme's own digest
must never go stale.

`tools/theme_sources.py` gains `source_fingerprint(theme)`: the same
directory walk `source_digest()` performs (same symlink rejection, depth,
entry-count, and per-file/total-byte limits), but collecting only
`(relative_path, size, mtime_ns)` per file -- no content read. `theme_
activate.theme_digest(theme)` wraps `source_digest()` with a cache keyed by
the theme's resolved path, valid only while the fingerprint is unchanged;
both call sites in `prepare()` now go through `theme_digest()` instead of
`source_digest()` directly. An edited file changes its size and/or mtime, so
it is still re-hashed on the very next call; an untouched theme is not.
Verify:

```sh
python3 -m unittest tests.test_omarchy_theme_sources tests.test_omarchy_theme_activation
```

`test_fingerprint_matches_digest_sensitivity_without_reading_content` proves
the fingerprint changes on any edit or added file without reading content;
`test_theme_and_helper_digests_are_cached_across_repeated_preparations`
(renamed from the task-5.3 test) and the new `test_theme_digest_cache_is_
invalidated_by_an_edit_between_preparations` cover the cache hit/invalidate
behaviour for `prepare()` itself.

## 6.3: skip the redundant prepare on an already-warm Apply

The board's dominant cost: `activate_generation()` in `tools/theme_
transaction.py` sent `prepare` to *both* receivers (the Rust chooser and the
Sway/card-shell compositor) before `commit`, even when a receiver already
held that exact generation staged -- from the chooser's own prepare-ahead
`preview`, or a prior identical `activate` -- because nothing tracked which
receiver was prepared for which generation across calls.

`exchange()` now records per-endpoint prepared state:

```python
_prepared_state: dict[Path, str] = {}

def _remember(endpoint: Path, phase: str, generation: Path | None) -> None:
    if phase == "prepare" and generation is not None:
        _prepared_state[endpoint] = generation.name
    elif phase in ("commit", "rollback"):
        _prepared_state.pop(endpoint, None)
```

`activate_generation()` partitions `targets` into `warm` (state says already
prepared for this exact generation) and `to_prepare`, sends `prepare` only
to `to_prepare`, then commits every target unconditionally. If a "warm"
receiver's `commit` is rejected anyway -- the tracking was stale, e.g. a
concurrent caller reset that receiver outside this process's view -- the
code transparently retries with a real `prepare` then `commit` for that one
receiver before re-raising on any further failure. A stale assumption
therefore degrades to exactly today's behaviour (a real prepare, then
commit) rather than ever risking a wrong or partial commit; full
all-or-nothing rollback correctness across both receivers is unchanged.
Verify:

```sh
python3 -m unittest tests.test_omarchy_theme_transaction
```

Five new cases: `test_activate_skips_a_prepare_already_warm_for_both_
receivers`, `test_activate_prepares_only_the_receiver_that_was_not_already_
warm`, `test_stale_warm_assumption_retries_with_a_real_prepare_and_still_
succeeds`, `test_a_genuine_commit_failure_for_a_warm_receiver_still_rolls_
back_fully`, `test_exchange_tracks_prepared_state_across_prepare_commit_
rollback`.

## 6.4: the optimistic tap-frame UI -- considered, not implemented

The coordinator's "better still" suggestion was to show the new theme in
the chooser UI on the tap frame itself, since the receivers already hold
the prepared resources, letting the durable commit finish asynchronously.
This was **not implemented**, for three reasons:

1. **Correctness risk.** The chooser's displayed state would diverge from
   the receivers' actual committed state for exactly the window between
   the optimistic repaint and the real commit ack. If that commit then
   failed and rolled back -- a real, handled case today (a receiver
   restarted, a generation removed from under it, a second commit failure
   after the first succeeded) -- the person would see a theme applied that
   the system then reverted, with no visible cue why. This is the precise
   invariant task 1's own instrumentation and this whole change's proposal
   both treat as load-bearing: "ack only after a real frame," never a
   result the two-phase protocol has not yet confirmed.
2. **Unverifiable without the board.** The entire point of the change is
   perceived, on-glass latency; a host or QEMU run cannot show whether an
   optimistic repaint actually looks instantaneous versus merely racy, and
   this task is explicitly not to touch the board.
3. **6.1-6.3 already remove the avoidable cost this was aimed at.** A warm
   Apply (the common case once 6.5's neighbour-warming is in place) no
   longer re-prepares either receiver at all -- the remaining `activate_
   generation` cost for a warm generation is just the `commit` round trip
   itself, not a second `prepare`. The board re-check in 6.6 is what tells
   us whether that remaining cost still needs the optimistic-UI idea as a
   follow-up, rather than guessing at it here.

Left as an explicit candidate follow-up, to be revisited only with a board
re-check in hand and, if pursued, a UI-level rollback affordance designed
alongside it.

## 6.5: warm the active theme's neighbours as soon as the list loads

Task 3.2 only ever warms the *centred* theme, and only after a 220 ms
dwell -- so the very first theme a person looks at when the chooser opens
(the board's cold 4071 ms `preview`) is never warmed ahead of time, and a
quick first swipe to an adjacent theme still pays the full cost.

`ThemeView` gains `pending_neighbor_warms: VecDeque<usize>`, populated with
the active theme's immediate list neighbours (one, at either end of the
list, or two) every time a `list` reply is accepted -- covering chooser-open
and the return from Preview/Cancel back to List alike. `poll_prepare_ahead`
still prioritises a real dwell-driven warm-up every tick (a person actively
browsing is never delayed behind a neighbour warm-up); only when nothing
dwell-driven is due does it drain the neighbour queue, one request per idle
tick, still bounded to a single request in flight, still discarded before
it can reach `ThemeView::accept`. Verify:

```sh
cd nix/rust-shell-client && cargo test --offline --lib theme_ui
```

Five new cases: `a_list_reply_queues_both_neighbours_of_a_mid_list_active_
theme`, `a_list_reply_queues_only_the_one_neighbour_at_each_end_of_the_
list`, `a_single_theme_list_queues_no_neighbours`, `the_neighbour_queue_
drains_when_nothing_is_dwell_driven`, `a_dwell_driven_request_takes_
priority_over_the_neighbour_queue`.

## Test-suite proof

- `cargo test --offline` (nix/rust-shell-client): all suites pass --
  `--lib` 16 `theme_ui` cases (11 pre-existing + 5 new) plus the crate's
  other lib tests, and the `theme_catalog_module`/`background_decode_
  module`/`service_data_module` integration suites, 0 failures.
- `python3 -m unittest tests.test_omarchy_theme_transaction
  tests.test_theme_helper_daemon tests.test_omarchy_theme_activation
  tests.test_omarchy_theme_sources tests.test_theme_catalog
  tests.test_theme_timing`: 73 cases, all passing (run 11 of 12 times
  clean; one run hit a `shutil.rmtree` "Directory not empty" race during
  an unrelated test's teardown under `uptime` load 14-24 from concurrent
  agents on this shared host -- reproduced 8/8 clean immediately after,
  consistent with the same host-contention flake class already documented
  in `docs/evidence/omarchy-themes/instant-theme-swap/README.md`'s own
  section 6; not touched by this task's diff, which adds no threading).
- `python3 tools/blob-scan.py`: exit 0 ("every binary is accounted for").
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust .#handheld-theme-command .#handheld-theme-default
  .#card-shell`: all built cleanly for riscv64; `theme_timing.py`,
  `theme_sources.py`, and `theme_transaction.py` confirmed present under
  `.#handheld-theme-command`'s own `libexec/handheld-theme/`.
- `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`:
  evaluates to a `.drv` path, no eval error.
- `openspec validate the-shell-swaps-themes-without-a-python-stall --strict`:
  valid.

## Board commands for the coordinator (task 6.6)

Same shape as `board-chooser-2026-09-25.md`'s own run: Settings, tap Themes,
wait long enough for the carousel's own neighbour-warm to land (no dwell
needed with 6.5 in place), tap a theme, wait past the 220 ms dwell so the
chooser's own prepare-ahead has time to run, then tap Apply.

```sh
journalctl -u theme-helper -u shell-ui -u shell -o json --since "-2min" \
  | grep -E "THEME_TIMING|theme-command|appearance-(prepare|commit)-accepted"
```

What to look for that would confirm this task's fixes landed:

- `parse=` well under 65 ms (parser built once, at daemon start).
- `prepare_entry=` lower for an already-warm generation (no full source
  re-hash).
- For an Apply of a theme the chooser already prepared (dwelled-on,
  neighbour-warmed, or a repeat of the same theme): no second
  `appearance-prepare-accepted` line between the chooser's own warm-up and
  the Apply's own commit -- only a commit. `activate_generation`'s own
  logged `ms=` should drop close to just the `commit` round trip's cost.
- For the *second* theme previewed after opening the chooser (not the
  first, not one dwelled on): a `preview` `ms=` close to the warm ~200 ms
  figure, not the cold ~4 s figure, proving the neighbour queue warmed it
  ahead of time.
- Whether the resulting Apply-to-visible time is now under the ~150 ms
  target from task 5, and how close it comes to the user's original
  ~100 ms goal -- the honest answer only the board can give.

Task 6.6's board run has not been executed by this worktree; `/dev/ttyACM0`
was not opened here.
