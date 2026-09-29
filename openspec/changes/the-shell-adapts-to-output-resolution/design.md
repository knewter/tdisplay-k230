## Context

Layer: userspace, entirely inside `nix/rust-shell-client` (the Rust shell
client's own Wayland/Cairo code). No kernel, device tree, or Nix derivation
shape changes.

Read for this change: `nix/rust-shell-client/src/lib.rs` (`configure_size`,
`configure_preserves_aspect`, the removed `pillarbox_width`), `main.rs`
(the three `LayerShellHandler::configure` branches and the removed
`pillarbox` method), `render.rs` (`scene`, `paint_home`, `paint_wifi`,
`draw_wallpaper`, `settings_row_y`/`SettingsLayout`), `home_grid.rs`,
`home_pager.rs`, `home_state.rs`, `navigation.rs`, `background_decode.rs`.

## Audit: what depends on the fixed 568x1232 design size today

| Surface | Mechanism | Reflows with output size? |
| --- | --- | --- |
| Wallpaper background fill (`render::RendererCache::draw_wallpaper`) | Fills `(0,0,width,height)` directly with the theme's solid color/brush | Yes, already — no code change needed. Confirmed: `docs/evidence/shell-responsive/wallpaper-1080x1920.png` is one uniform color across all 2,073,600 pixels. |
| Home grid rows (`home_grid::rows_per_page`, `grid_top`/`dock_top`) | `ROW_HEIGHT` is a fixed px pitch; row count = available height / that pitch | Yes, already — more height means more rows, no code change. |
| Home grid columns (`home_grid::COLUMNS`, `tile_width`) | `COLUMNS` is a `pub const = 4`; only `tile_width` (not the column count) is a function of width | **No.** A wide output gets 4 wider, sparser tiles, not more columns. Not changed by this proposal — see "Rejected/deferred" below. |
| Home dock (`home_grid::DOCK_SLOTS`, `dock_slot_width`) | Same shape as the grid: fixed slot count, width-derived slot width | No, same reason as the grid; deferred together (dock/grid column counts are coupled by design — see `DOCK_SLOTS`'s own doc comment). |
| Drawer grid (`navigation::COLUMNS`, `tile_rect`/`tile_at`/`max_scroll`) | Was the same fixed-`COLUMNS` shape as Home's grid | **Changed by this proposal.** `columns_for_width` makes the column count itself scale with width; no persisted per-column state exists here (unlike Home), so this was safe to change without a data-model/drag-logic audit. |
| Drawer/Shade/Settings/Power panel chrome (`render::scene`'s background/border fill) | Fills `(0, panel_y, w, panel_h)` with `w`/`h` = the real configured size | Yes, already — no code change needed once the surface itself is allowed to be whole-output-sized (this proposal's `main.rs` change). |
| Settings row content (`settings_row_y`, row card x-positions) | Fixed pixel offsets from the panel's own top/left, not capped or centered | No. Rows just extend edge-to-edge on a very wide panel instead of centering in a comfortable column. Deferred; see below. |
| Wi-Fi sub-page (`render::paint_wifi`) | `cr.scale(width / 568.0, height / 1232.0)` — draws in 568x1232 design units, then non-uniformly scales; `wifi_ui.rs` hit-testing inverse-maps touch points through the identical scale | Consistently scaled (paint and hit-test agree), but not uniform — a wide/tall configure stretches or squashes the Wi-Fi sub-page's own glyphs. Pre-existing; unaffected by this proposal either way. |
| Whole-surface Wayland configure acceptance (`lib.rs`, `main.rs`) | `configure_preserves_aspect` rejects (previously: pillarboxes) anything outside a 10% band of 568:1232 | **Changed by this proposal**: a whole-output configure is now accepted at its own size regardless of aspect; a non-whole-output configure (the keyboard-squish case) is still rejected exactly as before. |

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

## Rejected/deferred: Home's own grid column count

Considered and rejected for this change: making `home_grid::COLUMNS` a
function of width (`columns_for_width`, mirroring the Drawer's new one) and
threading a `columns` argument through `home_state::HomeLayout`'s
`anchor_at`/`fits_at`/`place`/`would_fit`/`first_fit`/`place_first_fit` and
the roughly dozen `home_screen.rs` call sites that invoke them during a
drag, a merge, a folder open, or a rearrange.

Why this is a different-weight change from the Drawer's: the Drawer has no
persisted state keyed by column count — `tile_rect`/`tile_at`/`max_scroll`
recompute a filtered app list's geometry fresh every call, so changing
`COLUMNS` to a width-dependent value changes nothing about *what* is stored,
only how it is drawn and hit-tested, both from the same live width every
time. Home's grid is the opposite: `home_state::HomeLayout.pages` is a
`Vec<Vec<Option<HomeItem>>>` sized and indexed by `apps_per_page` at
*placement* time, persisted to
`$XDG_STATE_HOME/k230-shell/home.json`, and read back across restarts and
resolution changes (rotating the panel, or moving between the panel and an
HDMI output). A width-dependent column count changes what a saved slot
index *means* — the same stored index resolves to a different row/column
depending on which output the shell happens to be running on at load time
— and every drag/merge/rearrange/folder code path in `home_screen.rs`
would need to agree, consistently, on which width's column count applies to
a given operation. That is real design work (does a saved layout "reflow"
its existing icons into new column positions when the output changes, or
only lay out *newly placed* icons at the new count; what happens to an
open folder or an in-flight drag when the output resizes mid-gesture), not
a mechanical parameter thread, and it cannot be verified against real touch
input without the board. Left as an explicit follow-up rather than
implemented unverified.

In the meantime, Home does not look broken on a wide output — the wallpaper
and dock/panel chrome fill the whole surface, and the existing 4 columns
just get wider tiles with more breathing room (`docs/evidence/shell-
responsive/home-1920x1080.png`) — it simply does not yet use the extra
width as *more* icons per row the way the Drawer now does.

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
