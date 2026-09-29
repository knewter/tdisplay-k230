# Widget visual redesign: host render evidence

Host-rendered screenshots, not board or QEMU evidence. Produced by
`cargo run --example render_widget_evidence -- <out-dir> <dark-wallpaper>
<light-wallpaper>` (`nix/rust-shell-client/examples/
render_widget_evidence.rs`), which calls the real, unmodified
`render::paint_home` offscreen (a Cairo `ImageSurface`, no Wayland, no
compositor) against two synthetic `AppearanceSnapshot` themes built
directly from `appearance.rs`'s own public fields -- a Catppuccin
Mocha-derived dark palette and a Catppuccin Latte-derived light one --
rather than a live Omarchy IPC session, which this host has no compositor
to run.

I looked at every image myself before writing this and iterated until they
read as genuinely designed, not debug output.

## Revision history

**Round 3 (this one):** board review on the deployed build, verbatim: "the
widgets don't have to have a background like they do and the clock looks
like shit browse the web find dope clock widgets plz." Every widget's card
background is gone entirely -- no fill, no border, no corner radius; each
one now paints straight onto a real theme wallpaper image (see below),
with legibility coming from a halo/glow computed from the glyph's own
color (dark glyphs get a light halo, light glyphs get a dark one). The
Clock widget was rebuilt from scratch after `docs/design/
clock-widget-research.md`'s survey of Pixel/Nothing OS/iOS/Samsung/Material
You/Braun/desktop-rice clock designs: four styles now (Bubble, Thin, Dot
matrix, Analog), the first two set in a genuine Inter static face
(`nix/shell.nix`'s `clockDisplayFont`, Thin through Black) instead of
DejaVu Sans's Book/Bold pair, Dot matrix drawn procedurally with Cairo
circles (no font at all), and Analog stripped of its dial fill/ring
entirely per Braun/Dieter Rams's "no dial background, just markers and
hands." Battery and Weather kept their round-2 content/layout, just moved
onto the same no-card/halo treatment.

**Round 2:** dropped a card-border bug (corner-leaking tint, boxed-in
borders), rescaled the battery ring, adjusted clock breathing room and
forecast legibility. Superseded by round 3's "no card at all" -- see git
history for that intermediate state if needed.

**Round 1:** the original widget redesign (cards, three clock styles,
weather forecast strip).

## Real wallpapers, not flat color

Every screenshot composites over a genuine Omarchy theme background image,
decoded through the same `background_decode::BackgroundCache` (crop-to-
cover) the production wallpaper layer uses, not a flat swatch -- this
matters this round specifically because a flat background would never
exercise the halo/glow legibility mechanism the "no card" redesign depends
on. The two images are real files from this repo's own pinned theme data
(`nix build .#handheld-theme-default`'s output):

- Dark: `catppuccin`'s `2-waves.webp` (an abstract line-wave illustration,
  genuinely busy in places -- a real legibility stress test, not a gentle
  gradient).
- Light: `catppuccin-latte`'s `1-color-fade.webp` (a soft warm-to-cool
  gradient).

`render_frame` renders the wallpaper and the Home content onto two
*separate* Cairo surfaces before compositing them, mirroring the real
client's own Wayland layering exactly: `render::paint_home` always clears
its own surface to transparent first (so a real compositor can show the
wallpaper surface underneath it), so painting both onto one surface would
have that clear wipe the wallpaper out again.

## Font: what's actually on screen

The Bubble/Thin styles are set in "Inter" (the classic static collection,
`Inter.ttc`, not the variable font -- see `nix/shell.nix`'s
`clockDisplayFont` doc and `docs/design/clock-widget-research.md`'s own
"Font decision" section for why the variable weight axis isn't reachable
from this client). These screenshots were rendered with that exact font
file installed into this host's own fontconfig (`~/.fonts/`, `fc-cache
-f`), the same file the image ships, so what's on screen is the real face,
not a host substitute.

## What this captures

Ten distinct captures, each in both themes (`dark-*.png`/`light-*.png`,
20 files -- the two drag-mechanic captures are theme-independent mechanics
and are only captured once, in the dark theme):

- `clock-bubble.png` -- hour and minute each their own huge line, Inter at
  its heaviest weight, both lines the same color, centered.
- `clock-thin.png` -- one line, Inter at its thinnest weight, centered.
- `clock-analog.png` -- ticks and hands only, no dial fill or ring at all.
- `clock-dotmatrix.png` -- a procedural 5x7 dot-matrix `HH:MM` readout
  (Nothing OS-style), digits in the theme's foreground, the colon in its
  accent.
- `battery-present.png` / `battery-absent.png` -- the ring (with a soft
  ambient backdrop for contrast) and the muted outline glyph, both now
  straight on the wallpaper.
- `weather.png` -- current temperature, a Cairo-drawn condition glyph over
  its own soft backdrop, location, high/low, and a 3-entry forecast strip.
- `overview.png` -- Bubble clock, Battery, and Weather together on one
  Home page over the wallpaper, plus a populated dock.
- `widget-picker.png` -- the widget-picker sheet, all six entries (four
  clock styles plus Battery/Weather) each previewing their own live
  content.
- `drag-edge-indicator.png` / `drag-no-room.png` (dark only) -- the same
  live-drag mechanic evidence from round 1/2, driven through `HomeScreen`'s
  real public API; with no card behind the lifted widget any more, the red
  dashed "no room" highlight is now actually visible next to it (round 2's
  version was mostly hidden behind the lifted card).

## What this does not prove

This is host software rendering, not the board's panel, not real-finger
touch, and not a full Sway/compositor frame. It proves the widget-drawing
code paths run and look the way described, including against a genuinely
busy wallpaper image; it does not prove daylight readability, real
touch-latency feel, or on-device color/font reproduction. Physical-board
acceptance remains open (see the change's `tasks.md`).
