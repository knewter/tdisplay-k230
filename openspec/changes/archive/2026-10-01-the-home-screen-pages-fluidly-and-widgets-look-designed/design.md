## Context

`home_screen::HomeScreen` already had a working, if slow and silent,
edge-hold page turn: a single `EDGE_HOLD_MS: u32 = 550` constant and an
instant `self.pager.set_page(next)` jump, both computed inline in `tick()`.
`home_widgets.rs`'s Clock/Battery/Weather modules already separated *content*
(host-testable, no touch surface) from *rendering* (`render.rs::
paint_widget_card`, plain `shadowed_label` text calls). Neither needed a
rewrite from scratch; both needed the mechanism widened and the paint code
replaced.

## Goals / Non-Goals

Goals: make cross-page dragging read as deliberately responsive (dwell
timing, visible affordance, fling, new-page creation, a "no room" cue);
redesign every widget's visuals without breaking its existing content/cache
logic; keep every existing `home_state`/`home_screen` test passing and add
coverage for the new timing/creation/fling/no-room behavior; produce visual
evidence without the board.

Non-goals: widget resizing; a new font package; touching
`nix/card-shell/` or any theme-picker file; changing where weather data
comes from (still wttr.in, still `curl`).

## Decisions

### 1. One eased `PageSwitchAnim`, driven independently of `HomePager`'s own drag/momentum/settle state

The old edge-hold code called `self.pager.set_page(next)` -- an instant,
un-eased jump, chosen originally because nothing at the time needed it to
animate. Making it slide smoothly could have reused `HomePager`'s own
`settle` field (already an eased from/target/elapsed/duration), but that
field's owner is a live *touch* drag's release; reaching into it from
`home_screen` for an edge-hold/fling trigger would mean either exposing a
`start_settle`-equivalent publicly (blurring "who owns this pager's motion
right now") or risking a real touch-driven settle and an edge-hold-driven
one fighting over the same field on the same tick.

Instead, `HomePager` gained one small, narrow addition:
`set_position(position, count)` -- an unconditional, un-animated setter
(clamped, clears velocity/settle) that assumes the caller supplies an
already-eased value. `home_screen::PageSwitchAnim { from, target,
elapsed_ms, duration_ms }` owns the easing curve entirely on the
`HomeScreen` side and calls `set_position` every tick. This keeps the two
animation *sources* (a live touch drag, and a triggered edge-hold/fling)
structurally separate: `HomePager` never runs both at once because nothing
in this change ever calls both `pager.down`/`pager.motion` and
`start_page_switch` for the same touch.

### 2. `note_drag_point`/`maybe_fling`/`advance_edge_hold` factored out of both drag paths

The internal (touch-tracked, `Contact`-gated) drag path and the external
(drawer-origin, no `Contact`) drag path used to each inline their own
edge-zone check. Both now funnel through one `note_drag_point(point,
time_ms, width, height)` that updates `edge_side`, resets the dwell timer on
a zone change, and calls `maybe_fling()`. This was worth the refactor
because task 1 asks for the *same* fling/edge-hold/no-new-page-
double-triggering behavior on both paths, and two independently-tuned copies
of the same threshold logic is exactly the kind of drift this project's own
`AGENTS.md` warns about.

### 2a. `drag_track_ms: Option<u32>`, not a bare `u32`, for the fling velocity baseline

The very first motion sample after a drag begins has no prior point to
diff against. Rather than seed `drag_track_ms` with the drag's start time
(which `tick()`-driven drag starts, e.g. promoting a long-press into a
rearrange, do not have -- `tick` only receives an elapsed-ms accumulator,
never an absolute timestamp), `reset_drag_tracking()` sets it to `None` and
`note_drag_point` only computes a velocity when a prior `Some` baseline
exists. This sidesteps needing `tick()` to know the wall clock at all, and
guarantees a drag's very first sample can never read a stale, wildly-large
elapsed time as if it were real motion.

### 3. `WidgetKind` gains one variant per clock style, not a separate `style: ClockStyle` field on `HomeItem::Widget`

Adding a style field to `HomeItem::Widget { widget: WidgetKind, style: ... }`
would need either an `Option<ClockStyle>` (meaningless for Battery/Weather)
or a default-valued new field threaded through every existing call site and
every schema-2 save file already on a board -- a real migration concern for
a "just landed" feature. Modeling each clock style as its own `WidgetKind`
variant (`Clock`/`ClockMinimal`/`ClockAnalog`, and now `ClockDotMatrix`) is
purely additive to the existing `#[serde(rename_all = "snake_case")]` tag:
an old save file simply never contains `"clock_minimal"`/`"clock_analog"`/
`"clock_dot_matrix"`, and a new one just starts using them. `span()`
already dispatches per-variant, so a wider analog face vs. the three
full-width line/readout styles falls out for free. The tradeoff:
`WidgetKind::ALL`'s length is load-bearing for the picker's row count
(`home_screen::picker_row_count`) -- fixed by deriving that count from
`WidgetKind::ALL.len()` instead of a hand-typed literal, so adding
`ClockDotMatrix` in round 3 needed no change to that count logic at all,
exactly the point of the original design. Only [`WidgetKind::label`]'s
*user-facing* string changed to match round 3's own style names (Bubble/
Thin/Dot matrix/Analog) -- the Rust variant identifiers, and therefore the
serialized tag, deliberately did not get renamed to match, since a board
may already have saved a layout using the old names.

### 4. Weather switches to wttr.in's `j1` JSON wholesale, cache shape included

The old `WeatherSnapshot { condition, temperature, fetched_unix_secs }`
could not carry a forecast, a high/low, or a location at all -- `%C|%t`
never had that data. Rather than adding a second, parallel fetch for the
extra fields, the whole snapshot moved to `j1` (`temperature_c: i32`, not a
formatted string with degree/unit baked in, since the widget now needs the
raw number for its own hero-numeral formatting). This is a breaking change
to the *cache file's* shape, deliberately not migrated: `weather.json` is a
disposable, re-fetchable cache (unlike `home.json`'s persisted layout,
losing which loses a person's actual arrangement), so an old-shape cache
file simply fails to deserialize, `load_cache` returns `None`, and the next
poll re-fetches -- one extra network round-trip, not a data-loss risk.

### 5. Forecast strip capped at 3 entries, not the task's suggested 3-5

The Weather widget's own card is 2x2 (`WidgetKind::span`), which at this
panel's real grid geometry (`home_grid`'s `ROW_HEIGHT`/`tile_width`) works
out to roughly 253x350px. Three forecast columns at a legible size (an
11-13px label/temperature pair plus a small glyph) fill that width
comfortably; four or five would either shrink past comfortable legibility
at 330ppi or force the card wider than its 2x2 footprint. `j1`'s own hourly
data has enough entries for 5 if a future pass widens the card; this one
keeps the fixed 2x2 span the sibling change already committed to and picks
the count that actually reads well at it.

### 6. One new font, added in round 3, after actually proving it builds

The first pass (see the superseded reasoning this replaces, below) declined
to add a font at all, partly because "this host environment cannot prove a
brand-new nixpkgs source fetch actually succeeds." Round 3's own research
task required actually trying it, which changed the calculus: `nix build
--impure --expr '...pkgs.inter'` against this repo's own pinned `nixpkgs`
input succeeded directly from `cache.nixos.org` (5.1 MiB compressed, 14.3
MiB unpacked) -- so the risk that motivated declining a font turned out not
to hold. `pkgs.inter` ships two things: a *variable* font (`InterVariable
(-Italic).ttf`, ~1.75 MiB combined) and a classic *static* collection
(`Inter.ttc`, 13,172,948 bytes, every weight from Thin to Black as its own
named face under one "Inter" family, confirmed with `fc-scan`). The
variable font was checked first and ruled out: `pango-sys` at this repo's
pinned version (0.21.5) has no binding at all for
`pango_font_description_set_variations`, confirmed directly with a scratch
`cargo check` against the real crate (not assumed from a changelog), so
that axis is unreachable from this client regardless of which font ships
it. `Inter.ttc`'s static faces need no such binding -- `pango::Weight`
already knows how to select a named face by weight, exactly the mechanism
this shell's existing DejaVu Book/Bold lookup already uses -- so that is
the one file `nix/shell.nix`'s `clockDisplayFont` extracts (via a small
`pkgs.runCommand`, so the final image closure carries only that one file,
not all of `pkgs.inter`; the fuller package is a build-time-only input,
discarded after extraction since the copied font file contains no store-
path references of its own). Used for the Clock widget's Bubble/Thin
styles only, per round 3's own "ONE small... font" instruction -- Dot
matrix draws its own dots and Analog's only text stays on `FONT_FAMILY`.

**Superseded first-pass reasoning, kept for the record:** "`render.rs::
FONT_FAMILY`'s own doc comment already recorded, for a prior rendering-
only fix, that this image ships exactly one family (`pkgs.dejavu_fonts`,
`nix/shell.nix`: 'One family is enough') and that pulling in a second is a
blob-inventory/image-size change out of scope for rendering work alone...
this pass did not attempt it partly because this host environment cannot
prove a new nixpkgs source fetch actually succeeds under the coordinator's
own cross-build sandbox." That specific risk is what round 3 actually
tested and found not to hold, for this exact font, in this exact
environment -- the general caution was reasonable given what was known at
the time, but "cannot prove it" is not the same claim as "would fail."

### 7. Host Cairo render harness for evidence, not a QEMU touch-injection script

The sibling change's own evidence README documents a QEMU/injected-touch
driver that was silently terminated at a reproducible point across three
attempts, on this same shared build machine. Rather than re-attempt that
same fragile path for a change that is 90% pure rendering, this change adds
`examples/render_widget_evidence.rs`: it calls the real, unmodified
`render::paint_home` offscreen against a `cairo::ImageSurface`, with two
synthetic `AppearanceSnapshot` themes built from that struct's own public
fields (not a live Omarchy IPC session -- this host has no compositor to
receive one). The two drag-mechanic screenshots in that evidence set are
not faked: they drive `HomeScreen` through its real public `down`/`motion`/
`tick`/`external_drag_motion` API, the same one a real touch event stream
calls. This proves the widget-drawing and drag-state-machine code paths
genuinely execute and look as designed; it does not substitute for
QEMU/board proof of real touch input, real compositor compositing, or
daylight/panel color reproduction, and is not claimed as such anywhere in
this change's evidence or tasks.

### 8. A board look-and-fix round-trip, before physical-board acceptance

The coordinator deployed the first pass's build to the board for the
user's judgment and, from the host evidence screenshots alone (not a board
photograph), flagged five concrete visual issues: the weather card's
condition tint leaking past its rounded corners; a 1px border on every
widget reading as "boxed-in"; an oversized battery ring with its percentage
captioned beneath instead of inside it; the "Big stacked" clock cramped
against the card's left edge with both lines at equal visual weight; and a
forecast strip too small to read at arm's length. Each is a rendering-only
fix, addressed in this same change rather than a follow-up:

- **Corner leak:** `paint_condition_tint` painted an unclipped rectangle.
  The call site now wraps it in the card's own rounded clip path (the exact
  clip `paint_widget_surface`, below, already establishes for the card's
  fill, just re-applied since Cairo's clip does not persist across a
  `save`/`restore` pair once popped).
- **Borders:** `service_card`'s border stroke (drawn from the theme's own
  `border`/`selected-border` brush when the theme defines one) was never
  wrong on the panels that still use it -- the dock, the folder overlay,
  the picker sheet all keep it, and still look consistent doing so, since
  they sit inside other chrome (a card row, a scrim) that already frames
  them. A widget has nothing else framing it; the same border read as a
  literal box around content sitting directly on the wallpaper. Decision 9
  covers the replacement in more detail.
- **Battery ring:** scaled to 70% of its first-pass radius, and the
  percentage moved from a caption below the ring (`caption_line`) to a new
  `ring_percent_label`, sized and positioned to sit centered inside the
  ring itself. The charging bolt moved out of the ring's dead center (where
  it would now collide with the centered percentage) to a small accent
  badge circle at the ring's own upper-right, the glyph drawn in the
  card's own background color for contrast against the accent fill --
  reading as a distinct status badge rather than competing with the
  number for the ring's center.
- **Clock breathing room:** the left inset grew from `pad` to `pad * 1.7`,
  and the minute line dropped from Bold to Normal weight (the hour stays
  Bold and accent-colored) so the pair reads as a clear hour-first
  hierarchy rather than two equally-weighted numbers pressed against the
  edge. The date caption grew from 14px to 17px.
- **Forecast legibility:** each column's glyph grew from 22px to 32px and
  its temperature label from 13px to 17px, with the whole block given
  roughly twice its first-pass vertical room (90px reserved instead of
  46px) so the larger glyphs and text have room to breathe rather than
  being compressed into the same cramped footprint.

### 9. `paint_widget_surface`: a dedicated, borderless widget background

**Superseded by decision 10, round 3:** the function this decision
describes no longer exists -- board review round 2's own fix (a filled
surface instead of a bordered one) was itself replaced by "no surface at
all" once the user judged the *filled* card itself, not just its border,
as something that "doesn't have to" be there. Kept below for the record of
why a dedicated painter (rather than a flag on `service_card`) was the
right shape for the problem as understood at the time; that reasoning
carried forward into decision 10's own halo/backdrop functions, which are
equally dedicated and equally narrow.

Rather than pass a flag into `service_card` to suppress its border only for
widgets (which would leave `service_card` itself doing two visually
different things depending on a boolean, for every one of its many other
call sites to reason about), widgets got their own small, single-purpose
painter. `paint_widget_surface` clips to the card's own rounded rect,
paints a handful of offset, low-alpha filled passes underneath as a cheap
soft shadow (no true blur -- Cairo's toy API has none, and a real one would
mean an intermediate render target on every dirty repaint), then fills the
theme's own "launcher"/"background" brush through the existing
`overlay_brush` helper at a fixed ~80% alpha via `paint_with_alpha`,
regardless of whatever alpha that brush's own authored stops carry. It
never queries a "border" token at all. This keeps `service_card` completely
unchanged for every other panel in this shell, and gives widgets one
narrow, easily-audited place that owns "what a widget card's own background
looks like" independent of whatever any other panel decides to look like.

### 10. Round 3: no card at all, legibility from a luminance-derived halo/glow

Board review, round 2, on the *first* pass's own evidence: "the widgets
don't have to have a background like they do." `paint_widget_surface`
(decision 9) is removed entirely -- `paint_widget_card` now paints nothing
behind its own content but whatever the caller already painted (the real
wallpaper). Legibility instead comes from `glow_for(rgb)`: a plain
luminance check (Rec. 709 coefficients) on the glyph's own resolved color,
returning black for a light glyph and white for a dark one -- literally
what the board review asked for ("dark text gets a light halo, light text
gets a dark shadow"), computed from the theme's own resolved value rather
than a fixed shadow color that would look wrong under the other theme.
Two primitives apply it:

- `draw_layout_halo` -- for text: draws the same Pango layout again at 8
  points evenly spaced around a small circle, each at a low alpha, before
  the real glyph on top at full opacity. This is a standard "poor man's
  blur" (multiple offset copies standing in for a true Gaussian blur, which
  Cairo's toy API has no support for at all) -- cheap, since a widget only
  repaints when its underlying value changes or once a minute for the
  clock, never per frame.
- `draw_soft_backdrop` -- for small graphic elements (the weather condition
  glyph, the battery ring, the absent-battery outline): a single soft
  filled circle behind the shape, the same idea without needing a text
  layout to redraw.

Every caption that previously used a lower-alpha "muted" tone
(`style.muted`, `caption_line`'s old 0.82 alpha) moved to the theme's full
`text`/`accent` colors at full opacity, the halo doing the contrast work
instead of a dimmer color -- a low-alpha color plus a halo still reads as
faint against a busy photo; a full-strength color plus a halo reads
clearly regardless of what is directly underneath it.

**The four clock styles, rebuilt from research rather than guessed:** with
no card constraining the layout to "content inside a box," Bubble and Thin
both moved from round 2's left-aligned-with-padding layout to centered,
matching the actual Pixel/iOS convention `docs/design/
clock-widget-research.md` surveys (a hero clock floating on wallpaper,
not boxed text) -- and both now use `CLOCK_FONT_FAMILY` (decision 6) at a
real Black/Thin weight instead of DejaVu's Bold/Normal standing in for
"heavy" and "light." Dot matrix is new, entirely procedural (decision
document's own digit-bitmap table), needing no font at all -- the
research survey's own "no font dependency" point from the r/unixporn/
Rainmeter/Conky tradition. Analog dropped its dial fill and ring stroke
entirely (`draw_analog_clock` no longer paints either), leaving only tick
marks and hands, per the same survey's Braun/Dieter Rams citation: "no
dial background, just markers and hands." The two hands get the halo
treatment too (they are this widget's own thinnest strokes, most likely to
vanish against a busy photo); the twelve tick marks stay plain, since
haloing all twelve reads as clutter rather than polish.

### Rejected: making the "no room" drop-target highlight always fully visible

The drop-target highlight rect is sized to the *single* raw grid cell under
the finger; the floating dragged-item preview is sized to the *dragged
item's own span*, centered at the same finger point. For a widget-sized
drag (2x2 or 4x2), the preview is necessarily larger than that one
highlighted cell and, centered on the same point, usually covers most or
all of it -- this is true for every existing drag in this shell, not new
behavior this change introduces. Redesigning the highlight to draw *outside*
the lifted preview's bounds (e.g., only its uncovered edges) was considered
and rejected: it would make the accepting-drop case look different from
every other reference launcher's convention (a highlighted cell the item
visibly sits inside), for a cosmetic gain only visible in the one moment a
widget-sized item hovers dead-center over its own target. The stronger,
already-shipped proof that "no room" actually blocks the wrong drop is
`HomeScreen::drop_target_fits`, unit-tested directly
(`dragging_a_widget_over_another_widgets_full_span_shows_no_room`).
