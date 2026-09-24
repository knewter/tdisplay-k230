# Theme/background carousel: Cover Flow parity with Omarchy Quattro

Captured 2026-09-24 against branch `feat/quattro-carousel`, base `master`
`8b538c66` (pushed). **Host and headless-QEMU only -- no board, no real
finger, no physical panel.** This supersedes the vertical-list approach
recorded in `docs/evidence/omarchy-themes/quattro-picker-parity/`: that
document explicitly scoped a scrolling list as "what we adopted... is its
information design, not its skeuomorphic geometry"; this change adopts the
geometry too, at the user's explicit request that the picker "work/look the
same" as Quattro's.

## 2026-09-24 update: the carousel becomes the page's hero (`fix/carousel-portrait-size`)

Re-captured the same day against branch `fix/carousel-portrait-size`, base
`master` `1f107beb` (this repo's `origin/master` moved further since, on
unrelated work; `1f107beb` is this branch's own merge-base). **Still host
and headless-QEMU only.** The pass above scaled Quattro's own
*landscape-monitor* geometry down by one flat factor and got the shape
right but the emphasis wrong: on this 568x1232 portrait panel the result
was only ~186px tall at the very top of the Themes page, correct geometry
read as a small ornament above an otherwise empty card. All five PNGs
below are replaced with this larger geometry; every earlier section of
this document (interaction contract, mid-drag interpolation, the general
shape of the imagery approximation) is unchanged and still accurate --
only the numbers this section corrects are stale.

**What changed, and why it's two geometries now.** The Themes page's
carousel and the Preview page's background carousel are no longer the
same fixed size. `nix/rust-shell-client/src/theme_carousel.rs` now has a
`CarouselGeometry` struct with two named instances -- `THEME_GEOMETRY`
(the Themes page hero: `480x640`, most of the panel's width, a *portrait*
3:4 crop of each theme's landscape `preview.png` rather than Quattro's own
`768:475` landscape aspect -- picked over letterboxing because a portrait
crop fills the whole enlarged slot with real pixels instead of a smaller
photo floating in extra bars, and a desktop screenshot's distinctive
content is usually centered anyway) and `BACKGROUND_GEOMETRY` (the Preview
page's background carousel: `420x260`, smaller because that page already
carries a palette row and a screen-crop preview above it and has far less
spare vertical budget). Every *width*-derived measure (a side slice's own
width, the skew shear, the pitch between slices) still keeps upstream's
exact ratio to its geometry's own `expanded_w`; a side slice's height
still keeps upstream's own ratio to `expanded_h`. Full derivation and
exact numbers are in `theme_carousel.rs`'s own module doc, not repeated
here.

**A real bug this surfaced: decode order, not decode failure.** The first
attempt at these captures showed *no* preview art at all on the Themes
page, even after minutes of waiting -- looking like a decode failure.
Instrumenting the worker thread (a throwaway, uncommitted probe) showed
every decode actually succeeding; the real cause was `RendererCache::
poll_theme_thumbnails` requesting nearby thumbnails in *paint* z-order
(farthest neighbor first, the centered slice last, correct for painting
so the centered slice ends up on top) but that is also *request* order
into the bounded worker queue (`theme_thumbnails::QUEUE`, capacity 4) --
so the one slice a user actually sees at rest, the centered one, claimed
a decode slot *last* of every nearby id. At the old, smaller `300x186`
target this never mattered (every decode was fast enough to clear the
queue before anyone noticed); the hero's much larger `480x640` target,
decoding a real ~1800x1012 desktop screenshot under `qemu-riscv64-static`
software emulation, made a single decode slow enough that request order
became visible as an apparent hang. Fixed by requesting centered-outward
(`.rev()` on the already z-sorted list) in `poll_theme_thumbnails` only;
`paint_carousel`'s own separate call to the same `visible_slices` keeps
its original (unreversed) paint order. Covered structurally by the
existing thumbnail cache tests; not itself given a new dedicated unit test
because reproducing it needs a slow real decode, not the tiny synthetic
fixtures those tests use -- this document is that finding's record.

**Thumbnail cache, resized.** `theme_thumbnails::CACHE_CAP` shrank from 48
to 36 -- just above one carousel's own steady-state need (`NEARBY_LIMIT`
8 either side, unchanged: 17 nearby ids x 2 variants = 34) -- because each
`Expanded` entry is now up to 1,228,800 bytes (`480*640*4`, the hero) where
before it was a uniform 223,200 (`300*186*4`) for both carousels. Worst
realistic case (the hero carousel fully populated: 17 `Expanded` + 17
`Slice`, `68*582*4` each) is `17*1,228,800 + 17*158,304` = 23,580,768
bytes, ~22.5 MiB -- up from the previous ~10 MiB, still a small, fixed,
explicitly bounded number (`theme_thumbnails.rs`'s own doc states it in
full). The Preview page's background carousel's own `Expanded` entries
(`420*260*4` = 436,800 bytes) are smaller, so browsing only ever there
stays well under half that figure.

## What was read

[`shell/plugins/image-picker/ImagePicker.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/plugins/image-picker/ImagePicker.qml)
at our pinned revision `28ceaae7` (`nix/handheld-theme-default/default.nix`;
confirmed still the tip of `origin/quattro` in the prior evidence pass), read
in full, not skimmed. The whole component -- geometry, mask/skew shape,
z-order, click handling, keyboard handling -- is 582 lines; every constant
and formula cited below is transcribed from it, not guessed from
screenshots. No `Behavior`/`Animation`/`NumberAnimation` exists anywhere in
the file: upstream's own selection is an instant snap driven by arrow
keys/Tab/a slice click, never a drag. Upstream reference imagery:
`omarchy.org/manual/themes`,
[`manual/06-themes.md`](https://github.com/omacom/omarchy/blob/quattro/manual/06-themes.md)
-- not committed here; follow the links rather than a copy of upstream art.

## Geometry: scaled, not reinvented

**The exact numbers in this section are the first pass's, since superseded
by the "2026-09-24 update" section above -- the scaling *method* and the
transcribed layout formula below are unchanged, only the absolute pixel
values and the single-shared-geometry assumption are stale.**

Upstream's constants (`expandedWidth: 768`, `expandedHeight: 475`,
`sliceWidth: 108`, `sliceHeight: 432`, `sliceSpacing: -30`, `skewOffset: 28`)
are sized for a desktop monitor. `nix/rust-shell-client/src/theme_carousel.rs`
scales every one of them by the same factor for this 568-wide portrait panel:
`EXPANDED_W: 300`, `EXPANDED_H: 186`, `SLICE_W: 42`, `SLICE_H: 169`,
`SKEW: 11`, `SPACING: -12` (rounded to whole pixels for crisp software
rasterization; each is within half a pixel of the exact 300/768 ratio).
`NEARBY_LIMIT` (how many slices either side get laid out/hit-tested at all)
is 8, not upstream's 16, because this screen is far narrower -- fewer
slices are ever visible, and every visible id must fit the bounded
thumbnail cache.

The layout formula itself -- which branch positions a slice, how z-order
resolves the shingled overlap from negative `sliceSpacing`, how the skew
mask cuts each slice's corners -- is transcribed line-for-line
(`exact_layout`/`in_slice` in `theme_carousel.rs`, citing the exact
`ImagePicker.qml` line numbers in comments).

## What's new: touch, not upstream's

Upstream has no drag physics at all -- it is keyboard/mouse/tap-only. This
panel is touch-first, so `theme_carousel.rs` adds real drag-with-momentum on
top of upstream's own interaction *contract*, which is kept exactly:

- horizontal drag moves the carousel 1:1 with the finger (a drag of one
  `CarouselGeometry::item_step()` in pixels moves the position by exactly
  one slice);
- release either coasts (a fast flick) or settles immediately (a slow
  release), using this shell's existing decay/ease conventions
  (`navigation.rs`'s `DrawerNavigation`, `service_ui.rs`'s
  `NotificationSwipeSettle` -- same `0.88`-per-16ms decay, same
  elapsed-accumulator `tick` instead of an absolute clock, same ease-out
  cubic settle);
- tapping a side slice recenters it (upstream's `root.select(index)`, no
  side effect);
- tapping the already-centered slice, or an explicit Apply, confirms
  (upstream's `root.applySelected()`); a drag release never itself
  confirms.

## Two deliberate approximations, and why

**Continuous mid-drag layout.** Upstream's layout function is only ever
evaluated at an integer `selectedIndex`; its own two position branches
(`relativeIndex < 0` vs `>= 1`) never have to agree at a shared boundary,
because that boundary case never occurs in a discrete, non-draggable
picker. Making the same layout draggable needs a continuous position. Deriving
a new continuous closed form (and asymmetrically pushing only the right
neighbor outward the way upstream's own discrete formula does) would not be
validated by any Quattro screenshot. Instead, `theme_carousel::Carousel`
computes upstream's own exact discrete layout at the two integers
bracketing the current (possibly fractional) position and linearly
interpolates every slice's `(x, y, width, height)` between them. At rest
(integer position) this reproduces upstream's layout exactly -- which is
what `theme-carousel-rest-dark.png` below checks by eye. Mid-drag it is a
cheap, plausible approximation (two closed-form evaluations plus a `lerp`,
no iteration, no trigonometry), not a physically exact continuous coverflow.
`theme-carousel-mid-drag.png` shows the visible result: the departing slice
shrinks and the arriving one grows continuously, exactly this blend.

**Imagery.** Quattro's own slices are two different aspect ratios -- an
expanded slice is a wide landscape crop, a side slice a narrow tall strip --
and a slice's blended size changes every frame while dragging.
Re-cropping the source image at the exact blended aspect every frame is the
"needlessly expensive per-frame transform" this change is told to avoid on
the K230's software (Pixman/Cairo) renderer, on a slow in-order RISC-V core.
`theme_thumbnails.rs` instead decodes and caches exactly two bitmaps per
catalog id -- one already cropped to the expanded aspect
(`Variant::Expanded`), one to the slice aspect (`Variant::Slice`) -- and the
renderer picks whichever is closer to a slice's current blend and scales it
onto the slice with a Cairo matrix (`cr.scale`), never a fresh decode. Both
endpoints of a drag are pixel-exact; a few frames near the halfway point of
a transition use the "wrong" aspect's crop, scaled -- a deliberate, cheap
tradeoff. (Sizes and cache capacity as of the original, single-geometry
pass were `300x186`/`42x169` and `CACHE_CAP` 48; the "2026-09-24 update"
section above has the current two-geometry sizes and cache numbers.)
Requests are scoped to `theme_carousel::NEARBY_LIMIT`, not the whole
catalog, mirroring upstream's own "only nearby images load, and stay
loaded once activated" comment (`ImagePicker.qml`'s `sourceActivated`).

A real bug this surfaced and fixed: the first version of this change
requested nearby thumbnails only from inside `RendererCache::draw`, so a
request dropped by the worker's bounded queue (or simply not yet decoded)
would never retry once the touch gesture that first opened the carousel
ended and nothing else was marking the scene dirty. Fixed by
`RendererCache::theme_thumbnails_pending()`, which the main loop
(`main.rs`) now polls independently of carousel animation, keeping the
redraw loop alive until every nearby slice's bitmap is actually resolved
(decoded, or permanently cached-absent), not only while the carousel
itself is still moving.

## Side-by-side vs. the prior (list) evidence

| | Omarchy Quattro | Prior pass (vertical list) | This change (carousel) |
| --- | --- | --- | --- |
| Layout | horizontal skewed Cover Flow, ~1 expanded + up to 16 slices/side | vertical scrolling list | horizontal skewed Cover Flow, ~1 expanded + up to 8 slices/side |
| Per-item imagery | full-bleed photo per slice | 64px rounded corner thumbnail beside text | full-bleed photo per slice (two cached aspect variants) |
| Browse | arrow keys/Tab/tap a slice (instant snap) | swipe/scroll | drag (1:1, momentum) or tap a side slice (settle animation) |
| Confirm | Enter, or tap the centered slice | tap any row | tap the centered slice, or explicit Apply |
| Background picker | same component, fed `backgrounds/` | second scrollable list | second carousel, same component |
| Current-theme mark | thicker accent border while browsing (not persistent) | highlighted card + label + checkmark badge | accent border on the centered slice (matches upstream; no separate persistent badge -- Quattro's own picker has none either) |

## Commands and store paths

Cross-built (`--max-jobs 1 --cores 6`). Paths from the original
`feat/quattro-carousel` pass:

```sh
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#handheld-shell-rust
# /nix/store/w228v2vngb47i5abpp6k0gdxfrn72hd3-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#card-shell .#handheld-theme-default
# /nix/store/lkdaakm71ydjf32sgig9zpak8jyygxgl-k230-card-shell
# /nix/store/rya33fd7vgcgp0vnydzgsrvznzx5pj15-handheld-theme-default-28ceaae7
```

`sway-unwrapped` (not the wrapper) via `nix-store -qR` on the `card-shell`
output: `/nix/store/mh4pqnim7v8zc8sgk7ma3pjqgxm707v4-sway-unwrapped-riscv64-unknown-linux-gnu-1.12`.

Paths from the `fix/carousel-portrait-size` re-capture (2026-09-24, same
`handheld-theme-default`/`sway-unwrapped` -- only the Rust shell's source
changed):

```sh
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#handheld-shell-rust
# /nix/store/pfa50hbxq4p9h3gb5px83690h4w7b8w4-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#card-shell .#handheld-theme-default
# /nix/store/yff5vvpqgmcsz7n23rcw7r2080kalq1g-k230-card-shell
# /nix/store/rya33fd7vgcgp0vnydzgsrvznzx5pj15-handheld-theme-default-28ceaae7 (unchanged)
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#handheld-theme-command
# /nix/store/sd5slw0m9qxhvcq7qc0kx5y06s5xbzzq-handheld-theme-command-0.1
#   (the real k230-theme wrapper; used for these screenshots instead of the
#   synthetic fixture the committed test uses, so preview.png/backgrounds
#   are the real 22-theme catalog's own art, not a solid-color placeholder)
```

```sh
cd nix/rust-shell-client && cargo test --offline
# 85 + 7 + 14 + 5 + 8 passed, 0 failed (includes theme_carousel::tests:: --
# index-from-offset, settle-target, momentum-decay, skewed-slice hit-testing,
# and background_geometry_is_smaller_but_keeps_upstreams_ratios)

python3 tests/rust_theme_chooser_qemu.py --sway <sway-unwrapped> --rust <k230-shell-rust>
# PASS paired Sway/Rust theme carousel QEMU touch, synthetic backend; no physical touch
```

The five PNGs below (not `swipe.mp4`/`swipe.json`, see their own entry)
were captured with a throwaway, uncommitted harness
(`capture_carousel_evidence.py`, same paired headless-Sway/Rust-under-
`qemu-riscv64-static` technique as the committed test, `K230_THEME_COMMAND`
pointed at the real `handheld-theme-command` wrapper above instead of a
synthetic fixture) rather than the committed test, so the real catalog's
own imagery shows rather than a solid test color.

The regression test (`tests/rust_theme_chooser_qemu.py`, committed) exercises
the full touch contract against a synthetic theme command: open, drag-browse
(no request fired), tap-a-side-slice-to-recenter (no request fired),
tap-center-to-confirm (exactly one `preview` request), drag+confirm on the
background carousel, Cancel (no `activate`), then an explicit Apply
(exactly one `activate`, with the correct `--expected-generation`). Its own
capture helper retries until several consecutive frames are pixel-identical
rather than trusting a fixed commit count or a fixed delay, after an earlier
version of this same test intermittently captured a mid-transition frame (a
"Loading themes" placeholder, or a still-blending slice) as if it were
settled.

## What the screenshots and video below show

All five PNGs (re-captured 2026-09-24 at the new, larger geometry): real,
installed `tools/theme_catalog.py` via the real `handheld-theme-command`
wrapper (see above), the real 22-theme `handheld-theme-default-28ceaae7`
package (`preview.png` per theme, real `.webp` backgrounds up to
3840x2160), run inside the same paired headless-Sway/Rust-under-
`qemu-riscv64-static` harness as the committed test, driven by synthetic
`card_shell test-touch` IPC (not a real finger). **Preview only -- no
Apply, no state mutation**, same scope as the prior evidence pass.

- [`theme-carousel-rest-dark.png`](theme-carousel-rest-dark.png) -- the
  Themes page now reads as a hero card: a large `480x640` portrait-cropped
  centre slice showing a real, legible crop of `catppuccin`'s own
  `preview.png` (a terminal, a system-monitor widget row, and a file
  manager window are all individually readable at this size, not just
  colour blocks), skewed shingled side slices peeking in from both edges
  with other themes' real preview art, accent border on the centre slice,
  name label and "Built in" caption below -- and nothing else: this is
  deliberately uncluttered, matching Quattro's own picker (name + a status
  caption, no additional chrome). `ThemeEntry` (the catalog listing) has no
  palette field, so palette swatches are not shown here (they are on the
  Preview page below, where a specific theme's own `ThemePreview` -- which
  does carry `palette` -- is already loaded); adding a palette fetch per
  browsed-past listing entry just to swatch an unselected carousel slice
  would mean a process spawn per drag frame, exactly the per-frame cost
  this change is told to avoid.
- [`theme-carousel-mid-drag.png`](theme-carousel-mid-drag.png) -- the same
  carousel held mid-drag (~0.4 slice), showing the continuous shrink/grow
  blend between `catppuccin` and its right-hand neighbor described above,
  not a discrete jump.
- [`preview-light.png`](preview-light.png) -- Preview page after confirming
  `catppuccin-latte` (light): real light palette swatches, a real
  screen-crop of its first background, "2 supported · 0 unavailable", and
  that theme's `420x260` background carousel at rest below -- one
  background ("Color fade", a real gradient `.webp`) expanded and centred,
  its "Omarchy" wordmark background peeking in as a dimmed grey side
  slice. The footer (Cancel/Apply) still sits with clear headroom below
  the carousel; this page's carousel grew less than the Themes page's
  because the palette row and screen-crop preview above it already use a
  meaningful share of the page (see the "2026-09-24 update" section).
- [`background-carousel-mid-drag.png`](background-carousel-mid-drag.png) --
  the same background carousel held mid-drag (~0.4 slice) toward that side
  slice.
- [`preview-dark.png`](preview-dark.png) -- the same page after cancelling
  back to the theme carousel (which recentres on `catppuccin`, since
  nothing was ever activated) and confirming it again: dark palette, its
  real "Totoro" background (a 3840x2160 source `.webp`) fully decoded and
  centred in the background carousel, clearly legible at this larger size.
  Getting a stable capture of this (and of `theme-carousel-rest-dark.png`
  and `preview-light.png`) needed a real fix, not just a longer wait --
  see the decode-order bug described in the "2026-09-24 update" section
  above; this capture is the corrected result, not the one that first
  surfaced the bug.
- [`swipe.mp4`](swipe.mp4) / [`swipe.json`](swipe.json) -- **not
  re-captured this pass; predates the resize.** A ~1.7s, 14-frame sampled
  swipe across several themes at the *original* `300x186` geometry,
  encoded with the repo's own `tools/encode-grim-samples.py` from real
  host `time.monotonic()` timestamps per sampled Grim frame (`swipe.json`
  records `interaction_provenance: "injected"` -- synthetic touch, not a
  real finger, and these are host/QEMU monotonic seconds, not the board's
  `/proc/uptime` the tool's docstring otherwise assumes). It still
  correctly demonstrates drag/momentum mechanics (unchanged by this
  resize), but its carousel proportions are stale; the five PNGs above are
  the current-geometry evidence.

## What still needs the real board

Swipe feel (does 1:1 drag actually feel like the finger is moving the
carousel, or does emulated/QEMU-only touch latency hide a real lag), actual
frame rate during a drag and during momentum coasting, whether the
skew/mask compositing (`MultiEffect`-equivalent Cairo clip per slice, 8
slices either side at once) is cheap enough on the K230's single applicable
C908 core, and real decode latency for large background assets (the
limitation noted above) are all `<!-- UNVERIFIED -->` and reserved for
`openspec/changes/the-shell-loads-omarchy-themes/tasks.md` task group 5's
board trial. This document proves the mechanism and the visual/geometric
parity with Quattro's picker under QEMU and on the host; it does not claim
either performance property.

**2026-09-24 update.** The larger hero geometry's `Expanded` decode target
(`480x640`, up from `300x186`) is real additional per-image decode/resize
work, on top of whatever the K230's software renderer already costs per
frame; this pass fixed a *request-order* bug (centered slice decoded last)
that made that added cost visible as an apparent hang under QEMU emulation,
but did not, and could not from a host/QEMU capture, measure whether the
larger per-image cost itself is acceptable on real hardware within a
single frame budget or a drag gesture's own decode-on-demand window. That
remains `<!-- UNVERIFIED -->` and belongs with the rest of this section's
board trial, not inferred from the fix above landing cleanly under QEMU.
