## Why

`the-home-screen-has-widgets-and-folders` (still unarchived) shipped
drag-to-place, folders, and three plain widgets. The user tried it on the
board and reported two concrete gaps, in their own words: "i can't drag
widgets/icons between screens easily and the widgets all are designed like
horseshit can they look way better we need a dope clock nice weather
widget."

Two concrete problems this closes:

1. **Cross-page dragging is not fluid.** The sibling change's own edge-hold
   turn existed, but at a single, slow 550ms dwell with a fixed instant page
   jump, no visible affordance that anything was about to happen, no way to
   page over quickly with a deliberate fling, and no way to actually reach a
   genuinely new page past the last one (a widget dragged to the edge of the
   last page just sat there). A person holding an icon at the edge had no
   feedback loop telling them it was even working.
2. **The widgets look plain, not designed.** Task text only, one weak/one
   regular weight, no icons, no visual hierarchy: "Battery" / "72%" and a
   condition word plus a temperature string. Nothing here reads as a
   deliberately designed hero clock, a battery gauge, or a weather card --
   it reads as debug output.

A first pass at both landed, and the coordinator deployed it to the board
for the user's judgment. Board review round 2 (from the deployed build's
own evidence screenshots, before the user looked) fixed a corner-leaking
tint, a boxed-in border, an oversized battery ring, a cramped clock, and a
tiny forecast strip. The user then tried *that* build on the board and
reported, verbatim: "the widgets don't have to have a background like they
do and the clock looks like shit browse the web find dope clock widgets
plz." Round 3 (this pass) responds to both halves of that: every widget's
card background is gone entirely, replaced by a theme-derived halo/glow
computed straight from each glyph's own color; and the Clock widget was
rebuilt from a survey of real clock-widget design across current mobile
platforms and community tools (`docs/design/clock-widget-research.md`),
not another guess.

## What Changes

- **Cross-page drag, tuned and made legible.** The edge zone narrows to
  ~40px; the first page-turn fires after ~350-400ms of dwell (not 550ms),
  and holding continues to page with a shorter ~260ms repeat delay. A
  themed edge glow plus a growing chevron arrow shows the dwell building
  before it fires. Every page-switch this drag triggers (edge-hold or
  fling) now slides smoothly via a dedicated eased transition
  (`home_screen::PageSwitchAnim` driving `home_pager::HomePager::
  set_position`), never an instant jump, and the lifted item keeps
  following the raw finger position throughout, unaffected by the page
  transform. A quick, deliberate horizontal fling mid-drag (`>=900px/s`,
  independent of edge proximity) pages over immediately, with a short
  lockout against re-triggering off one continuous swipe. Dragging a widget
  or icon to the true last page's right edge and continuing to hold now
  creates a brand-new empty page and slides onto it, rather than sitting
  inert at the clamp. Page dots enlarge while any drag is live. A
  multi-cell widget hovering somewhere its span cannot fit now shows a
  distinct dashed "no room here" highlight (the theme's error role)
  instead of the ordinary accepting one.
- **Research first.** `docs/design/clock-widget-research.md` surveys twelve
  standout clock-widget designs -- Pixel's lock-screen bubble/thin presets
  and At a Glance's own legibility fix, Nothing OS's Ndot dot-matrix,
  iOS StandBy, Samsung One UI's Adaptive Clock, Material You's system clock
  widget, KWGT/KLWP community packs, Braun/Dieter Rams's single-accent
  analog convention, and r/unixporn/Omarchy desktop-rice clocks -- and
  states, per design, what each borrows into this change.
- **Four selectable clock styles**, matching that research: `WidgetKind`
  gains `ClockMinimal`, `ClockAnalog`, and `ClockDotMatrix` alongside the
  existing `Clock`, all additive to the schema-2 tag (`clock`/
  `clock_minimal`/`clock_analog`/`clock_dot_matrix`), so an existing save
  file needs no migration and the enum's *internal* variant names stay
  unchanged even though every style's user-facing label changed. All four
  are selectable from the widget picker, which renders a live preview of
  each inline in its own row.
  - **"Bubble"** (`Clock`): hour and minute each their own huge line, Inter
    at its heaviest weight, the same color, centered -- Pixel's own
    two-line lock clock.
  - **"Thin"** (`ClockMinimal`): one line, Inter at its thinnest weight,
    centered.
  - **"Dot matrix"** (`ClockDotMatrix`, new): a procedural 5x7 dot-matrix
    `HH:MM` readout drawn with plain Cairo circles, no font file at all --
    digits in the theme's foreground, the colon in its accent.
  - **"Analog"** (`ClockAnalog`): ticks and hands only, the dial fill/ring
    from the first two passes removed entirely (Braun/Rams: "no dial
    background, just markers and hands"), an accent minute hand.
  - **Font:** `nix/shell.nix` gains `clockDisplayFont`, one file
    (`Inter.ttc`, 13,172,948 bytes) extracted from nixpkgs's `pkgs.inter`
    -- the classic *static* collection, not the variable font: `pango-sys`
    at this repo's pinned version has no binding at all for
    `pango_font_description_set_variations` (confirmed with a scratch
    `cargo check`), so the variable weight axis is unreachable from this
    client, but the static collection already carries Thin through Black
    as ordinary named faces `pango::Weight` addresses the same way this
    shell's existing DejaVu lookup already does. Used for the Bubble/Thin
    styles only; Dot matrix needs no font, and Analog's only text (its
    date caption) stays on the existing `FONT_FAMILY`.
- **No card behind any widget, of any kind.** Board review, round 2 (a
  first look at the *first* pass's own evidence): "the widgets don't have
  to have a background like they do." `render.rs::paint_widget_surface`
  (round 2's own card-without-a-border fix) is gone entirely -- no fill,
  no border, no corner radius, nothing painted behind a widget's content
  but the wallpaper itself. Legibility instead comes from a halo/glow
  computed from each glyph's own resolved color (`glow_for`): a dark glyph
  gets a light halo, a light glyph gets a dark one, via 8 offset copies of
  the same Pango layout at a small radius and low alpha behind the real
  glyph (`draw_layout_halo`) -- a cheap stand-in for a true blur, which
  Cairo's toy API has none of. Small graphic elements (the weather glyph,
  the battery ring/outline) get the equivalent non-text treatment, a soft
  ambient circular backdrop (`draw_soft_backdrop`) rather than a halo.
- **Weather widget kept its round-2 content, switched to wttr.in's `j1`
  format.** Current temperature (large), a Cairo-drawn condition glyph
  (sun/cloud/rain/snow/fog/storm), location name, today's high/low, and a
  3-entry forecast strip, all now painted straight on the wallpaper with
  the halo/backdrop treatment above instead of on a card. The 30-minute
  throttle, disk cache, and offline-keeps-last-reading behavior are
  unchanged.
- **Battery widget kept its round-2 layout** (a themed ring sized for a 2x2
  card, the live percentage centered inside it, a small accent
  charging-badge circle when charging, a muted outline glyph when absent),
  moved onto the same no-card/halo treatment.
- **Performance is unchanged in shape.** Widgets already only repaint when
  Home repaints and the underlying value (`home.battery`/`home.weather`)
  changed, or once a minute for the clock (`clock::ms_until_next_minute`);
  this pass adds more Cairo path drawing per widget paint but no new timers
  and no per-frame recomputation -- `paint_widget_card` still reads
  already-cached state and draws once per repaint, exactly as before.

**Non-goals for this pass:** widget resizing (still explicitly out of
scope, as in the sibling change); a fourth clock style beyond the three
named; changing the weather source away from wttr.in; touching any
`theme_ui.rs`/`theme_carousel.rs`/`theme_thumbnails.rs`/`theme_catalog.rs`/
`appearance.rs` file (per the coordinator's explicit instruction -- this
change reads theme colors through the existing `appearance`/`render.rs`
brush/palette lookups only); `nix/card-shell/` (the C card renderer, owned
by other concurrent work).

**Board dependency:** every behavior above is host-testable. The drag
timing/page-creation/fling state machine is exercised by `cargo test`
(`home_screen`/`home_pager` unit tests, including new ones for the ~380ms/
~260ms dwell thresholds, the last-page new-page creation, and the "no room"
drop-target check). The widget content/parsing logic (the three clock
styles' formatting, the `j1` forecast selection, the battery ring's percent/
charging state) is unit-tested with no hardware. The *visual* result is
evidenced by a host Cairo render harness
(`nix/rust-shell-client/examples/render_widget_evidence.rs`,
`docs/evidence/home-widget-design/`), not a board or QEMU capture -- this
proposal does not touch the board, and physical-board real-finger
acceptance (daylight readability, real touch feel, real forecast data over
the board's own network) remains an explicitly open evidence gate for the
coordinator.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None archived to modify -- `openspec/specs/runtime/home-screen/` does not
exist yet (`the-home-screen-has-widgets-and-folders`, the change that would
create it, is itself still unarchived). This change's own spec delta below
therefore also adds its requirements as `ADDED`, exactly as that sibling
change's own proposal explains doing for the same reason. Two of this
change's requirements *revise in place*, once both land, requirements the
sibling change already added:

- The sibling's "Home items can be dragged to a specific place instead of
  instant-pinned" requirement already names "about 500ms" holding at the
  edge and "add a new page when held past the last one" (not actually
  implemented in that pass). This change's own "Cross-page dragging pages
  fluidly with a visible edge affordance" requirement below supersedes
  those specific numbers (~350-400ms first dwell, ~260ms repeat, an
  explicit visible affordance, a fling) and completes the new-page
  behavior. Whichever change archives first should fold the edge-hold
  timing language from the other into one coherent requirement rather than
  leaving both as separately-numbered claims.
- The sibling's "Home offers Clock, Battery, and Weather widgets drawn by
  the shell" requirement covers *that widgets exist and show correct
  content*; this change's own "Home's widgets are visually redesigned with
  distinct styles and richer content" requirement is additive to it (three
  clock styles, ring/glyph visuals, a forecast strip), not a replacement --
  the sibling's content-correctness scenarios (fresh-install seeding,
  minute-boundary redraw, absent/present battery, offline weather) all
  still hold unchanged.

## Impact

Mostly userspace, `nix/rust-shell-client/`: `home_state.rs` (`WidgetKind`
gains three variants plus `add_blank_page`/`would_fit`), `home_pager.rs`
(`set_position`), `home_screen.rs` (edge-hold/fling/page-switch-animation
state machine, `drag_edge_indicator`/`drop_target_fits` accessors),
`home_widgets.rs` (the weather module's `j1` rewrite), `render.rs` (the
no-card/halo widget redesign, the four clock styles, the edge indicator,
the "no room" drop-target style, enlarged page dots), `main.rs` (two
call-site signature updates for the drawer-drag hand-off's now
time/height-aware `external_drag_motion`), and a rewritten
`examples/render_widget_evidence.rs` host harness (now composites over a
real wallpaper image via `background_decode::BackgroundCache`). Plus one
Nix-level change: `nix/shell.nix` gains `clockDisplayFont` (one font file,
13,172,948 bytes, extracted from nixpkgs's `pkgs.inter`) in
`fonts.packages`, alongside the existing `pkgs.dejavu_fonts` -- the one
font addition this whole `home-widget-design` change makes, used only by
the Clock widget's Bubble/Thin styles. No kernel, device tree, boot, radio,
or second-core change. The existing `.#handheld-shell-rust`/`.#card-shell`
outputs and the `k230-coherent-shell` NixOS configuration absorb it.
