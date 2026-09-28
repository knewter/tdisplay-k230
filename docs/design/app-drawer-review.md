# App drawer review and redesign — September 2026

Requested by the operator: "when i swipe down in the app drawer to scroll
back up, it closes the drawer that's no good also review the design of the
app drawer it's fuggin awful as is performance." A first pass at the
redesign and performance work (grid 3→4 columns, unchanged tile plates, a
label raster cache) was reviewed by the coordinator and correctly rejected:
"it's the same design with a 4th column" and the estimated board frame
time (95-236ms) "isn't a fix." This document describes the actual redesign
and performance work that replaced it. Scope: `nix/rust-shell-client/src/
navigation.rs`, `service_ui.rs`'s Drawer-only functions, `main.rs`'s Drawer
touch handlers, `render.rs`'s Drawer paint block, and `icon.rs`. Out of
scope: the theme picker/carousel, the Settings brightness row and the
shade (owned by concurrent branches), and Home/dock (a separate grid,
`home_grid.rs`, not touched here). The scroll-reversal-closes-the-drawer
bug fix landed separately, in its own commit, before this work; it is not
re-described here beyond what this redesign builds on top of it (§1).

This repo already carries `docs/design/shell-polish-review-2026-09.md`,
which reviewed the whole shell including the drawer (§3) three days before
this document. That review confirmed **search is deferred by an explicit
prior decision** (`the-handheld-presents-a-coherent-shell/design.md`
decision 2, restated in `shell-ux-critique.md` §4) — this redesign
reopens that decision, at the coordinator's explicit direction, and
implements search (§3).

No board or `/dev/ttyACM0` access was used to write this document. Every
claim is a direct source read of this worktree, a committed evidence
file, or a screenshot rendered on this host via `k230-shell-rust
--render-fixture drawer OUTPUT.png` (see §5) — a real Cairo/Pixman render
of the real paint code, not a mockup. Board and real-finger claims are
marked UNVERIFIED throughout.

## 1. What carries over from the bug fix

The drag-to-close fix (a separate, earlier commit on this branch) is
unchanged by this redesign: `Contact::scrolled_away` still gates
`DrawerNavigation::up`'s release-only dismiss check, and
`service_ui::drawer_close_candidate_after_scroll` still gates the live
"follow the finger" close drag. This redesign does change *where* the
close-eligible "handle" zone sits, since the header it used to be carved
out of no longer exists (§2.3): `service_ui::drawer_handle_zone`
(`service_ui.rs:275`) now spans the whole, much shorter top chrome
(`navigation::panel_top`..`navigation::list_top` — handle plus search
field, both interactive and neither one prose a scrolling thumb could
brush against), replacing the earlier bug-fix commit's narrower
`DRAWER_HANDLE_HEIGHT` constant. The invariant the bug fix established
(the grid itself is close-eligible only once already scrolled to its own
top, and a gesture that scrolls away is permanently disqualified) is
untouched.

## 2. The actual redesign

### 2.1 What the rejected first attempt got wrong

Coordinator's own words: "it's the same design with a 4th column." Correct
— the first attempt kept every per-app tile as a themed rounded-rect card
(`service_card`) with an icon-card inset inside it, the full "YOUR DEVICE /
All apps / Everything installed…" header, and the "Swipe down to return to
cards" footer, and only changed `COLUMNS`/icon pixel sizes. None of that
reads as a Pixel-launcher-style drawer; it reads as the same drawer with
a different grid arithmetic. This version removes all of it.

### 2.2 Per-app tiles: icon and label only, no plate

`paint_drawer_tile` (`render.rs:1640`) no longer calls `service_card` (the
rounded-rect card primitive) for the app tile at all. Each cell paints
exactly: a 64px icon (`DRAWER_ICON_SIZE`, `render.rs:49`), and a
single-line, ellipsized 14px label (`DRAWER_LABEL_SIZE`, `render.rs:55`)
below it, both directly on the sheet's own background.

**Icon fallback: a round, theme-tinted circle, tuned twice on review.**
First round: a low-alpha (0.30) accent tint over this dark sheet's own
background, which coordinator review correctly called "dark and flat."
Now: a stronger 0.55-alpha accent fill (a tonal container, not a faint
tint) with the initial in `style.text` (bright, guaranteed-contrasting —
accent-on-accent would fight the very contrast a tonal container needs),
not the accent colour again.

Second round: an initial screenshot (`docs/evidence/app-drawer/
redesign-real-icons.png`, first revision) showed the fallback circle on
nearly every real application — `2048`, `Clock`, `Editor`, `Htop`, `Net`,
`NetHack`, `Timer`, `Video`, `Weather`, only `btop++` resolving a real
icon. Investigated per the coordinator's own request (full table in
`docs/evidence/app-drawer/README.md`): **a harness gap in this change's
own evidence-gathering, not a resolution failure.** Every one of those
`Icon=` names resolves against the board's real, bundled Yaru-based
theme (`nix/handheld-theme-icons`) via its already-correct `Inherits`
chain (`icon.rs::theme_lookup`, unchanged) — three of them (`htop`,
`foot`, `mpv`) only because the real session's own `XDG_DATA_DIRS`
(`nix/shell.nix`'s `launcherEnvironment`) lists those specific packages'
own `share/` trees as individual roots, which the first screenshot's
hand-assembled `XDG_DATA_DIRS` never included, and never set
`K230_ICON_THEME` either (defaulting to plain `hicolor`, not this
device's actual `Yaru-purple`). Re-rendered with the *exact* real
`XDG_DATA_DIRS` string (extracted directly from the built
`k230-touch-launcher` binary, not hand-assembled) and
`K230_ICON_THEME=Yaru-purple`: every application in the catalog now
resolves a real icon — zero fallback circles.

Fixed anyway, as defense in depth, since a future application's icon
name might genuinely not exist in the bundled theme: `paint_drawer_tile`
retries a generic `utilities-terminal` icon (confirmed present in the
bundled theme) for any terminal-emulator-like application
(`catalog::terminal_like`, reading `Terminal=`/`Categories=` directly
from the raw desktop file) before falling all the way back to the letter
circle. Not currently triggered by this catalog, given the harness fix
above — every application's own named icon already resolves.

### 2.3 Header and footer: replaced with a handle and a search field

The "YOUR DEVICE" eyebrow, "All apps" heading, "Everything installed…"
subtitle, and the "Swipe down to return to cards" footer are gone
entirely — removed from `scene()`'s Drawer branch, which now returns
early into a dedicated `paint_drawer` (`render.rs:1769`) that never calls
any of that code. In their place: a slim drag handle
(`navigation::handle_rect`, `navigation.rs:56`) and a rounded, pill-shaped
"Search apps" field (`navigation::search_field_rect`, `navigation.rs:64`),
both painted by `paint_drawer_chrome` (`render.rs:1695`). Total top chrome
height: 86px, versus the old header's ~181px.

### 2.4 Search: implemented, not deferred

Reopening `shell-ux-critique.md`'s deferred-search decision, at the
coordinator's explicit direction. Tapping the search field focuses it
(`service_ui::DrawerSearch::focus`, `service_ui.rs:92`) and raises a
compact, lowercase-only on-screen keyboard anchored to the sheet's own
bottom edge (`navigation::SEARCH_KEYBOARD_HEIGHT = 300px`,
`navigation.rs:85`; key layout and hit-testing in
`navigation::search_keyboard_key_at`, `navigation.rs:159`) — a new,
purpose-built compact keyboard, not the existing WiFi password entry's
full QWERTY-with-shift-and-symbols keyboard (`render.rs`'s `paint_wifi`),
which is hardcoded to that screen's own full-height layout and not
reusable without a separate refactor out of scope here. Lowercase-only is
deliberate, not a shortcut: matching is already case-insensitive
(`service_ui::filter_app_indices`, `service_ui.rs:142`, a plain
lowercased-substring scan — cheap enough, over this catalog's bounded
128-entry cap, that it needs no cache of its own, unlike the *painting* of
the results), so a shift/symbols row would only let someone type
characters that can never change which apps match. Filtering is live:
every keystroke re-filters and the grid relayouts immediately (still
backed by the same cached-bitmap architecture, §3 — a keystroke is exactly
one of the events that legitimately invalidates that cache). Filtered
results map back to real catalog entries via `ShellClient::
drawer_filtered_apps` (`main.rs:2349`), so `DrawerAction::Launch`/
`LongPress` (still a *display* index, matching `tile_at`'s own convention)
resolve to the right app regardless of what's currently filtered out.

An alphabetical fast-scroller remains **out of scope**, unchanged from the
earlier review's own reasoning: it would need its own hit-region carved
out of the grid's right edge, coupling grid-width layout math to whether
the rail is showing — real work, and this device's bounded, small app
catalog (128-entry cap, and the real installed set is far smaller) does
not have the "thousands of apps" problem a rail solves.

### 2.5 The sheet itself

`paint_drawer` fills from `navigation::panel_top` (a fixed 32px inset from
the very top of the screen, replacing the old `height * 0.19` ≈ 234px gap)
down to the screen's own bottom edge, with the top two corners rounded at
28px (`rounded_top`, `render.rs:1506` — a new helper; the old sheet had no
distinct corner rounding of its own at all, per `shell-polish-review-
2026-09.md`'s own finding) and a flat, opaque theme surface colour (not a
gradient brush — see that function's own comment on why: a gradient
brush's `fill_brush` issues its own plain-rectangle path, which would
overwrite the rounded-top path already set). `panel_travel_height`'s
Drawer case (`render.rs`) changes from a fixed `h * 0.81` to `h -
navigation::panel_top(height)`, keeping the compositor's own reveal
travel consistent with the new, taller sheet.

### 2.6 The grid: 4 columns, 64px icons, ~110px rows, even gutters, centered

`navigation.rs`: `COLUMNS = 4` (`navigation.rs:12`), `ROW_HEIGHT = 110.0`
(`navigation.rs:18`, replacing the old 160px pitch plus a separate 148px
tile height — one number now, since there is no plate height to
distinguish from row pitch), margin and inter-column gap both `24.0`px.
At this panel's 568px width that divides out exactly: `2×24 + 3×24 +
4×112 = 568` — the grid is centered with no remainder and no separate
centering offset to compute, and every gap (left margin, each inter-column
gap, right margin) reads as one even rhythm rather than a tighter gap
inside a wider border. Within each 112px cell, the 64px icon is centered
with 24px clearance on every side — matching the gutter exactly.
`GRID_BOTTOM_INSET` shrinks from 72px to a plain 24px safe-bottom margin
(`navigation.rs:26`) now that there is no footer caption reserving space.

### 2.7 Press feedback

A subtle, low-alpha (0.22) round highlight behind the icon (`paint_drawer`,
drawn as an overlay after the cached grid blit, radius 8px larger than the
icon), not the previous bordered-square outline — matches the redesign's
"just the icon" tile shape (a square border around a now-plateless tile
would look like a stray artifact, not feedback).

### 2.8 Already correct, unchanged

Long-press-to-pin (`DrawerAction::LongPress`, 500ms, `navigation.rs`) and
the fling deceleration curve (`DrawerNavigation::tick`'s exponential decay)
were already right (per the earlier review) and are untouched.

## 3. Performance: a cached grid bitmap, not a bigger label cache

### 3.1 Why the first attempt's fix wasn't enough

The rejected first attempt added a bounded label-raster cache
(`IconCache::paint_label`) and measured ~20% per-frame improvement,
scaled to an estimated 95-236ms/frame board cost — "isn't a fix," per the
coordinator, correctly: caching *labels* did nothing about the dominant
remaining cost, which was that **every visible tile still repainted its
full background card, icon-card backdrop and border every single frame**,
whether or not that tile's content had changed, plus a full-panel
background fill every frame regardless of scroll. `RendererCache::draw`'s
own rebuild trigger (any `scroll` delta ≥ 0.25px) forces a fresh `scene()`
call on every scroll tick; nothing about a label cache changes how much
work that call does.

### 3.2 The actual fix: `DrawerGridCache`

`DrawerGridCache` (`render.rs:1546`) pre-renders the **entire filtered
grid** — every row, not just the visible ones — into one off-screen
ARGB32 bitmap, in content-space coordinates (row 0 at bitmap `y = 0`,
independent of live scroll), keyed on `(filtered display list, theme
generation, panel width, search query)`. It is rebuilt only when that key
actually changes — a catalog rescan, a theme swap, a width change, or a
keystroke in search — never on a plain scroll or fling tick.

`paint_drawer` (`render.rs:1769`) then does, every frame: paint the fixed
chrome (handle, search field, sheet background — cheap, a handful of
small fixed shapes, unrelated to catalog size), clip to the grid's own
viewport rectangle, and blit one vertical slice of the cached bitmap at
`row_start - scroll` — a single `cairo_set_source_surface` +
`cairo_paint`, not a loop over every visible tile. The press highlight is
drawn as a small circular overlay on top afterward (cheap, and it changes
independently of the cached content, so baking it into the cache would
force a rebuild on every press/release instead of never).

`IconCache::paint_label` (`icon.rs:381`, `LABEL_CACHE_LIMIT = 48`,
`icon.rs:295`) is retained from the earlier attempt and still earns its
keep: it is what makes each (rare) cache **rebuild** cheap, since a
keystroke in search rebuilds a mostly-overlapping filtered set whose
labels mostly did not change text between one keystroke and the next.

### 3.3 Host measurement (host build, not board)

A committed, opt-in benchmark (`render::tests::
drawer_grid_cache_host_timing`, `#[ignore]`d so it never runs in an
ordinary `cargo test` and cannot make CI flaky on wall-clock noise; run
explicitly with `cargo test --lib --release drawer_grid_cache_host_timing
-- --ignored --nocapture`) drives the real `RendererCache::draw` path —
not a lower-level helper — over 200 simulated scroll/fling frames of a
64-app catalog (half with a real icon path, half without, so both
`IconCache::paint` and the round-circle fallback are exercised).

```
host: AMD Ryzen 9 5950X, single thread, cargo test --release
cold (fresh RendererCache every frame, forcing a full grid-bitmap
      rebuild each time -- this change's "before"):    33.60 ms/frame  mean over 200 frames
warm (persistent cache, scroll-only reuse -- this
      change's "after"):                                0.87 ms/frame  mean over 200 frames
```

**A 38.8× reduction** in this benchmark's own cold-vs-warm terms — well
past the "order of magnitude" bar, because the dominant cost this time
really was the per-tile repaint work the cache now skips entirely on an
ordinary scroll frame, not text shaping.

### 3.4 Honest board estimate — UNVERIFIED

Scaled by this repo's own established, explicitly-labeled convention for
converting a host measurement on this same 5950X into a board estimate
(`docs/evidence/card-shell/backdrop-blur-feasibility.md` §3: **20-40×**
slower for a single-issue, in-order 1.6GHz C908 core versus a ~4.5GHz
out-of-order desktop core on this kind of scalar, Pixman-backed paint
workload — "not derived from any board measurement of this workload […]
offered so the conclusion below is checkable, not so the number is
treated as calibrated"):

```
warm estimated board: 17.3 - 34.6 ms/frame
```

This straddles the ~20ms (50fps) target: at the low end of the
multiplier's own range it clears it (17.3ms), at the high end it does not
(34.6ms). **This is a real, order-of-magnitude improvement over both
prior estimates** (the original uncached tile-by-tile approach's
118-236ms, and the label-cache-only attempt's 95-236ms) and plausibly
close to or at the target — but it is still an estimate, not a
measurement, and is reported as such rather than claimed as a pass. §3.5
is the concrete gate that resolves it.

A themed board additionally likely pays less than this benchmark's own
`theme: None` case for the fixed chrome's background fill (a flat/brush
fill instead of a gradient fallback), so real numbers may run slightly
better than this estimate, not worse.

### 3.5 Board-readable timing log

`K230_DRAWER_FRAME` (`main.rs`'s `draw`, gated to `Route::Drawer`,
`DRAWER_FRAME_LOG_INTERVAL = 500ms`, `main.rs:117`, so a sustained
scroll/fling logs roughly 2 samples/second rather than one per frame)
logs `rust-shell {N}ms K230_DRAWER_FRAME ms={frame_render_ms:.2}
apps={app_count} scroll={scroll:.0}` to the journal via the shell's
existing `self.log(...)` — no `K230_TRACE_PATH` capture session required.
The coordinator can read this directly on the board with `journalctl
--user -u k230-shell-rust -f | grep K230_DRAWER_FRAME` (or the console
equivalent) while scrolling the drawer, and compare the real per-frame
`ms=` value against §3.4's estimate. **This is the concrete gate that
resolves §3.4's UNVERIFIED estimate into a real number** — this change
adds the instrumentation; it does not itself constitute the board
measurement.

## 4. Commits

Per the coordinator's explicit instruction, the drag-to-close bug fix
(§1) landed in its own commit, with its own tests, with no layout changes
— separately from this redesign-and-performance work, which follows in
a later commit on the same branch. The redesign and the performance work
land together in that later commit: they are not cleanly separable in
this implementation, since `DrawerGridCache`/`paint_drawer` is the single
piece of new code that both paints the redesigned tiles *and* is the
caching mechanism itself — there was no intermediate "redesigned but
uncached" version of this code to split a commit boundary through.

## 5. Evidence

Three screenshots, all real Cairo/Pixman renders of the production paint
code (`k230-shell-rust --render-fixture drawer OUTPUT.png`), at the real
panel geometry (568×1232). Exact commands, fixture construction and
stated limits: `docs/evidence/app-drawer/README.md`.

- `docs/evidence/app-drawer/original-before-redesign.png` — the true
  original design (temporarily restored from this branch's own merge-base,
  `d054d16b`, in this same worktree, then reverted back), for a real
  before/after rather than a description.
- `docs/evidence/app-drawer/redesign-fixture.png` — the redesign against
  a 24-app fixture catalog with no resolvable icons (every tile exercises
  the round fallback): 4 columns, circular icons, search field, no
  plates, no header/footer, rounded top sheet corners.
- `docs/evidence/app-drawer/redesign-real-icons.png` — the redesign
  against this repo's own real installed-app set and real icon packages
  (`viewnior`, `galculator`, `zathura`, `btop`, from the built system
  closure) — a real icon (`btop++`) resolves and paints correctly
  alongside the round fallback for the rest of that particular set. See
  that README's own stated limits on exactly which apps this ad-hoc
  environment did and did not surface.

## 6. What remains open

- **Board proof of §3.5's frame timing**: the actual `K230_DRAWER_FRAME
  ms=` values on hardware, to replace §3.4's estimate with a measurement,
  and confirm whether the ~20ms target is actually met.
- **Board proof of the bug fix** (§1, tracked against its own commit):
  a real-finger scroll-then-reverse gesture on glass.
- **Board proof of search**: real-finger taps on the search field and
  the compact keyboard, and real-finger scrolling of filtered results.
- **The alphabetical fast-scroller**, explicitly scoped out (§2.4).
- If §3.5's board measurement is still over budget despite the cache,
  the next lever is damage-limited *scroll-direction* blitting (shift the
  already-composited on-screen bitmap by the scroll delta and paint only
  the newly-exposed strip, rather than re-blitting the full viewport from
  the cached bitmap every frame) — not attempted here, since the
  cached-bitmap architecture already turns the per-frame cost into one
  blit of a bounded (viewport-sized) area, not one proportional to
  catalog size; a further win here is a smaller, marginal one relative to
  §3.2's own gain, not the same order of magnitude.
