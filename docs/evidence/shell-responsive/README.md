# feat/shell-responsive host render captures

Generated 2026-09-29 with:

```
cargo run --example render_responsive_evidence -- <out-dir>
```

from `nix/rust-shell-client` at commit history on branch `feat/shell-responsive`
(base `feat/hdmi-pillarbox` @ `4c2eb57c8cc5`), then copied into this directory.
The harness is `nix/rust-shell-client/examples/render_responsive_evidence.rs`.

## What this proves

Each of `home-*.png`, `drawer-*.png`, `settings-*.png`, `wallpaper-*.png` is
rendered through the exact production paint path (`render::paint_home`,
`render::export_png` → `scene()`/`paint_drawer`, `render::RendererCache::
draw_wallpaper`) at four surface sizes:

- `568x1232` — the native panel; must read identically to before this change.
- `768x1024`, `1080x1920` — rotated-portrait HDMI sizes.
- `1920x1080` — landscape HDMI.

`home-*` and `drawer-*` use 30 synthetic apps (`evidence.appN.desktop`, no
real icon) placed by `HomeLayout::place_first_fit`/`DrawerNavigation`'s own
tile math — enough to overflow one page/viewport and show real reflow, not
just an empty grid. `settings-*` uses `Route::Settings` with no live service
snapshot (hence the static "Loading settings" row). `wallpaper-*` has no
theme loaded, so it is `render::RendererCache::draw_wallpaper`'s flat
`palette_rgb_or` fallback fill (`0x1e1e2e`), not a decoded image — this
directory does not carry evidence for `background_decode.rs`'s image
crop/center/fit paths, which are unit-tested directly in
`nix/rust-shell-client/tests/background_decode_module.rs` instead (including
the widened `MAX_OUTPUT_WIDTH`/`MAX_OUTPUT_PIXELS` bounds this change adds).

Confirmed by inspection (`drawer-568x1232.png` vs `drawer-1920x1080.png`,
`home-1920x1080.png` vs `home-568x1232.png`, `settings-1920x1080.png`):

- The drawer reflows from 4 columns at 568px to 14 at 1920px
  (`navigation::columns_for_width`), filling the surface edge to edge with
  same-sized tiles instead of 4 huge, sparse ones.
- Home's wallpaper and drawer/settings chrome fill the whole surface at
  every size with no black pillarbox bars (`feat/hdmi-pillarbox`'s removed
  behavior would have shown a centered 568-aspect column here instead).
- `wallpaper-1080x1920.png` is confirmed by `PIL.Image.getcolors` to be
  exactly one RGB value across all 2,073,600 pixels — a uniform full-bleed
  fill, not a partial or letterboxed one.

## What this does NOT prove

- **No board, no QEMU, no live Wayland compositor.** This never opens a
  Wayland connection, so it says nothing about whether the compositor
  actually offers this client a whole-output configure at these sizes, or
  about `main.rs`'s `is_whole_output`/`lib.rs`'s `configure_preserves_aspect`
  acceptance logic at runtime (that logic is covered by
  `nix/rust-shell-client/src/lib.rs`'s own unit tests instead). Real HDMI
  output, real touch, and real panel behavior remain open, board-gated work
  — see `openspec/changes/the-shell-adapts-to-output-resolution/tasks.md`.
- **Home's grid column count does not reflow** in these captures (still 4
  columns, same as `568x1232`, just wider tiles/gaps at `1920x1080`) — a
  deliberate scope boundary for this change; see the proposal's design doc
  for why (persisted per-page layout data, drag/rearrange/merge logic all
  key off a fixed column count today).
- Settings' inner content (rows, "Themes" link) is not yet width-capped or
  centered at `1920x1080`; only the chrome (background/border) fills
  correctly. Also an explicit open follow-up.
