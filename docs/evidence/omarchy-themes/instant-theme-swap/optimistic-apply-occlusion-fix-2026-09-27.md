# Optimistic Apply: the overlay's own frame_pending gate, and the ~300 ms gap

Implements OpenSpec tasks 7.6-7.8 from
`openspec/changes/the-shell-swaps-themes-without-a-python-stall/tasks.md`,
addressing the coordinator's board re-run of the neighbour-warm-race fix
(`docs/evidence/omarchy-themes/instant-theme-swap/
optimistic-apply-neighbor-race-fix-2026-09-26.md`). This is a **host-only**
result: no board, glass, or real-finger observation. Worktree
`fix/optimistic-apply-occlusion-and-latency`, base `master` `2b575dba`.

## The board symptom

Master `2b575dba`, installed as `nmdf96j1...`. The race is fixed and the
decision is reached, but:

```
71028ms touch-down 0 329.5 1081.6   (Apply)
71327ms optimistic-apply skipped reason=not-ready-for-a-frame
71428ms appearance-commit-accepted
71530ms theme-command activate b801... path=socket ms=346
```

## Problem 1: `reason=not-ready-for-a-frame`

### Root cause

`cd36242b` ("Stop gating wallpaper redraw on its own stale frame
callback") already established the relevant rule: a compositor is not
obligated to keep sending frame-done callbacks for a surface nothing is
presently compositing, so a `frame_pending` flag can stay stuck
indefinitely for an occluded surface. That commit fixed `draw_wallpaper()`
's own entry guard and the durable commit path's own `ready` predicate
for the *background/wallpaper* layer. It never touched `draw()` -- the
theme chooser's own *overlay/settings* surface -- whose entry guard still
read:

```rust
if self.appearance_pending || !self.configured || self.frame_pending || self.layer.is_none() {
    return false;
}
```

`show_theme_optimistically`'s own separate readiness pre-check (copied
from what looked, at a glance, like the already-fixed durable path)
carried the identical gap:

```rust
let overlay_ready = self.layer.is_none() || (self.configured && !self.frame_pending);
if !(self.wallpaper.configured && overlay_ready) { ... skip ... }
```

Re-reading the durable commit path's own `ready`/`overlay_ready`
computation (`serve`'s own `pending_appearance` handling) found the exact
same `!state.frame_pending` term still present there too -- it was never
actually fixed for the overlay case; it merely never surfaced as a
*failure*, because that code path retries for up to 1400 ms, giving the
overlay's own frame time to clear across several ticks. Optimistic Apply's
own check is a single, one-shot attempt with no retry (by design: a missed
optimistic frame costs nothing but the optimism itself, since the real
commit/rollback event still lands), so the identical gap that the durable
path merely *hid* behind its retry window made Optimistic Apply fail
outright.

### Fix

A new pure function, `redraw_entry_ready(appearance_pending, configured,
layer_present)` (`nix/rust-shell-client/src/main.rs`), is `draw()`'s
entry guard now -- structurally the same fix `cd36242b` already applied to
`draw_wallpaper()`, extended to the surface that fix never touched. Its
signature is deliberately the regression proof: there is no parameter to
gate on any surface's own outstanding frame callback at all, so this
specific mistake cannot be reintroduced by accident.

`show_theme_optimistically`'s own separate `overlay_ready`/`ready`
pre-check is removed entirely. It now attempts `draw_wallpaper()`/`draw()`
directly and reads their own boolean return values -- exactly what the
durable commit path's own `ready == true` branch already does -- relying
on the buffer pool's free-slot bookkeeping inside each of those functions
as the correct and sufficient gate. There is deliberately no 1400 ms retry
window here: unlike a durable commit, a missed optimistic frame is not a
failure requiring recovery, so there is nothing to wait out.

The durable commit path's own `overlay_ready` term is fixed the same way
(drops `!state.frame_pending`, keeps `state.configured`), closing the
identical latent gap there too -- previously invisible behind its own
retry loop, but a real source of up to 1400 ms of needless delay in the
same occluded-overlay scenario, now removed for the durable path as well.

## Problem 2: ~300 ms from Apply touch-down to the optimistic decision

### What the code review found (and did not find)

Traced every step between the touch event and the optimistic decision for
a synchronous stall:

- `theme_action(ThemeIntent::Apply)` -> `apply_request()` -> `submit_theme()`
  runs entirely on the Wayland/touch-handling thread, synchronously, in
  the same call chain as touch-up recognition itself -- `theme_apply_
  tapped_at` is set essentially at the same instant as the existing
  `touch-up <id>` log line, not meaningfully later.
- `ThemeWorker::try_submit` uses `try_send` (never blocks) on a bounded
  channel; a full queue returns an error immediately, not a stall.
- `AppearanceSnapshot::clone()` carries no pixel data (palette/section
  tokens, paths, strings only -- the decoded wallpaper bytes live in
  `BackgroundCache`, keyed separately), so cloning the prepared snapshot
  for the optimistic check is not a plausible source of hundreds of
  milliseconds.
- After the fix above, the draw calls themselves no longer wait on any
  frame callback; a buffer-pool cache hit should make them fast, but a
  genuine Cairo repaint of the chooser's own overlay is real work on the
  K230's in-order core, and `appearance_renderable`'s own wallpaper decode
  is a real image decode if the panel-sized cache entry is not already
  warm (it should be, from the confirm-preview's own `prepare` moments
  earlier, but this was not independently measured).

None of this conclusively proves *where* the ~300 ms went, and this task
does not claim to have found it. The most likely remaining candidates are
outside this code path entirely (raw touch-event delivery latency through
the compositor/kernel input stack) or inside the draw calls' own real
rendering/decode cost on real hardware -- neither of which host review can
distinguish from Wayland event-loop scheduling without board timing data.

### What this task does instead: instrumentation

Every `optimistic-apply skipped reason=...` and `optimistic-apply shown`
log now carries `ms=<elapsed since tapped_at>`, measured at the exact
point each outcome is decided (including immediately before any draw is
attempted, and again if a draw/flush itself fails). A board re-run with
this instrumentation, cross-referenced against the existing `touch-up
<id>` log, will show:

- whether the ~300 ms is already present in the *first* `ms=` value this
  function ever logs (proving it is input-delivery/dispatch latency,
  before this code runs at all), or
- whether it grows across the function's own few log points (proving it
  is inside the draw/flush calls themselves).

This is deliberately the same "instrument first, then fix with evidence"
approach `cd36242b` itself used; guessing at a fix for problem 2 without
that data risked solving the wrong thing.

## Test-suite proof

- `cargo test --offline` (nix/rust-shell-client): 160+11+14+8+8+5 = 206
  cases, all passing. New:
  `route_tests::redraw_entry_never_gates_on_a_surfaces_own_outstanding_
  frame_callback` -- proves `redraw_entry_ready`'s four cases (ready;
  refused while a real transaction's own draw is in flight; refused
  before the surface is ever configured; refused while unmapped), none of
  them involving a frame-pending flag by construction.
- `python3 tools/blob-scan.py`: exit 0 (no Python source touched by this
  task).
- `openspec validate the-shell-swaps-themes-without-a-python-stall
  --strict`: valid.
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust`: built cleanly for riscv64.
- `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`:
  evaluates cleanly.

## What was deliberately not attempted

A full regression test reproducing "an occluded wallpaper/overlay with
`frame_pending` stuck" end to end (real Sway + real Rust shell under
QEMU, a maximized occluding surface, real touch injection through the
chooser) was not built. `redraw_entry_ready`'s own test is a structural
proof at the unit level (this function cannot depend on a frame-pending
flag because its signature does not accept one), matching this task's
time budget; a true end-to-end proof would extend `tests/
test_theme_commit_under_occlusion_runtime.py`'s own occlusion harness (it
already proves this exact bug class for the durable path, per `cd36242b`)
to also drive the chooser's own touch-triggered Apply path rather than
calling `theme_transaction.activate_generation()` directly -- the same
gap already named in the prior evidence doc for the neighbour-warm-race
fix, not closed by this task either.

## Board commands for the coordinator (tasks 7.6 re-check and 7.8)

```sh
journalctl -u shell-ui -o json --since "-2min" \
  | grep -E "touch-up|optimistic-apply|appearance-(prepare|commit)-accepted"
```

Same steps as before: dwell/neighbour-warm a theme, swipe to and confirm
it, tap Apply. Expected now: no more `reason=not-ready-for-a-frame`
(unless a genuinely different readiness condition is false). Every
`optimistic-apply skipped`/`shown` line now carries its own `ms=`, timed
from the Apply tap; comparing that to the `touch-up <id>` timestamp
immediately before it is what will localise problem 2's remaining ~300 ms
to either "before this code runs" or "inside this code's own draw/flush
work." Not run by this task; `/dev/ttyACM0` was not opened here.
