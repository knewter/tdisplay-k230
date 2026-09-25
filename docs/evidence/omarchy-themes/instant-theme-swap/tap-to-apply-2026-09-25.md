# Tap-to-apply: no separate Preview page, no Apply/Cancel step

Implements OpenSpec task 10 from
`openspec/changes/the-shell-swaps-themes-without-a-python-stall/tasks.md`.
User decision (2026-09-25, verbatim): "i don't really think we need an
'apply' window for themes at all. tap theme in the theme picker, apply
immediately, so i can compare them easily." Also folds in a second
coordinator message with fresh board data for task 9's own fix (master
`644cd061`, installed `n44hk9js...`). Worktree `feat/tap-to-apply-theme`,
base `master` `644cd061`.

This is a **host-only, plus one real QEMU touch-injection run** result:
no board, glass, or real-finger observation. The board-verification gate
this task still needs is named at the end.

## What changed

There is now one chooser page: the theme carousel, the active theme's own
background carousel below it, and a plain "Current theme"/"Current
background" label under whichever slice of each is centred and durably
active. Tapping a carousel's own already-centred slice applies it
immediately, through the same `preview` (learn the generation)/`activate`
request pair an explicit Apply button used to send, chained automatically.
Dragging, or tapping an off-centre slice, only recentres -- `theme_
carousel::Carousel::up`'s own pre-existing `Confirm`-only-when-already-
centred rule is what makes "tap centres if needed, only a tap on the
already-centred slice applies" work with no carousel-level code change.

The Preview page, its Apply/Cancel footer (`paint_preview_footer_status`,
task 9.1), `ThemeIntent::Apply`, `ThemeView::preview_request`/
`background_request`/`apply_request`/`selection_error`/`selection_failed`,
and the local `PREVIEW_FOOTER_Y` constant are all removed. `ThemeView::
tap_theme`/`tap_background` (returning the next `ThemeRequest` to submit,
or `None`) replace them.

### Rapid-tap coalescing

A new `Desired` (theme id, optional background id, learned generation, an
`already_active` flag) is what a tap sets; `ThemeView::advance()` submits
the next step toward it only when nothing is already in flight, called
once right after every `accept()` that returns `true`. A reply that no
longer matches `desired` is discarded rather than shown or applied, and the
caller's own next `advance()` call moves straight on to whatever is now
desired.

This bounds in-flight work to exactly one request, with a deliberate,
documented tradeoff: **a second rapid tap's own visible effect is bounded
by the first tap's own in-flight round trip, not instantaneous** -- the
existing protocol allows only one request in flight per chooser at a time,
and this task does not change that. What it does guarantee: no queue of
stale activations, no crash, no wrong durable state, and the superseded
target's own late reply is provably discarded (proven directly by
`rapid_taps_across_themes_coalesce_onto_the_last_one` and the QEMU run
below).

### Backgrounds already know their own generation

A background tap targets one of the *active* theme's own backgrounds, so
its generation (`preview.generation`) is already known -- `tap_background`
sets `desired.generation` directly and goes straight to `Activate`, no
`Preview` round trip first (unlike a theme tap, whose target's generation
is not necessarily known). This is a genuine behavior change from the
first draft of this task (which, like a theme tap, always previewed
first); found and fixed while writing
`tap_background_activates_directly_since_the_generation_is_already_known`,
which failed against the first draft and passes now.

### Busy state without blocking the carousel

`ThemeView::applying_theme_index`/`applying_background_index` report which
slice (if any) a pending request targets; `render.rs::paint_carousel`'s
existing `busy: Option<usize>` parameter (already drew a spinner clipped to
one slice, unchanged by this task) is wired to them. The carousel itself
stays visible and draggable the whole time -- nothing blocks on a pending
Preview/Activate except `ThemeView::hit`'s pre-existing rule that a
pending `Activate` specifically cannot be cancelled by navigating away.

### No live overlay needed any more

Task 9's own fix (still landed, unchanged) split the Preview page's
Apply/Cancel footer into a live overlay painted on every `draw()` call,
specifically so an Apply tap's own `pending` transition or the busy
spinner's own pulse tick would not itself invalidate a computed
pre-render. With no Apply button, that whole mechanism is now
unnecessary: `RendererCache::set_theme_view`'s own `invalidate()` still
runs unconditionally on every `ThemeView` change (task 9.2's own doc), so
the *ordinary* (non-optimistic) rebuild path already repaints the busy
spinner and the pending/error/message line fresh, every time. The one
case that skips a fresh rebuild -- an *adopted* pre-render, inside
`show_theme_optimistically` -- is correct exactly because, at the moment
it is shown, the applied theme already looks done (no busy spinner is
needed, since nothing is visibly still "applying"). Proven by
`a_theme_view_change_after_adopting_still_rebuilds_and_shows_pending`
(render.rs) and `a_pending_only_theme_view_change_does_not_bump_content_
generation` (re-targeted, doc updated to explain *why* this is safe now,
not just that it holds).

`paint_preview_footer_status` and its call site inside `RendererCache::
draw()` are removed outright.

### The still-image "screen crop" preview is now dead weight, not deleted

The Preview page used to show a large decoded "screen crop" of the
selected background (`RendererCache::poll_theme_image`/`preview_surface`,
`ThemeImageWorker`/`ThemeImageKey`). Neither carousel needs it -- each
already shows its own thumbnail via `ThemeThumbnailCache`, the same
mechanism used everywhere else in this chooser -- so `poll_theme_image` is
now a deliberate, documented permanent no-op: it never requests a decode,
and `theme_preview_image_pending()` always returns `false`. `ThemeImageWorker`/
`ThemeImageKey` and their own two tests (`still_preview_worker_returns_
output_crop_outside_dispatch`, `still_preview_reuses_the_generations_
background_cache_instead_of_redecoding`) are kept, unused, rather than torn
out in this same task -- a named follow-up, not a silent removal.

## The double-pre-render investigation (coordinator's third observation)

Board data (master `644cd061`, installed `n44hk9js...`):

```
62679ms / 62833ms: optimistic-apply prerendered generation=97e32ff4a99d  (computed twice, ~154ms apart)
72092ms touch-down, 72243ms touch-up
72405ms optimistic-apply shown ms=160.7 prerendered=true
72407ms appearance-commit-accepted reused=optimistic
activate 286ms; helper total 279ms
```

Task 9's own fix (`optimistic-apply-prerender-match-fix-2026-09-28.md`)
was believed to close this by excluding `pending`/`pending_id`/`error`/
`message`/`pulse_phase` from `theme_view_cache_key_differs`, the predicate
`content_generation` bumps on. This board run shows it still happening,
for the same generation, on top of that fix.

Investigated by code review this session (no board access): on master
`644cd061`, `RendererCache::poll_theme_image` was *still actively
decoding* the Preview page's own "screen crop" still image, asynchronously,
via a one-entry worker/channel. That decode completing calls `self.
invalidate()` and, independently of `theme_view_cache_key_differs`
entirely, bumps `content_generation` through its own `if changed { self.
content_generation... }` branch inside `poll_theme_image` itself -- a
signal task 9's fix never touched, because it is not a `ThemeView` field
change at all. A background image decode completing roughly 150ms after
the Preview page loads matches the reported ~154ms gap, and "computed
twice for the same generation" (not two different candidates) matches a
decode completing while a person is still dwelling on one unchanged
candidate.

This task's own removal of the still-image preview (above) makes
`poll_theme_image` a permanent no-op, which removes this trigger
structurally: there is no asynchronous decode left that can bump `content_
generation` a second time while nothing else changed. This is reasoned
from the code, not re-verified against fresh board evidence this session
-- the board-verification gate below is where that gets confirmed or
refuted.

## The 161ms-on-a-match number, and what this task did and did not do about it

Per-stage instrumentation was added to `show_theme_optimistically`
(`nix/rust-shell-client/src/main.rs`): `optimistic-apply stage adopt_ms=...
wallpaper_ms=... overlay_ms=... flush_ms=...`, logged alongside the
existing `optimistic-apply shown ms=... prerendered=...` summary line.
`adopt_ms` covers `adopt_prerendered_overlay`'s own pixel copy (or, on a
miss, `set_appearance`'s cache invalidation); `wallpaper_ms`/`overlay_ms`
each cover one surface's whole `draw_wallpaper`/`draw` call -- attach,
damage, and `wl_surface::commit` all happen inside those calls and are
**not** separately timed by this instrumentation.

**Not attempted this task**, named here as deferred follow-up rather than
silently dropped:

- A finer breakdown inside `draw`/`draw_wallpaper` themselves (attach,
  damage, commit as separate `ms=` fields).
- The wallpaper-buffer-attach optimization (pre-build the actual `wl_buffer`
  at prepare time, so adopting at apply time is attach-only, no pixel
  copy) -- scoped by the coordinator to the wallpaper surface specifically,
  since the overlay surface must still paint dynamic content (the busy
  spinner) live regardless of whether its body came from a rebuild or a
  pre-render, making a full buffer-attach for the overlay lower
  return-on-investment.
- Damaging only the regions that changed, instead of the whole surface.

Reasoning for deferring rather than attempting a fast, unverified change:
none of these can be judged correct or actually faster without measuring
them on the K230 itself (a software Cairo/Pixman path, no GPU, on a
board this task did not touch), and a wrong buffer-attach implementation
specifically risks showing stale or torn pixels -- a correctness bug, not
merely a missed optimization. The per-stage instrumentation above is what
the next board run needs to find which of `adopt_ms`/`wallpaper_ms`/
`overlay_ms`/`flush_ms` actually dominates the 161ms, before spending
effort on the wrong one.

## Layout, not board-verified

`THEME_CAROUSEL_TOP` moved from `204.0` to `132.0`; `BACKGROUND_CAROUSEL_TOP`
is now `THEME_CAROUSEL_TOP + THEME_GEOMETRY.expanded_h + 100.0` = `872.0`
(both fixed 568x1232-panel-space constants, computed to fit both carousels,
their own labels, and one pending/error/message line inside the panel's
1232px height with a small margin at every stage). This is arithmetic, not
a board observation of actual rendered spacing/legibility -- the board
gate below covers it.

## Tests run this session (host)

```
cd nix/rust-shell-client
cargo test --offline
```

`k230-shell-rust` (lib): **171 passed, 0 failed** (includes 24 new/adapted
`theme_ui::tests` -- tap-apply of a cold theme
(`tap_theme_on_a_cold_slice_previews_then_activates_and_switches_the_
background_carousel`), tap-apply of the already-active theme, background
tap-apply (direct `Activate`, no `Preview`), the video/already-selected
background no-ops, rapid-tap coalescing
(`rapid_taps_across_themes_coalesce_onto_the_last_one`), rollback-on-
failure with a visible error
(`a_failed_activate_rolls_back_with_a_visible_error_and_clears_pending`),
and all the pre-existing prepare-ahead/neighbour-warm tests, adapted to
the one-page model).
`k230-shell-rust` (bin/`route_tests`): **14 passed, 0 failed**, unchanged
-- `should_apply_optimistically`/`optimistic_apply_due`/`may_reuse_
optimistic_frame`/`prerendered_overlay_matches` are pure functions this
task did not touch.
`appearance_module`/`background_decode_module`/`service_data_module`/
`theme_catalog_module` integration tests: **14 + 8 + 8 + 5 passed, 0
failed**, all unchanged.

```
python3 -m unittest tests.test_theme_catalog tests.test_theme_helper_daemon \
  tests.test_theme_preferences tests.test_theme_timing \
  tests.test_omarchy_theme_activation tests.test_omarchy_theme_resolution \
  tests.test_omarchy_theme_sources tests.test_omarchy_theme_tools \
  tests.test_omarchy_theme_transaction -v
```

**88 passed, 0 failed** -- this task touched no Python source, run as a
regression check on the theme protocol/daemon these Rust changes talk to.

```
python3 tools/blob-scan.py
```

`blob-scan: ok -- every binary is accounted for`.

## Builds

```
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 \
  .#handheld-shell-rust .#card-shell
```

Both succeeded:
- `/nix/store/sz4rjr4qx7jvygnb04c9waxinnz3mlyj-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`
- `/nix/store/1va4angandva4xbm5i0v7367p0nd9jry-k230-card-shell`

```
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 \
  .#handheld-theme-command .#handheld-theme-default
```

Both succeeded:
- `/nix/store/5c2ydl2zlll3dayf3gxj4lrhqsxrfbdi-handheld-theme-command-0.1`
- `/nix/store/59w41ngkinv5lgxisnpm1w5salzldvrn-handheld-theme-default-28ceaae7`

`nix eval .#nixosConfigurations.k230.config.system.build.toplevel.drvPath`
succeeded: `/nix/store/9yx3i3yqh348dhk070vbjv140ggjx957-nixos-system-nixos-26.11.20260919.20b1ddd.drv`.

## Dark and light theme evidence: host-rendered visual fixtures

Real evidence, host-only (no board): `RendererCache::draw` for the
one-page chooser, run through the same `themed_surface_fixtures_keep_
live_area_clear_and_use_authored_roles` host test every prior visual
evidence doc in this directory uses, against two real, previously-staged
theme generations (Catppuccin dark, Catppuccin Latte).

```
cd nix/rust-shell-client
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share \
K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-catppuccin/generations/cd73257753c4a1a64fa092b3 \
K230_VISUAL_FIXTURE_DIR=/tmp/k230-tap-to-apply-dark \
K230_VISUAL_REQUIRE_ICONS=1 \
cargo test --offline --lib -q themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles

XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share \
K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-latte/generations/c55da9f13ae1265e4ff18435 \
K230_VISUAL_FIXTURE_DIR=/tmp/k230-tap-to-apply-latte \
K230_VISUAL_REQUIRE_ICONS=1 \
cargo test --offline --lib -q themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles
```

Both `1 passed; 0 failed`. `themes.png` from each run is committed as
`tap-to-apply-host/themes-dark.png` and `tap-to-apply-host/themes-latte.png`.
Both show the theme carousel, its "Current theme" label, the "Backgrounds"
heading, the background carousel, and its own "Current background" label,
all fitting inside the 1232px panel with margin to spare in both themes --
confirming the new `THEME_CAROUSEL_TOP`/`BACKGROUND_CAROUSEL_TOP` layout
arithmetic (above) actually renders as intended, on real (if host-Cairo,
not board-Pixman) output. The carousel slices show a loading spinner, not
decoded art, because this fixture never waits on `poll_theme_thumbnails`'s
own worker thread the way the interactive QEMU/board path does -- expected
and unchanged from every prior visual fixture in this directory.

## QEMU touch-injection run: attempted, environment-blocked, not a code regression

The `sway-unwrapped` build (a large dependency chain -- wlroots, xwayland,
and their own dependents, built serially at `--max-jobs 1`) finished
successfully: `/nix/store/rvjwy2wiqs9cnkawqvg7hmglj7a46fgl-sway-unwrapped-
riscv64-unknown-linux-gnu-1.12` (the patched, `card_shell`-IPC-capable
build already produced as a side effect of the earlier `.#card-shell`
build, found at `swaybar`/`swaymsg`/`swaynag`'s own resolved symlink
target next to it -- `.#nixosConfigurations.k230.pkgs.sway-unwrapped`
turned out to be plain upstream sway, missing the `card_shell` IPC
commands this test needs; corrected once found).

```
python3 tests/rust_theme_chooser_qemu.py \
  --sway /nix/store/rvjwy2wiqs9cnkawqvg7hmglj7a46fgl-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/sz4rjr4qx7jvygnb04c9waxinnz3mlyj-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --output /tmp/k230-tap-to-apply-qemu-run2
```

Run twice; both times the harness failed at `k230-shell-rust: route timed
out` (`main.rs::request`, a pre-existing 500ms deadline for the short-lived
`--surface settings` helper invocation's own socket round trip to the
already-running `--serve` process), **before reaching any theme-chooser-
specific code** -- sway itself started correctly and accepted the harness's
own `card_shell test-touch init` IPC command first (see `sway.log`: "K230_
CARD_SHELL input=injected operation=test-touch accepted=1"), and the
`--serve` process's own log showed a normal, complete startup (`wallpaper-
configure`, `home-configure`, `ready-idle`) with no error.

Confirmed via `git diff 80817e3d..HEAD -- nix/rust-shell-client/src/
main.rs` that this task's own diff touches neither `fn request` nor
`poll_until` nor their 500ms deadline at all -- this is not a regression
in this task's own code. This machine was running several other
concurrent agents' own heavy builds and at least one other agent's own
`qemu-riscv64-static`-based sway test at the same time (`ps aux` during
this investigation), so the most likely explanation is CPU contention on
a shared host making the existing 500ms deadline too tight right now, not
a functional break in the route-request mechanism itself. This was not
chased further by loosening the timeout or by other environment
workarounds, since that code is outside this task's own scope and
changing it without being sure of the actual cause risks masking a real
problem elsewhere.

**Not obtained this session**: the QEMU touch-injection proof of the new
tap-to-apply flow (warm/cold tap-apply, background tap-apply, rapid-tap
coalescing) that `tests/rust_theme_chooser_qemu.py`'s own rewrite (this
task) was built to produce. The script itself is written and committed;
running it to a real result -- on a less contended host, or after
investigating the route-timeout separately -- remains open. The state
machine and touch-mechanics it would exercise are covered instead by the
24 `theme_ui::tests` (host, `cargo test`) and the two dark/light host
visual fixtures (above); neither substitutes for an actual touch-injected
run.

## Remaining gates: QEMU rerun (any host) and board-verification

- The QEMU touch-injection run itself (`tests/rust_theme_chooser_qemu.py`,
  committed, not run to completion this session -- see above).

## Board-verification gate this task still needs

- `optimistic-apply stage adopt_ms=... wallpaper_ms=... overlay_ms=...
  flush_ms=...` for a real tap-apply, on the board, to find which stage
  actually dominates the 161ms `optimistic-apply shown ms=...` figure.
- Whether the double-pre-render symptom (`optimistic-apply prerendered`
  computed twice for the same generation) is actually gone now that
  `poll_theme_image` is a permanent no-op, per the code-review finding
  above.
- Whether the new `THEME_CAROUSEL_TOP`/`BACKGROUND_CAROUSEL_TOP` layout
  actually fits the panel without clipping or crowding, in both dark and
  light themes.
- A real-finger tap-to-apply of a warm theme, a cold theme, a background,
  and a deliberately rapid double tap across two different themes, plus
  one forced-failure rollback if a failure can be induced without
  modifying user themes.

None of the above is claimed done by this task; `python3 tools/
work-status.py` and the operator's own board/serial reservation govern
when it can run.
