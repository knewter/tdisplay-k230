# Optimistic Apply: pre-render at prepare time, reuse the durable commit's own frame

Implements OpenSpec task 8 from
`openspec/changes/the-shell-swaps-themes-without-a-python-stall/tasks.md`,
against the coordinator's board re-run of the occlusion fix
(`docs/evidence/omarchy-themes/instant-theme-swap/
optimistic-apply-occlusion-fix-2026-09-27.md`). This is a **host-only**
result: no board, glass, or real-finger observation. Worktree
`feat/optimistic-apply-prerender`, base `master` `e2ba1d7e`.

## The board result that motivated this

Master `e2ba1d7e`, installed as `s376wb46...`. The optimistic path now
fires: `optimistic-apply shown ms=222.7` (224 ms after touch-up), but:

1. The 222.7 ms *is* the render cost itself -- a full software redraw of
   the wallpaper and, more expensively, the settings panel's own themed
   chrome (icons, palette-derived colors). Tap-to-visible was still about
   375 ms from touch-down.
2. The optimistic draw left no free wallpaper buffer, so the durable
   commit's own `draw_wallpaper` failed
   (`appearance-commit-rejected draw-wallpaper-failed`), forcing a full
   prepare+commit retry that roughly doubled `activate_generation`'s own
   reported time (452.4 ms).

## Why the overlay redraw is the dominant cost (found by code review)

`draw_wallpaper()`'s own expensive step, `BackgroundCache::render(...)`,
is a warmed cache hit by Apply time (the confirm-preview's own `prepare`
already populated it) -- effectively a `memcpy`. The overlay's own
`draw()`, by contrast, calls `draw_shm_with_icons()` (a full Cairo scene:
icon decode/compositing, palette-derived fills, text layout) whenever
`self.route`/`width`/`height`/`scroll` do not already match the cached
`static_pixels` -- and `show_theme_optimistically`'s own
`self.renderer.set_appearance(...)` call unconditionally invalidates that
cache (`RendererCache::invalidate()` clears `route`/`static_pixels`),
forcing exactly this rebuild synchronously, on the Apply tap's own
critical path. Confirmed by reading `render.rs`'s `scene()`: the settings
panel's own background/border/accent genuinely are palette-driven
(`Route::Settings` reads `theme`/`palette_rgb_or`/`theme_brush` for its
own `"controls"` section), so this repaint is real work, not a bug to
remove -- the fix is *when* it happens, not whether it happens.

## What changed

### 8.1: a third wallpaper buffer

`draw_wallpaper()`'s own buffer-pool exhaustion check raised from `>= 2`
to `>= 3` (the overlay's own pool was already bounded to 3); the SHM
pool's initial-size hint raised `* 5` to `* 6` (an estimate only --
`SlotPool::resize`'s own doc: "the pool automatically resizes when you
allocate new slots", confirmed by reading
`smithay-client-toolkit-0.20.0/src/shm/slot.rs`). This alone, independent
of pre-rendering, stops the durable commit's own redraw from ever again
failing merely because an optimistic draw still holds a buffer the
compositor has not released.

### 8.2: `RendererCache` gains a candidate-render primitive and a freshness counter

- `content_generation: u64` -- bumped by `set_theme_view`/`set_services`/
  a real `set_drawer_pressed` change/a `poll_theme_image`- or
  `poll_theme_thumbnails`-detected change (every input besides the theme
  itself that a scene render depends on), and deliberately *not* by
  `set_appearance`/`set_icon_theme` -- a candidate render is expected to
  differ from the live theme on purpose.
- `render_candidate_overlay(theme, route, width, height, apps)` -- computes
  a full overlay-scene raster for an arbitrary `theme`, using a *fresh*,
  isolated `IconCache` (never `self.icons`) and every other input read
  live from `self` (`services`/`chooser`/`pressed`/`preview_surface`/
  `preview_error`/`thumbnails`). Provably never mutates `self.theme`/
  `self.icons`/`static_pixels`/`route` -- see the test below.
- `adopt_prerendered_overlay(theme, route, width, height, pixels)` --
  seeds the live cache directly from an already-computed raster, so
  `draw()`'s own next call sees a cache hit (no rebuild).

### 8.3: computed once, after this tick's own flush, only for a matching prepared candidate

`main.rs`'s event loop computes the pre-render at most once per
`(generation, route, geometry, content_generation)`, only when the
Preview page's own currently-loaded candidate is already the receiver's
own `prepare`d snapshot -- the same precondition Optimistic Apply itself
checks, so this never triggers preparing a cold generation early, and
never fires for a merely-warmed neighbour still being browsed past.
Placed *after* that tick's own `queue.flush()`, deliberately: the render
is real, synchronous Cairo cost (the same ~222 ms Apply's own optimistic
show pays without it), and running it earlier in the same iteration would
delay sending whatever that tick's own draw already queued -- including
the very Preview-page frame that made this eligible in the first place.
Skipped entirely while an Activate is already in flight.

### 8.4: Apply consumes it, or falls back

`show_theme_optimistically` always takes the one bounded pre-render slot
(matching or not, so a stale one never lingers for a later Apply). On an
exact match (generation, route, geometry, `content_generation`), it
adopts the pre-render instead of calling `set_appearance` -- skipping the
rebuild entirely. On any mismatch (a resize, a page/route change, or
anything `content_generation` covers having changed since it was
computed), it falls back to `set_appearance` exactly as before this task
-- the coordinator's own "invalidate on geometry, page or content change"
requirement, satisfied by construction rather than by an ad hoc check list.
The `optimistic-apply shown ms=...` log now carries `prerendered=true/false`.

### 8.5: the durable commit reuses an already-shown optimistic frame

`ShellClient::optimistic_active: Option<String>` records the generation a
successful optimistic show just flushed. The very next `Commit`/
`Rollback` event's own handling checks `may_reuse_optimistic_frame` (pure:
true only for a `Commit` whose own generation matches exactly -- a
`Rollback`'s own target is by definition the *previous* generation, never
the one just shown) and clears `optimistic_active` unconditionally either
way, so it can only ever be read by that one next event. A match skips
`draw_wallpaper`/`draw`/`flush` entirely and goes straight to the same
video-state bookkeeping (`adopt_committed_video_state`, factored out of
what was inline in the redraw-success branch so both paths share it
verbatim) and the ack -- still sent only after a real, already-flushed
frame, never before one; the "ack only after a real frame" invariant is
unchanged, since the *reused* frame was itself real.

## Why this is safe (the invalidation argument)

Every input `render_candidate_overlay` reads besides the theme is either
captured in `content_generation` (bumped on every relevant change) or
passed explicitly (`route`/`width`/`height`, matched exactly at Apply
time). A stale pre-render can therefore only ever be *rejected* (falling
back to a fresh rebuild), never silently *shown* -- there is no path where
a mismatch on any tracked field still adopts the pre-render. The
durable-commit reuse is bounded even more tightly: `optimistic_active` is
read by, and cleared by, the very next `Commit`/`Rollback` event only,
so a stale reference cannot persist across more than one such event even
in principle.

## Test-suite proof

- `cargo test --offline` (nix/rust-shell-client): 163+13+14+8+8+5 = 211
  cases, all passing. New:
  - `render::tests::content_generation_bumps_on_content_changes_but_not_
    on_appearance_changes` -- proves both halves of the freshness
    contract.
  - `render::tests::render_candidate_overlay_never_mutates_the_live_cache`
    -- computes a visibly different candidate, then proves a subsequent
    ordinary draw with the *original* live theme still produces
    byte-identical pixels to a pre-candidate baseline, with no extra
    rebuild.
  - `render::tests::adopt_prerendered_overlay_is_a_cache_hit_with_the_
    candidates_own_pixels` -- proves adoption is a genuine cache hit
    (`rebuild_count()` unchanged) and the shown frame is exactly the
    pre-rendered candidate's own bytes.
  - `route_tests::prerendered_overlay_matches_requires_every_field_to_
    agree` -- generation/route/width/height/content_generation, each
    independently causing a rejection on mismatch.
  - `route_tests::may_reuse_optimistic_frame_only_for_a_commit_matching_
    exactly` -- the Commit-only, exact-match, `None != None` cases.
- `python3 tools/blob-scan.py`: exit 0 (no Python source touched by this
  task).
- `openspec validate the-shell-swaps-themes-without-a-python-stall
  --strict`: valid (adds two scenarios to the existing "A warm Apply
  shows the new appearance ahead of the durable commit" requirement,
  covering pre-render invisibility-before-Apply and invalidation).
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust`: built cleanly for riscv64.
- `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`:
  evaluates cleanly.

## What was deliberately not attempted

- **The wallpaper frame is not separately pre-rendered into a spare
  buffer.** Code review found `draw_wallpaper()`'s own expensive step
  already a cache hit by Apply time (the confirm-preview's own `prepare`
  already warmed `BackgroundCache`), so a separate wallpaper pre-render
  buffer would add real complexity (a second isolated render path, a
  second buffer to manage and invalidate) for a cost that measurement
  attributes almost entirely to the overlay, not the wallpaper. If a
  future board run's `prerendered=true` case still shows meaningful
  `ms=`, that would be the evidence to revisit this.
- **The compositor's deck brushes.** The coordinator's message notes the
  compositor "already does" pre-render its own deck brushes (task 3.1b's
  `appearance_prepare`/`card_brush_scene` adopt path, landed earlier in
  this change) -- nothing new needed there.
- **A touch-driven QEMU proof of the pre-render path end to end.** Same
  limitation as the prior two stages: the existing chooser QEMU harness's
  synthetic `K230_THEME_COMMAND` never populates a real `prepared`
  snapshot, so it cannot exercise `content_generation`/
  `render_candidate_overlay`/`adopt_prerendered_overlay` at all. Coverage
  here is unit-level (`render.rs`'s own tests, which do exercise real
  Cairo rendering against real pixel buffers, just not through a real
  Wayland surface) plus code review; not claimed as an integration pass.
- **Retrying a failed pre-render on the same tick.** `render_candidate_
  overlay` failing (defensive; an already-prepared, already-validated
  snapshot should not fail this) leaves no cached entry, so the same
  tick-by-tick check retries every subsequent tick rather than
  backing off. Accepted as a minor inefficiency in an expected-never
  path, not fixed here.

## Board commands for the coordinator (task 8.6)

```sh
journalctl -u shell-ui -o json --since "-2min" \
  | grep -E "optimistic-apply|appearance-commit-(accepted|rejected)"
```

Same steps as before: dwell/neighbour-warm or confirm-preview a theme
long enough for its own prepare to land (this now also warms the overlay
pre-render on the following tick -- look for a new
`optimistic-apply prerendered generation=...` line before the Apply tap),
then tap Apply. Expected: `optimistic-apply shown ms=<N> prerendered=true`
with `<N>` close to the ~30 ms target; no `appearance-commit-rejected
draw-wallpaper-failed`; the durable commit's own log showing
`appearance-commit-accepted reused=optimistic` instead of a second full
redraw; `activate_generation` no longer carrying a retry's doubled cost.
For the invalidation case: change something (rotate/resize, navigate away
and back, or dwell long enough for an unrelated content change) between
the confirm-preview and Apply, and confirm `prerendered=false` with a
normal (not stale) rebuild -- never incorrect content shown. Not run by
this task; `/dev/ttyACM0` was not opened here.
