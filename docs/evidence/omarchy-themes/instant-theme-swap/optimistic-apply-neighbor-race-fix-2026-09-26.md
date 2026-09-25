# Optimistic Apply missed its own show: a neighbour-warm race

Implements OpenSpec tasks 7.4-7.5 from
`openspec/changes/the-shell-swaps-themes-without-a-python-stall/tasks.md`,
fixing a bug the coordinator's board run found in the Optimistic Apply work
(`docs/evidence/omarchy-themes/instant-theme-swap/optimistic-apply-2026-09-25.md`).
This is a **host-only** result: no board, glass, or real-finger
observation. Worktree `fix/optimistic-apply-neighbor-race`, base `master`
`4b947d13`.

## The board symptom

Master `4b947d13`, installed as `i3dxi8y0...`. No `optimistic-apply shown`
line anywhere in the journal for an Apply of a theme (`b801d916...`) the
chooser had already neighbour-warmed and then explicitly confirmed by tap.
The durable path alone ran: `activate ... path=socket ms=441`, helper
`activate_generation=356.6ms`.

## Root cause

`ThemeView::poll_prepare_ahead` (`nix/rust-shell-client/src/theme_ui.rs`)
never checked `self.pending`. `main.rs`'s own call site gates it on
`state.theme_view.page == ThemePage::List` -- but tapping a carousel slice
to confirm a preview only *submits* the real `Preview` request; the page
does not move to `ThemePage::Preview` until that request's own reply lands
in `accept()`. So there was a window, however short, where a real,
explicit `Preview` was `self.pending` while the page was still `List` --
and `poll_prepare_ahead` kept running every tick in that window, free to
drain `pending_neighbor_warms` and submit a *different* neighbour's own
warm-up `Preview`.

`ThemeWorker` (`theme_catalog.rs`) processes requests strictly in
submission order, one at a time, on a single background thread. Each
appearance receiver (`AppearanceReceiver::prepared` in `appearance.rs`,
`service.prepared`/`candidate` in `card-shell/appearance.c`) keeps only
its single most-recently-`prepare`d candidate. So: the confirm tap's own
`Preview` request reached the worker first and staged the confirmed
theme's generation in `appearance.prepared`; a neighbour-warm submitted a
tick or two later, before the confirm's own reply was even back, reached
the worker *second* and staged a *different* theme's generation in that
same single slot -- overwriting the confirmed one. By the time Apply ran,
`appearance.prepared()` named the wrong generation, and
`optimistic_apply_skip_reason` correctly returned `generation-mismatch`
(the bug was never in the mismatch check itself -- both `should_apply_
optimistically` and `optimistic_apply_due` were already doing exactly what
their own inputs told them to; the inputs were wrong by the time Apply
read them).

This rules out the other candidates the coordinator listed: the catalog
theme id and the generation id were never confused (`apply_request()`'s
own `expected_generation: preview.generation.clone()` is, and always was,
a generation id, compared against `AppearanceSnapshot.generation` -- also
a generation id); there is no second code path to Activate besides the
Apply button (`theme_ui.rs::hit()`'s only `ThemeIntent::Apply` case is the
Preview page's own footer tap); and there is no env/feature gate on the
Rust-local optimistic check at all (only the compositor's own best-effort
`show` send is gated by `K230_CARD_APPEARANCE_SOCKET`, which does not
affect the Rust-surface decision the board's own log was about).

## Fix

`poll_prepare_ahead` now returns `None` unconditionally whenever
`self.pending.is_some()` -- neither a dwell-driven warm-up nor a
neighbour-queue drain is emitted while any real, explicit request is
awaiting its reply, regardless of how many ticks that takes. The dwell
clock (`prepare_ahead_elapsed_ms`) keeps accumulating in the meantime, so
resuming once `pending` clears never re-waits out an already-elapsed
debounce. The neighbour queue itself is left untouched (not silently
drained and discarded) during the pause.

## Debug logging (the coordinator's own ask)

A new pure function, `optimistic_apply_skip_reason` (`main.rs`), names
exactly why an Apply tap will not show optimistically --
`not-an-activate-request`, `not-prepared`, `generation-mismatch` -- and
`show_theme_optimistically`'s own internal readiness checks now each log
their own reason too (`commit-draw-in-flight`, `video-background`,
`unrenderable-snapshot`, `not-ready-for-a-frame`, `draw-wallpaper-failed`,
`draw-failed`, `flush-failed`). Every skip is logged verbatim as
`rust-shell <ms>ms optimistic-apply skipped reason=<reason>`, so a future
board run that misses the optimistic path names its own cause directly,
without needing to reconstruct a multi-step timeline by hand the way this
bug required. `should_apply_optimistically` is unchanged in signature and
behaviour (its own existing test still passes unmodified); it now simply
delegates to `optimistic_apply_skip_reason`.

## Test-suite proof

- `cargo test --offline` (nix/rust-shell-client): 160+10+14+8+8+5 = 205
  cases, all passing. New:
  - `theme_ui::tests::a_pending_confirm_pauses_every_warm_up_until_its_own_reply_lands`
    -- reproduces the board's own sequence at the `ThemeView` level: load
    a 3-theme list (active at index 1, neighbours 0 and 2 queued), warm
    neighbour 0 and let its reply land, then swipe to and tap-confirm
    theme 2 (the other queued neighbour) -- a real `Preview` now pending.
    Asserts `poll_prepare_ahead` returns `None` for four further ticks
    (mixed centred/uncentred, matching the observed injected-touch
    sequence) while that confirm is pending, that the neighbour queue is
    left intact rather than drained, and that once the confirm's own
    reply lands, `apply_request()` targets exactly the generation that
    reply reported. **Independently confirmed this test fails against the
    pre-fix code** (`git diff`'d the fix out via a one-line `if false &&`
    guard, re-ran: `left: Some((2, Preview { theme_id:
    "222222222222222222222222", background_id: None })) right: None`,
    then restored the fix and re-ran clean) -- this is a real regression
    test, not a tautology.
  - `route_tests::optimistic_apply_skip_reason_names_the_specific_cause`
    -- the four reason strings (`None`/warm, `not-prepared`,
    `generation-mismatch`, `not-an-activate-request`).
- `python3 -m unittest tests.test_omarchy_theme_transaction
  tests.test_theme_helper_daemon tests.test_omarchy_theme_activation
  tests.test_omarchy_theme_sources tests.test_theme_catalog
  tests.test_theme_timing tests.test_card_shell_appearance`: 83 cases, all
  passing (no Python source changed this task).
- `python3 tools/blob-scan.py`: exit 0.
- `openspec validate the-shell-swaps-themes-without-a-python-stall
  --strict`: valid.
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust .#card-shell`: both built cleanly for riscv64
  (`.#card-shell` reused its unchanged cached build -- `appearance.c` was
  not touched by this fix).
- `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`:
  evaluates cleanly.

## Board re-check (task 7.4, re-run)

Same shape as before: dwell/neighbour-warm a theme, swipe to and confirm a
theme the chooser already warmed, tap Apply.

```sh
journalctl -u shell-ui -o json --since "-2min" \
  | grep -E "optimistic-apply|appearance-(prepare|commit)-accepted"
```

Expected now: either an `optimistic-apply shown ms=<N>` line (the fix
worked; `<N>` is the number to compare against the ~100 ms target), or, if
still skipped, an `optimistic-apply skipped reason=<reason>` line naming
exactly why -- which itself is now enough to diagnose any further case
without another multi-step log reconstruction. Not run by this task;
`/dev/ttyACM0` was not opened here.
