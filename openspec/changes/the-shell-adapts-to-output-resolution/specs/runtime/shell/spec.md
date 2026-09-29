## ADDED Requirements

### Requirement: The shell fills a whole non-panel output instead of letterboxing it

*Grounding: `nix/rust-shell-client/src/main.rs`'s `is_whole_output` (reads
`OutputState`, matches a configure's `(width, height)` against a known
output's own `logical_size`) and `lib.rs`'s `configure_preserves_aspect`,
both read for this change. `feat/hdmi-pillarbox` (commit `4c2eb57c`,
2026-09-29) recorded a board log of a real whole-output configure this
logic must handle: `pillarbox 1080x1920 -> 885x1920`, HDMI-A-1, Home and
wallpaper drawn (that log is this requirement's evidence that the shell
does receive such a configure on real hardware; it predates this change's
own fix and describes the pillarboxed behavior being replaced). Whether the
*reflowed* (non-pillarboxed) fill has itself been observed on the physical
board or under QEMU is <!-- UNVERIFIED --> as of this change: the evidence
committed with it (`docs/evidence/shell-responsive/`) is host-rendered
through the production paint path with no Wayland connection, per that
directory's own `README.md`.*

When a Wayland layer-shell `configure` gives a surface exactly the size of
a currently known output (an HDMI monitor at its own resolution, at any
aspect ratio, landscape or rotated portrait), the shell SHALL accept that
size and paint its wallpaper, Home grid/dock, and Drawer/Shade/Settings/
Power panel chrome to fill it completely, with no letterboxed or
pillarboxed band of unpainted or differently-colored space. A configure
that is not the size of any known output (in particular, a single-axis
shrink such as an on-screen keyboard's exclusive zone) SHALL continue to be
rejected exactly as before this requirement existed, leaving the surface at
its last accepted geometry.

This requirement governs whether the *surface itself* is allowed to take
the output's full size and whether what already reflows (the wallpaper
fill, Home's row count, panel chrome) is allowed to do so. It does not by
itself require every on-screen element to relayout for the new size:
`paint_wifi`'s own pre-existing non-uniform scale and the theme chooser are
untouched by this requirement and remain named, out-of-scope follow-up work
in `design.md`.

#### Scenario: An HDMI monitor is configured at its own landscape resolution

- **WHEN** the compositor sends a layer-shell `configure` whose size
  matches a connected HDMI output's own logical size (e.g. 1920x1080)
- **THEN** the shell accepts that size for the surface, and the wallpaper,
  Home, and any open Drawer/Shade/Settings/Power panel fill it edge to edge
  with no pillarboxed column

#### Scenario: An on-screen keyboard's exclusive zone shrinks one axis

- **WHEN** a `configure` reduces only the surface's height (or only its
  width), to a size that does not match any known output's own logical size
- **THEN** the shell rejects that configure and keeps the surface at its
  last accepted geometry, exactly as it did before this requirement

#### Scenario: The Drawer reflows its column count with a wider output

- **WHEN** the Drawer is open on a surface wider than the 568px design width
- **THEN** its app grid uses more columns, proportional to the extra width,
  instead of the same 4 columns stretched into wider, sparser tiles

### Requirement: Home's grid reflows its column count without losing or reordering pinned items

*Grounding: `nix/rust-shell-client/src/home_state.rs`'s `HomeLayout::
reflow_to` and its own `columns` field, `home_grid::columns_for_width`, and
`home_screen::HomeScreen::sync_columns`, all read for this change. Proven
host-side by `home_state.rs`'s `reflow_to_a_wider_column_count_never_loses_
or_reorders_items`, `reflow_to_round_trips_4_then_8_then_back_to_4`,
`reflow_to_is_a_no_op_when_columns_already_match`, `reflow_to_keeps_a_
multi_span_widget_intact_as_one_item`, and `home_screen.rs`'s `sync_columns_
reflows_to_a_wide_output_and_back_without_losing_items` -- all host unit
tests, `<!-- UNVERIFIED -->` on the physical board or under QEMU: no test
here drives a real touch/drag gesture against a reflowed grid, only the
pure placement/geometry functions a real drag also calls.*

The Home screen's grid and dock SHALL use more columns, proportional to the
surface's own width (the same reflow the Drawer's grid already uses),
instead of a fixed column count that leaves a wide output's extra space as
bigger gaps between the same four columns. Every icon, folder, and widget
already pinned to the grid SHALL remain present after a column-count
change, in its original relative reading order (top-left to bottom-right,
page by page); a widget's multi-cell span SHALL remain a single, contiguous,
non-overlapping footprint at the new column count. Reflowing to a column
count already in effect SHALL NOT alter the stored layout.

#### Scenario: An HDMI monitor is configured wider than the panel

- **WHEN** Home is displayed on a surface wider than the 568px design width
- **THEN** its grid and dock use more columns, proportional to the extra
  width, and every previously pinned item is still present, in its
  original relative order

#### Scenario: The output returns to the panel's own width

- **WHEN** Home's surface returns to exactly 568px wide after having been
  reflowed wider
- **THEN** the grid returns to exactly 4 columns and every item is restored
  to its original page and slot

### Requirement: Settings' body content is a centered, density-scaled column

*Grounding: `nix/rust-shell-client/src/lib.rs`'s `density_scale` and
`settings_content_transform`, `render.rs`'s `scene` (the transformed block
in its `Route::Settings` arm) and `settings_panel_h`, and `service_ui.rs`'s
`panel_intent` (the matching touch-point remap), all read for this change.
Proven host-side by `lib.rs`'s `density_scale_is_pixel_identical_at_native_
and_bounded_above`, `settings_content_transform_fills_the_panel_at_native_
size`, and `service_ui.rs`'s `settings_row_taps_follow_the_scaled_centered_
content_column_on_hdmi` (which maps a real touch point through the same
transform `scene` paints with and confirms it still resolves to the
correct row, and that a point past the row still misses). `<!-- UNVERIFIED
-->` on the physical board or under QEMU: no host render or test here
opens a live Wayland connection or drives a real touch/drag gesture.*

Settings' body content (the row cards, sliders, and Power section below the
unscaled header strip) SHALL paint within a centered column no wider than
the design's own 568px, scaled up on a surface taller and denser than the
568x1232 design so its rows and text are not left disproportionately small
relative to the extra space, and the panel containing it SHALL grow to
match that scaled content's own real height instead of remaining a short,
content-sized "stub" over empty space below it. A tap SHALL resolve against
that same centered, scaled position -- never the row's un-transformed
design-unit position -- so a real touch always lands on what is actually
drawn there.

#### Scenario: Settings is opened on a wide landscape HDMI output

- **WHEN** Settings is displayed on a surface wider than the design's own
  568px
- **THEN** its body content paints in a centered column no wider than 568
  design px times the surface's own density scale, not stretched edge to
  edge

#### Scenario: Settings is opened on a tall, dense HDMI output

- **WHEN** Settings is displayed on a surface both taller and denser than
  568x1232
- **THEN** its body content paints larger, proportional to that density,
  and the panel containing it grows to match instead of leaving empty
  space below a content-sized stub

#### Scenario: A person taps a Settings row on a scaled, centered output

- **WHEN** a person taps where a Settings row (e.g. the Reboot card) is
  actually drawn on a surface where the content column is scaled and/or
  offset from the panel's own left edge
- **THEN** that row's action fires, exactly as it would at the row's
  design-unit position on the native panel
