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
- **Three selectable clock styles.** `WidgetKind` gains `ClockMinimal` and
  `ClockAnalog` alongside the existing `Clock` ("Big stacked"): a full-width
  hero pair of hour/minute lines, a single thinner `HH:MM` line, and a
  Cairo-drawn analog face (ticks, a neutral hour hand, an accent minute
  hand) -- all three additive to the schema-2 `WidgetKind` tag
  (`clock`/`clock_minimal`/`clock_analog`), so an existing save file needs
  no migration. All three are selectable from the widget picker, which now
  also renders a live preview of each widget kind inline in its own row.
  "Big stacked" is left-aligned with deliberate breathing room from the
  card's own edges, the hour in accent Bold and the minute beneath it in a
  lighter Normal weight (a board look at the first pass found it cramped
  against the left edge with both lines reading at the same visual weight).
  Every clock style shows a tracked-caps date caption, sized up a touch
  from the first pass for legibility.
  - **Font choice:** kept `DejaVu Sans` (the image's one shipped family,
    `render.rs`'s own `FONT_FAMILY` doc already turned down adding a second
    face for a prior rendering-only fix). No variable/light-weight family
    was added this pass either: DejaVu Sans ships only Book/Bold, so the
    "thinner" minimal-line style leans on Normal weight plus reduced
    opacity and size rather than a genuine font-weight axis. Adding a small
    variable sans remains an option for a future pass; it was not worth the
    blob-inventory/image-size risk here, and this host environment cannot
    prove a new nixpkgs fetch actually succeeds under the coordinator's
    cross-build.
- **Weather widget redesigned, switched to wttr.in's `j1` format.** Current
  temperature (large), a Cairo-drawn condition glyph (sun/cloud/rain/snow/
  fog/storm, replacing the old plain condition word), location name,
  today's high/low, and a 3-entry forecast strip (this card's own 2x2 width
  fits three columns legibly; wttr.in's `j1` response has enough hourly data
  for up to 5, but three is what actually reads at this size). Each
  forecast column's own glyph and temperature are sized for legibility at
  arm's length (a board look at the first pass found them too small to
  read). The 30-minute throttle, disk cache, and offline-keeps-last-reading
  behavior are unchanged, now carrying the richer snapshot shape.
- **Battery widget redesigned.** A themed ring, sized to actually suit a 2x2
  card (about 30% smaller than the first pass, which read as oversized on
  the board), with the live percentage large and centered *inside* the ring
  rather than as a caption beneath it, plus a small accent charging-badge
  circle (with the bolt glyph inside it) when charging, replacing the old
  plain percentage text. The absent state keeps its "No battery info"
  wording paired with a muted outline battery glyph.
- **Consistent, borderless card chrome.** Every widget shares one dedicated
  surface treatment (`render.rs::paint_widget_surface`): the same 16px
  radius `docs/design/shell-polish-review-2026-09.md` already names as the
  Rust-side "sheet" radius, a subtly filled surface derived from the theme
  at ~80% alpha, and a cheap layered soft shadow -- deliberately no border
  stroke, unlike `service_card` (which every *other* floating panel here
  still uses). A first pass reused `service_card` outright; a board look at
  the rendered result found its 1px border made every widget "look
  boxed-in" over the wallpaper, where nothing else frames it the way a
  bordered panel's own surroundings do. The Weather widget's condition tint
  is now clipped to this same rounded shape (it previously leaked past the
  corners as a plain unclipped rectangle).
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

Userspace only, `nix/rust-shell-client/`: `home_state.rs` (`WidgetKind`
gains two variants plus `add_blank_page`/`would_fit`), `home_pager.rs`
(`set_position`), `home_screen.rs` (edge-hold/fling/page-switch-animation
state machine, `drag_edge_indicator`/`drop_target_fits` accessors),
`home_widgets.rs` (the weather module's `j1` rewrite), `render.rs` (the
widget-card redesign, the edge indicator, the "no room" drop-target style,
enlarged page dots), `main.rs` (two call-site signature updates for the
drawer-drag hand-off's now time/height-aware `external_drag_motion`), and a
new `examples/render_widget_evidence.rs` host harness. No kernel, device
tree, boot, radio, or second-core change; no new Nix package or font. The
existing `.#handheld-shell-rust`/`.#card-shell` outputs and the
`k230-coherent-shell` NixOS configuration absorb it.
