## Context

Layer: userspace, entirely inside `nix/rust-shell-client` (the Rust shell
client's own Wayland/Cairo code). No kernel, device tree, or Nix derivation
shape changes.

Read for this change: `nix/rust-shell-client/src/lib.rs` (`configure_size`,
`configure_preserves_aspect`, the removed `pillarbox_width`, and this
follow-up's `density_scale`/`reflow_columns`/`settings_content_transform`),
`main.rs` (the three `LayerShellHandler::configure` branches and the
removed `pillarbox` method), `render.rs` (`scene`, `paint_home`,
`paint_wifi`, `draw_wallpaper`, `settings_row_y`/`SettingsLayout`/
`settings_panel_h`), `home_grid.rs`, `home_pager.rs`, `home_state.rs`
(`HomeLayout::columns`/`reflow_to`), `home_screen.rs` (`sync_columns`),
`navigation.rs`, `service_ui.rs` (`panel_intent`'s Settings arm),
`background_decode.rs`.

This design doc covers two passes on the same branch: the initial
whole-output-fill change (accept-and-fill, Drawer column reflow), and a
coordinator-requested follow-up landed immediately after (Home grid
reflow, a Settings content-density scale, a committed pixel-identity
test). Both are described together below rather than as separate
documents, since the follow-up directly extends and in one case
(Home's grid) reverses an explicit "rejected/deferred" call the first
pass made.

## Audit: what depends on the fixed 568x1232 design size today

| Surface | Mechanism | Reflows with output size? |
| --- | --- | --- |
| Wallpaper background fill (`render::RendererCache::draw_wallpaper`) | Fills `(0,0,width,height)` directly with the theme's solid color/brush | Yes, already — no code change needed. Confirmed: `docs/evidence/shell-responsive/wallpaper-1080x1920.png` is one uniform color across all 2,073,600 pixels. |
| Home grid rows (`home_grid::rows_per_page`, `grid_top`/`dock_top`) | `ROW_HEIGHT` is a fixed px pitch; row count = available height / that pitch | Yes, already — more height means more rows, no code change. |
| Home grid columns (`home_grid::COLUMNS`, `home_grid::columns_for_width`, `home_state::HomeLayout.columns`) | Was a `pub const = 4`, only `tile_width` a function of width | **Changed by the follow-up.** `columns_for_width` (`crate::reflow_columns` at scale `1.0`) now decides the *count* too; `HomeLayout.columns` + `reflow_to` keep the persisted layout safely in sync — see the dedicated decision section below. |
| Home dock (`home_grid::DOCK_SLOTS`, `dock_slot_width`) | Fixed slot count, width-derived slot width | **Still no**, deliberately: `DOCK_SLOTS` stays 4 on every surface size in both passes. A dock slot count tied to width raises the same "what does a stored dock index mean now" question the grid's `columns` field answers, plus a UX question this change does not resolve (does a wider dock re-pin more apps automatically, or stay a fixed quick-launch row regardless of space). Left as a further, separately-scoped follow-up. |
| Drawer grid (`navigation::COLUMNS`, `tile_rect`/`tile_at`/`max_scroll`) | Was the same fixed-`COLUMNS` shape as Home's grid | **Changed by the first pass.** `columns_for_width` (now delegating to the shared `crate::reflow_columns`) makes the column count itself scale with width; no persisted per-column state exists here (unlike Home), so this was safe to change without a data-model/drag-logic audit. |
| Drawer/Shade/Settings/Power panel chrome (`render::scene`'s background/border fill) | Fills `(0, panel_y, w, panel_h)` with `w`/`h` = the real configured size | Yes, already — no code change needed once the surface itself is allowed to be whole-output-sized (the first pass's `main.rs` change). |
| Settings body content (`settings_row_y`, row card x-positions, the Power section, the confirm dialog) | Fixed pixel offsets from the panel's own top/left, not capped or centered | **Changed by the follow-up.** Now painted inside a `cr.translate`/`cr.scale` content transform (`crate::settings_content_transform`) that centers a design-568-wide column, scaled by `crate::density_scale` — see the dedicated decision section below. The unscaled header strip (title/Done/Device controls/Themes link) is deliberately excluded. |
| Wi-Fi sub-page (`render::paint_wifi`) and the theme chooser | `cr.scale(width / 568.0, height / 1232.0)` — draws in 568x1232 design units, then non-uniformly scales; `wifi_ui.rs` hit-testing inverse-maps touch points through the identical scale | Consistently scaled (paint and hit-test agree), but not uniform — a wide/tall configure stretches or squashes these sub-pages' own glyphs. Pre-existing; unaffected by either pass — `scene`'s Settings arm returns before reaching the new content transform whenever either is open. |
| Whole-surface Wayland configure acceptance (`lib.rs`, `main.rs`) | `configure_preserves_aspect` rejects (previously: pillarboxes) anything outside a 10% band of 568:1232 | **Changed by the first pass**: a whole-output configure is now accepted at its own size regardless of aspect; a non-whole-output configure (the keyboard-squish case) is still rejected exactly as before. |
| Home/Drawer icon and text pixel sizes (`home_grid::ICON_SIZE`/`ROW_HEIGHT`, `navigation::ROW_HEIGHT`) | Fixed pixel constants, independent of `density_scale` | **Still no, deliberately, in both passes.** Only the *column count* reflows for these two grids; the icons/text themselves stay the panel's own native pixel size at every surface size. See "Non-goal" below for why. |

## Decision: accept-and-fill at the configure layer, reflow opportunistically above it

`main.rs`'s three `configure` branches now accept a configure that fails
`configure_preserves_aspect` when `is_whole_output(width, height)` is true
— the surface's own `(width, height)` becomes exactly the output's, no
pillarbox column requested. Everything above that layer (`render.rs`,
`home_grid.rs`, `navigation.rs`) already receives real pixel width/height as
plain arguments, not a compiled-in `568.0`/`1232.0`, for every surface
*except* the Wi-Fi sub-page and Settings' row offsets — so most of the
"reflow" is really "stop actively resizing the surface down to a shape
those functions were never given a chance to fill." The Drawer's column
count is the one piece of genuine new reflow logic this change adds, because
it was the one place doing so was low-risk (see next section).

`is_whole_output` (a plain immutable read of `OutputState`) replaces
`pillarbox`'s identical whole-output check; the only change to that check
itself is what happens on a `true` result (accept the configure's own size)
versus `feat/hdmi-pillarbox`'s `false` fallback shape (request a narrower
column). The check that must stay correct — telling a real output resize
apart from a keyboard-exclusive-zone squish, which is never the size of any
known output — is unchanged and still covered by `lib.rs`'s own
`configure_preserves_aspect_accepts_uniform_resize_only` test.

## Decision (follow-up): Home's grid reflows via a `columns` field on the persisted layout, not a threaded parameter

The first pass explicitly deferred this (see the superseded reasoning this
section used to hold, now resolved): `home_state::HomeLayout.pages` is
persisted to `$XDG_STATE_HOME/k230-shell/home.json` and every placement/
drag/merge/rearrange/folder code path in `home_screen.rs` indexes it by a
column count. Threading a `columns: usize` *parameter* through
`anchor_at`/`fits_at`/`place`/`would_fit`/`first_fit`/`place_first_fit` and
every `home_screen.rs` call site was the change considered and rejected —
too many places to keep consistent, and no way to verify the result against
real drag/touch behavior without the board.

The follow-up instead gives `HomeLayout` its own `columns: usize` field
(`#[serde(default)]` so a pre-existing saved file without it loads as `4`,
its only-ever value until now). Every internal placement/fit/anchor
computation reads `self.columns` instead of a parameter or the
`home_grid::COLUMNS` constant — so `place`/`would_fit`/`first_fit`/
`place_first_fit`/`anchor_at`'s *signatures* did not change at all, and
every existing call site in `home_screen.rs`, `main.rs`, and the two
`examples/` harnesses kept working unmodified. Only the *rendering/hit-
testing* functions in `home_grid.rs` (`tile_rect`, `tile_content`,
`spanned_tile_rect`, `slot_at`, `plate_top_left`) gained an explicit
`columns` parameter, always sourced from `home.layout.columns` at the one
or two call sites each has (`render::paint_home`, `home_screen.rs`'s own
hit-testing) — a single source of truth a paint and its matching hit-test
can never independently disagree about.

`HomeLayout::reflow_to(columns, apps_per_page)` is the one thing that ever
changes `self.columns`: it flattens every stored item in reading order
(page by page, row-major, skipping cells a multi-span widget merely
covers — the same `covered_slots` its own placement already uses), then
re-inserts each one, in that exact order, through the already-tested
`place_first_fit` bin-packing at the new column count. This is why a
widget's span survives intact (it goes through the same fitting algorithm
a fresh placement does, never a naive re-chunk that could split it across
rows) and why nothing is ever lost (every flattened item is re-placed;
`place_first_fit`'s own existing overflow-to-a-new-page behavior is the
worst case, never a dropped item) or reordered (the flatten pass reads
strictly in the original order, and `place_first_fit` fills strictly
left-to-right, top-to-bottom). `home_state.rs`'s own
`reflow_to_round_trips_4_then_8_then_back_to_4` proves this is not just
order-preserving but *exactly* shape-preserving when every item still fits
on one page both ways (as it must for any realistic Home page).

`HomeScreen::sync_columns(width, height)` is the one call site that invokes
`reflow_to`, called from `main.rs`'s `draw_home` before every repaint (a
no-op once `self.layout.columns` already matches `home_grid::
columns_for_width(width)`, so calling it defensively is cheap) — this is
the choke point the design relies on: by the time any touch handler can
run, at least one `draw_home` for the current geometry has already
reflowed the layout, so painting and hit-testing never observe a
`self.layout.columns` that disagrees with the live width.

What remains genuinely unverified: every test proving this (`home_state.
rs`'s `reflow_to_*`, `home_screen.rs`'s `sync_columns_*`) is a host unit
test against the pure placement/geometry functions — none drives a real
finger drag against a reflowed grid. That gap is named in `tasks.md`'s
board-gated group, same as the rest of this change.

## Decision (follow-up): Settings gets a centered, scaled content column, not a full-surface non-uniform stretch

Settings' body content (the row cards, sliders, Power section, and confirm
dialog — everything `scene`'s `Route::Settings` arm paints after its
"Done" hit-test check, i.e. after the two early returns into `paint_wifi`/
`paint_theme_chooser`) is now wrapped in `cr.save(); cr.translate(content_x,
0.0); cr.scale(content_scale, content_scale); ...; cr.restore();`, where
`(content_scale, content_x) = crate::settings_content_transform(width,
height)`: `content_scale` is `density_scale`'s own value, and the column's
own width is the design's `568` at that scale, capped to the real surface
width and centered. Because the transform is *uniform* (`content_scale`
applied equally to both axes, unlike `paint_wifi`'s existing non-uniform
`width/568.0, height/1232.0`), every existing fixed-pixel literal in that
block (`w - 48.0`, `settings_row_y(row)`, `SETTINGS_ROW_H`, ...) keeps its
original, already-correct proportions without a single literal changing —
`w` itself is shadowed to `crate::DESIGN_WIDTH` (568.0) for exactly this
block, so those literals compute the same design-space rect they always
did; only the surrounding transform decides where that rect actually lands
on screen.

The header strip above it (the bold "Settings" title from the shared
per-route heading, plus this arm's own "Done"/"Device controls"/"Themes ›"
row) is deliberately left *outside* the transform, at its original real-
pixel position — matching Shade's and the Drawer's own chrome, which never
scales either, and avoiding a hit-test change for the "Done" tap zone
(`service_ui::panel_intent`'s `end.1 < 108.0 && end.0 > w - 150.0` check,
unchanged). Only the content below it centers and scales.

`settings_panel_h` (and therefore `panel_travel_height`, the close-drag
travel distance, and the backdrop dim) multiplies its own "natural content
height" inputs by the same `content_scale` — so the *background panel*
grows to match the *content* actually painted inside it, instead of a
mismatch where the panel stays content's-old-size while the content itself
paints bigger. This directly answers the "short stub panel" report: on a
tall, dense output, Settings' rows are genuinely bigger (not just
repositioned), so the panel containing them is genuinely taller, not a
small box floating over empty space.

`service_ui::panel_intent`'s `Route::Settings` arm calls the identical
`crate::settings_content_transform(width, height)` and remaps `end` into
that same design-unit space (`(end.0 - content_x) / content_scale, end.1 /
content_scale`) before any of its row-rhythm checks — but only after its
own `OVERLAY_DISMISS_ZONE_Y` and "Done" corner checks, which stay in real
coordinates to match the still-unscaled header. `service_ui.rs`'s
`settings_row_taps_follow_the_scaled_centered_content_column_on_hdmi` test
computes its expected tap position through the same shared function
`scene` paints with (never a hand-picked literal), at both a wide and a
tall HDMI size, and confirms the reboot row still resolves and a point well
past it still misses.

Rejected alternative, same reasoning as the first pass's own rejected
"single non-uniform `cr.scale` for everything": stretching Settings'
content to the *surface's own* aspect ratio (a `width/568, height/1232`-
style scale, like `paint_wifi`'s) was not considered here at all, for the
identical reason — it would squash or stretch every row/glyph whenever the
surface aspect isn't close to 568:1232, exactly the defect
`configure_preserves_aspect` exists to prevent for the keyboard-squish
case.

## Non-goal, both passes: Home/Drawer icon and text pixel sizes do not scale with `density_scale`

Both the Drawer's `columns_for_width` and Home's now call
`crate::reflow_columns(width, 1.0, base_columns)` with `scale` pinned at
`1.0`, not `density_scale`'s own value — deliberately: `reflow_columns`'s
own doc explains that a grid's extra space should become *more cells*, not
*bigger cells with the same gaps*, so baking `density_scale` into the
column-count formula without *also* scaling `ICON_SIZE`/`ROW_HEIGHT`/the
tile margins by the same factor would make columns wider without making
their contents bigger — reintroducing the exact "sparse" look this whole
change exists to fix, just with fewer, wider gaps instead of many.

Doing this properly — scaling `home_grid.rs`'s and `navigation.rs`'s own
icon/plate/label/row-pitch constants by `density_scale`, the same way
Settings' content column now does — was considered for this follow-up and
set aside for time: unlike Settings' single content transform (one `cr.
scale` wrapping one block, one matching hit-test remap), the grid surfaces'
sizes are threaded through many small pure functions (`tile_width`,
`tile_content`, `dock_content`, `folder_app_rect_of`, `picker_row_rect`,
...) each of which would need a `scale` parameter alongside (or folded into)
their existing `columns` one, on both Home and the Drawer, doubling the
surface area of this change's own host-test coverage for a benefit already
substantially met by the column-count reflow alone (more, not tinier,
icons; no dead space). Named here as the next concrete follow-up, not
silently dropped.

## Rejected: a single non-uniform `cr.scale` for everything

`paint_wifi`'s existing `cr.scale(width / 568.0, height / 1232.0)` was
briefly considered as a model to extend to Settings/Shade generally (draw
once in design units, scale to fill). Rejected: a non-uniform scale
stretches or squashes every glyph and control whenever the surface's aspect
ratio isn't close to 568:1232 — exactly the defect
`configure_preserves_aspect` exists to prevent for the *keyboard-squish*
case, and no more acceptable here just because the cause is a monitor
instead of a keyboard. `paint_wifi`'s own use of it is a pre-existing,
narrow, low-traffic sub-page; not extended, not removed, by this change.

## Rejected: keep pillarboxing, just widen the column

Widening `pillarbox_width`'s column (e.g. to some fraction of the output
rather than the exact design aspect) was considered and rejected outright:
the operator's own instruction was that a wider monitor should be filled,
not float any column at all, regardless of the column's width.
