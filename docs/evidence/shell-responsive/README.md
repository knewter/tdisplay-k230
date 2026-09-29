# feat/shell-responsive host render captures

Generated 2026-09-29, regenerated the same day after the density-scale/
Home-grid-reflow/Settings-content-column follow-up, with:

```
cargo run --example render_responsive_evidence -- <out-dir>
```

from `nix/rust-shell-client` at commit history on branch `feat/shell-responsive`
(base `feat/hdmi-pillarbox` @ `4c2eb57c8cc5`, later rebased onto that same
branch's `46a8e37e`), then copied into this directory. The harness is
`nix/rust-shell-client/src/evidence_render.rs`, called from both
`examples/render_responsive_evidence.rs` (produces these PNGs) and
`tests/responsive_pixel_identity.rs` (asserts the `*-568x1232.png` files
below stay byte-for-byte identical to a fresh render on every `cargo test`
— see that test file's own doc for exactly what it does and does not
prove).

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
`home-1920x1080.png` vs `home-568x1232.png`, `settings-1080x1920.png` vs
`settings-1920x1080.png`):

- The drawer reflows from 4 columns at 568px to 14 at 1920px
  (`navigation::columns_for_width`), filling the surface edge to edge with
  same-sized tiles instead of 4 huge, sparse ones.
- **Home's grid now reflows too** (this follow-up's own task 2): 4 columns
  at 568px, up to 14 at 1920px (`home_grid::columns_for_width`, the same
  formula the Drawer uses), via `HomeLayout.columns` and `HomeLayout::
  reflow_to` -- see `home-1920x1080.png`, which shows the 30 synthetic apps
  flowing 14-wide instead of 4 huge, sparse tiles. `home_state.rs`'s own
  `reflow_to_*`/`sync_columns_*` tests prove this never drops, duplicates,
  or reorders a stored item, and round-trips 4→8→4 back to the exact
  original page shape.
- **Settings' body content is now a centered, density-scaled column**
  (task 3): `settings-1920x1080.png`'s "Loading settings" row no longer
  spans the full 1920px width, and `settings-1080x1920.png`'s panel is
  visibly taller (content scaled up by `crate::density_scale`, about
  1.56x) instead of a short stub floating over empty space below it. The
  header strip (`Settings` / `Done` / `Device controls` / `Themes ›`)
  deliberately stays unscaled, at the real screen edges, matching Shade's
  and the Drawer's own chrome.
- Home's wallpaper and drawer/settings chrome fill the whole surface at
  every size with no black pillarbox bars (`feat/hdmi-pillarbox`'s removed
  behavior would have shown a centered 568-aspect column here instead).
- `wallpaper-1080x1920.png` is confirmed by `PIL.Image.getcolors` to be
  exactly one RGB value across all 2,073,600 pixels — a uniform full-bleed
  fill, not a partial or letterboxed one.
- `home-568x1232.png`, `drawer-568x1232.png`, `settings-568x1232.png`, and
  `wallpaper-568x1232.png` are confirmed byte-for-byte identical to a fresh
  render by `tests/responsive_pixel_identity.rs`, on every `cargo test` —
  not just a one-time visual check at the time this evidence was captured.

## What this does NOT prove

- **No board, no QEMU, no live Wayland compositor.** This never opens a
  Wayland connection, so it says nothing about whether the compositor
  actually offers this client a whole-output configure at these sizes, or
  about `main.rs`'s `is_whole_output`/`lib.rs`'s `configure_preserves_aspect`
  acceptance logic at runtime (that logic is covered by
  `nix/rust-shell-client/src/lib.rs`'s own unit tests instead). Real HDMI
  output, real touch, and real panel behavior remain open, board-gated work
  — see `openspec/changes/the-shell-adapts-to-output-resolution/tasks.md`.
- **Icon/text pixel sizes in Home and the Drawer do not scale up** with
  `crate::density_scale` -- only their *column counts* reflow. A tall,
  dense HDMI output (1080x1920) gets more Home/Drawer columns of the same
  80px-icon tiles this panel always used, not visibly larger icons the way
  Settings' text/rows now do. Deliberately scoped this way (see the
  proposal's design doc); a real icon/text density scale for the grid
  surfaces is a named follow-up.
- Settings' Wi-Fi sub-page (`render::paint_wifi`) and the theme chooser
  still use their own pre-existing, independent, non-uniform `cr.scale`
  and are unaffected by (and excluded from) this follow-up's content
  transform -- see `render.rs::scene`'s Settings arm, which returns before
  reaching the transformed block whenever either sub-page is open.

## Integrated HDMI candidate, 2026-09-29

Branch `integrate/hdmi-touch-responsive`, based on master `c5158fa8`, combines
HDMI driver `848d24c0` and responsive-shell `fdd26105`. The build at
`e0e3b04a` passed:

```sh
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --lib --bin k230-shell-rust
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 4 --out-link result-hdmi-touch-responsive
nix build .#deviceTreeHdmi --max-jobs 1 --cores 4 --out-link result-hdmi-dtb
nix build .#sdImage-coherent --max-jobs 1 --cores 4 --out-link result-hdmi-touch-responsive-image
```

The 401 library and 22 binary tests pass. Both OpenSpec changes validate
strictly. [Artifact inspection](integration-host.json) pins the system,
image and HDMI DTB and verifies the SD layout, kernel, ramdisk and init
selection against that system. The HDMI tree retains the Goodix touchscreen;
the normal image still boots the panel.

**UNVERIFIED:** This combined candidate has not been installed or booted on
the board. The removed resize handshake is a proposed HDMI touch fix, not
physical touch acceptance. Trackpad and mainline-kernel work are separate.
