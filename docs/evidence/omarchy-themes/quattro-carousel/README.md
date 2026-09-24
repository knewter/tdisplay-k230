# Theme/background carousel: Cover Flow parity with Omarchy Quattro

Captured 2026-09-24 against branch `feat/quattro-carousel`, base `master`
`8b538c66` (pushed). **Host and headless-QEMU only -- no board, no real
finger, no physical panel.** This supersedes the vertical-list approach
recorded in `docs/evidence/omarchy-themes/quattro-picker-parity/`: that
document explicitly scoped a scrolling list as "what we adopted... is its
information design, not its skeuomorphic geometry"; this change adopts the
geometry too, at the user's explicit request that the picker "work/look the
same" as Quattro's.

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
  `ITEM_STEP` in pixels moves the position by exactly one slice);
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
(`Variant::Expanded`, 300x186), one to the slice aspect (`Variant::Slice`,
42x169) -- and the renderer picks whichever is closer to a slice's current
blend and scales it onto the slice with a Cairo matrix (`cr.scale`), never a
fresh decode. Both endpoints of a drag are pixel-exact; a few frames near
the halfway point of a transition use the "wrong" aspect's crop, scaled --
a deliberate, cheap tradeoff. Cache capacity was raised accordingly
(`CACHE_CAP` 128 small 64x64 squares before, to 48 larger dual-variant
entries now -- still bounded, ~10 MiB at the generous end) and requests are
scoped to `theme_carousel::NEARBY_LIMIT`, not the whole catalog, mirroring
upstream's own "only nearby images load, and stay loaded once
activated" comment (`ImagePicker.qml`'s `sourceActivated`).

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

Cross-built (`--max-jobs 1 --cores 6`):

```sh
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#handheld-shell-rust
# /nix/store/w228v2vngb47i5abpp6k0gdxfrn72hd3-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#card-shell .#handheld-theme-default
# /nix/store/lkdaakm71ydjf32sgig9zpak8jyygxgl-k230-card-shell
# /nix/store/rya33fd7vgcgp0vnydzgsrvznzx5pj15-handheld-theme-default-28ceaae7
```

`sway-unwrapped` (not the wrapper) via `nix-store -qR` on the `card-shell`
output: `/nix/store/mh4pqnim7v8zc8sgk7ma3pjqgxm707v4-sway-unwrapped-riscv64-unknown-linux-gnu-1.12`.

```sh
cd nix/rust-shell-client && cargo test --offline
# 78 + 6 + 13 + 5 + 8 passed, 0 failed (includes theme_carousel::tests:: --
# index-from-offset, settle-target, momentum-decay, skewed-slice hit-testing)

python3 tests/rust_theme_chooser_qemu.py --sway <sway-unwrapped> --rust <k230-shell-rust>
# PASS paired Sway/Rust theme carousel QEMU touch, synthetic backend; no physical touch
```

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

All captures: real, installed `tools/theme_catalog.py`, the real 22-theme
`handheld-theme-default-28ceaae7` package (`preview.png` per theme, real
`.webp` backgrounds up to 3840x2160), run inside the same paired
headless-Sway/Rust-under-`qemu-riscv64-static` harness as the committed
test, driven by synthetic `card_shell test-touch` IPC (not a real finger).
**Preview only -- no Apply, no state mutation**, same scope as the prior
evidence pass.

- [`theme-carousel-rest-dark.png`](theme-carousel-rest-dark.png) -- the
  theme carousel at rest, centered on `catppuccin` (dark): expanded centre
  slice showing its real `preview.png`, skewed shingled side slices with
  other themes' real preview art visible either side, accent border on the
  centre slice, name label and "Built in" caption below.
- [`theme-carousel-mid-drag.png`](theme-carousel-mid-drag.png) -- the same
  carousel held mid-drag (~0.4 slice), showing the continuous
  shrink/grow blend between `catppuccin` and `catppuccin-latte` described
  above, not a discrete jump.
- [`preview-light.png`](preview-light.png) -- Preview page after confirming
  `catppuccin-latte` (light): real light palette swatches, a real
  screen-crop of its first background, "2 supported · 0 unavailable",
  and that theme's background carousel at rest below -- one background
  ("Color fade") expanded and centered, its "Omarchy" wordmark background
  peeking in as a dimmed side slice.
- [`background-carousel-mid-drag.png`](background-carousel-mid-drag.png) --
  the same background carousel held mid-drag (~0.5 slice) toward that side
  slice.
- [`preview-dark.png`](preview-dark.png) -- the same page after cancelling
  back to the theme carousel (which recentres on `catppuccin`, since
  nothing was ever activated) and confirming it again: dark palette, its
  real "Totoro" background (a 3840x2160 source `.webp`) fully decoded and
  centered in the background carousel. An earlier capture in this same run,
  taken immediately after confirming, still showed that large asset's
  carousel slice as a plain placeholder while the *smaller* `Screen crop`
  thumbnail on the same page (a different, already-bounded decode path) had
  already painted -- real single-worker decode-queue timing under
  `qemu-riscv64-static`'s CPU emulation, not a logic bug (confirmed by
  waiting slightly longer, as this capture did); not evidence of real-
  hardware decode speed either way.
- [`swipe.mp4`](swipe.mp4) / [`swipe.json`](swipe.json) -- a ~1.7s, 14-frame
  sampled swipe across several themes, encoded with the repo's own
  `tools/encode-grim-samples.py` from real host `time.monotonic()`
  timestamps per sampled Grim frame (`swipe.json` records
  `interaction_provenance: "injected"` -- synthetic touch, not a real
  finger, and these are host/QEMU monotonic seconds, not the board's
  `/proc/uptime` the tool's docstring otherwise assumes).

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
