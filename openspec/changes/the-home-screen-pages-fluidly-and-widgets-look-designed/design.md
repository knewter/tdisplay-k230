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

### 3. `WidgetKind` gains two variants, not a separate `style: ClockStyle` field on `HomeItem::Widget`

Adding a style field to `HomeItem::Widget { widget: WidgetKind, style: ... }`
would need either an `Option<ClockStyle>` (meaningless for Battery/Weather)
or a default-valued new field threaded through every existing call site and
every schema-2 save file already on a board -- a real migration concern for
a "just landed" feature. Modeling each clock style as its own `WidgetKind`
variant (`Clock`/`ClockMinimal`/`ClockAnalog`) is purely additive to the
existing `#[serde(rename_all = "snake_case")]` tag: an old save file simply
never contains `"clock_minimal"`/`"clock_analog"`, and a new one just starts
using them. `span()` already dispatches per-variant, so a wider analog
face vs. the two full-width line styles falls out for free. The tradeoff:
`WidgetKind::ALL`'s length is now load-bearing for the picker's row count
(`home_screen::picker_row_count`) -- fixed by deriving that count from
`WidgetKind::ALL.len()` instead of a hand-typed literal, so a future
fourth style cannot silently desync the two.

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

### 6. No new font package

`render.rs::FONT_FAMILY`'s own doc comment already recorded, for a prior
rendering-only fix, that this image ships exactly one family
(`pkgs.dejavu_fonts`, `nix/shell.nix`: "One family is enough") and that
pulling in a second is a blob-inventory/image-size change out of scope for
rendering work alone. That reasoning applies again here. DejaVu Sans has no
Light/Thin face for a true "thin" hero clock; the "Minimal line" style
instead uses Normal weight (vs. Bold for "Big stacked") plus a touch of
tracking and reduced opacity to read as visually lighter. A future pass
could add a small variable sans (e.g. Inter) if the visual gap matters
enough to justify the closure-size and build-risk cost -- this pass did not
attempt it partly because this host environment cannot prove a brand-new
nixpkgs source fetch actually succeeds under the coordinator's own
cross-build sandbox, and getting that wrong would break everyone's build,
not just this widget.

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
