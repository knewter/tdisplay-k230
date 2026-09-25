# Optimistic Apply: splitting the footer so a pre-render can actually match

Implements OpenSpec task 9 from
`openspec/changes/the-shell-swaps-themes-without-a-python-stall/tasks.md`,
fixing the coordinator's board re-run of task 8's pre-render
(`docs/evidence/omarchy-themes/instant-theme-swap/
optimistic-apply-prerender-2026-09-27.md`). This is a **host-only**
result: no board, glass, or real-finger observation. Worktree
`fix/optimistic-apply-prerender-match`, base `master` `c6f0237a`.

## The board symptom

Master `c6f0237a`, installed as `vq6vkvqz...`.

```
63734ms / 63887ms: optimistic-apply prerendered generation=6626f904f843  (computed twice)
73130ms touch-down (Apply), 73285ms touch-up
73510ms optimistic-apply shown ms=224.0 prerendered=false
73512ms appearance-commit-accepted reused=optimistic   (the reuse itself works)
activate 354ms; helper total 347ms
```

After applying, the screen correctly showed "Theme applied"/"Apply
again" -- the *content* was right, only the *timing* was back to a full
~224ms rebuild.

## Root cause

`submit_theme()` (called synchronously, in the same touch-up handling
that submits the durable `Activate`) always ends with `self.theme_
dirty()`, which calls `self.renderer.set_theme_view(self.theme_view.
clone())` -- and by that point `theme_view.pending` is already `Some(
Activate{...})`. `RendererCache::set_theme_view` bumped `content_
generation` unconditionally on every call. So the Apply tap itself --
before Optimistic Apply's own freshness check ever ran -- always
invalidated the pre-render it was about to need. The double `
optimistic-apply prerendered` computation (63734/63887, ~150ms apart,
matching `THEME_PULSE_INTERVAL`) was the same mechanism: the busy-
spinner pulse tick (gated on `theme_thumbnails_pending()`/`theme_
preview_image_pending()`/a pending Activate) also calls `theme_dirty()`,
also bumping `content_generation` unconditionally.

Fixing *only* the bump condition, without anything else, would have
introduced a real regression: `show_theme_optimistically`'s adopted
pre-render is what the durable commit's own reuse (task 8.5) then shows
*permanently* (reuse skips redrawing). A pre-render computed while idle
(`pending: None`) bakes in "Apply"/"Apply again"; if content_generation
stopped tracking `pending` without also fixing what gets painted, an
adopted pre-render would show the wrong footer text for good, never
corrected.

## What changed

### 9.1: split the footer into a live overlay

The Preview page's Apply/Cancel footer (pressed highlight, Apply
button text/color/spinner across idle/applying/applied, and the
`Preparing…`/error/message status line) is extracted out of
`paint_theme_chooser` into a standalone `paint_preview_footer_status`,
and painted by `RendererCache::draw()` itself, live, on *every* call --
after the cached-body shift-copy, on top of whatever that body is
(freshly rebuilt or an adopted pre-render). `paint_theme_chooser` no
longer paints any of it. The List page's own status line is untouched
(still baked into its cached body, since it has no live overlay of its
own and doesn't need one for this task).

This is checked by `RendererCache::draw` reading `self.chooser` directly
(not by threading a new parameter through `main.rs`), so `ShellClient::
draw`/`draw_wallpaper` in `main.rs` needed **no changes at all** -- every
existing caller of `RendererCache::draw` automatically gets the correct,
live footer, including all 25 pre-existing `render::tests` cases that
exercise it through the same public method, which all still pass
byte-for-byte unmodified.

### 9.2: `content_generation` no longer tracks the fields that moved

A new pure `theme_view_cache_key_differs(old, new)` compares only what
the cached body (now that the footer is split out) actually depends on:
`page`/`list`/`preview`/`theme_pressed`/`background_pressed` exactly,
`theme_position`/`background_position` with the same small tolerance
`RendererCache::draw`'s own `scroll` check already uses. `set_theme_view`
bumps `content_generation` only when this says something changed;
`invalidate()` itself stays unconditional, so an ordinary live `draw()`
still rebuilds on every theme_view change exactly as before this task --
only `content_generation`, read solely by Optimistic Apply's own
freshness check, is now this much narrower. This also closes the
coordinator's own third observation directly: a pulse-only tick can no
longer bump it either.

### 9.3: the pre-render trigger requires nothing pending at all

Previously excluded only `Some(Activate{..})`; now requires `theme_view.
pending.is_none()` outright. Reasoning: the background carousel's own
busy spinner (a `Preview{background_id: Some(_)}` request in flight) is
still baked into the cached body -- 9.1's live overlay covers only the
Apply/Cancel footer and status line, not that spinner -- so computing a
pre-render while a background selection was still pending risked caching
a stale busy indicator nothing would ever repaint live. Requiring
nothing pending closes this by construction instead of adding a second
live overlay for a narrower case.

### 9.4: `prerendered=false` names which field mismatched

A new `prerendered_overlay_mismatch_reason` returns `no-prerender-
computed`, `generation`, `route`, `geometry`, or `content-changed` (in
that fixed order, so a candidate failing several checks still reports
one reproducible reason), plus `not-on-settings-route` for the outer
defensive check in `show_theme_optimistically`. `prerendered_overlay_
matches` now delegates to it, so the boolean and the reason can never
drift apart. Logged as `optimistic-apply shown ms=... prerendered=false
reason=<this>`.

## Why this is still safe

`paint_theme_chooser`'s own cached output is now provably independent of
`pending`/`pulse_phase` (they are simply never read by the code left in
it), so excluding them from `content_generation` cannot make a stale
*cached body* look fresh -- there is nothing left in the body that could
be stale with respect to them. Correctness for the footer/status itself
comes from `RendererCache::draw()` painting it live, unconditionally, on
every call regardless of cache-hit or adopted pre-render -- there is no
path that shows a `static_pixels`-baked (or pre-rendered) footer at all
any more.

## Test-suite proof

- `cargo test --offline` (nix/rust-shell-client): 165+14+14+8+8+5 = 214
  cases, all passing. New:
  - `render::tests::adopted_prerender_still_shows_the_live_pending_state_
    via_the_overlay` -- adopts a pre-render computed while idle, then
    changes only `pending` (matching a real Apply tap) and asserts the
    resulting frame differs from the idle one (the live "Applying…"
    overlay actually painted). **Independently confirmed this test fails
    without the fix**: temporarily disabled the live-overlay block (`if
    false && route == Route::Settings`), re-ran, got the exact
    stale-idle-button pixels (`assert_ne!` failed, showing byte-identical
    idle/activating frames); restored the fix, re-ran clean.
  - `render::tests::a_pending_only_theme_view_change_does_not_bump_
    content_generation` -- pending+pulse change alone: no bump; a real
    content change (a different preview): still bumps.
  - `route_tests::prerendered_overlay_mismatch_reason_names_the_specific_
    field` -- all five reason strings.
  - All 25 pre-existing `render::tests` cases (including the ones this
    task's own predecessor added) pass unmodified, confirming the split
    is output-equivalent everywhere already covered.
- `python3 tools/blob-scan.py`: exit 0 (no Python source touched by this
  task).
- `openspec validate the-shell-swaps-themes-without-a-python-stall
  --strict`: valid.
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust`: built cleanly for riscv64.
- `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`:
  evaluates cleanly.

## What was deliberately not attempted

- **The background carousel's own busy spinner is still not split into
  a live overlay.** Task 9.3 avoids the correctness risk by simply never
  pre-rendering while it could be active, rather than adding a second
  live-overlay region for a narrower, rarer case (a background selection
  and an Apply-eligible generation being simultaneously pending). If a
  future board run shows this actually costing meaningful `prerendered=
  false` misses in practice, that would be the evidence to revisit it.
- **A touch-driven QEMU proof of the fix end to end.** Same limitation as
  every prior stage of this feature: the existing chooser QEMU harness's
  synthetic `K230_THEME_COMMAND` never populates a real `prepared`
  snapshot, so it cannot exercise this code at all. Coverage here is
  unit-level (real Cairo rendering against real pixel buffers, including
  a test independently confirmed to fail against the pre-fix code) plus
  code review.

## Board commands for the coordinator (task 9.5)

```sh
journalctl -u shell-ui -o json --since "-2min" \
  | grep -E "touch-up|optimistic-apply|appearance-commit-(accepted|rejected)"
```

Same steps as before: dwell/neighbour-warm or confirm-preview a theme
long enough for its own prepare (and now its own overlay pre-render) to
land, then tap Apply. Expected: at most one `optimistic-apply
prerendered` line per genuine change while dwelling (not a pulse-driven
double); `optimistic-apply shown ms=<N> prerendered=true` with `<N>`
close to the ~30 ms target; the on-screen footer correctly reading
`Applying…` then the settled state, never stuck on a stale `Apply`. If
`prerendered=false` still occurs, its own `reason=` field states which
check failed directly. Not run by this task; `/dev/ttyACM0` was not
opened here.
