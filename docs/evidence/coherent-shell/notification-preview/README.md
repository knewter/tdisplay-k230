# Notification preview banner: host renders

Evidence class: **host render only**. These PNGs are produced by
`cargo run --offline --example render_notification_banner_evidence -- <dir>`
(`nix/rust-shell-client/examples/render_notification_banner_evidence.rs`),
which paints the banner through `RendererCache::draw_notification_banner`, the
same function the live client uses, and composites it at the layer-surface
position (`notification_banner::banner_geometry`) over a rendered Home screen
with synthetic apps.

Files: `banner-{trusted,unknown}-{568x1232,1232x568}.png`.

- `trusted`: a preview with source "Terminal" and a real summary.
- `unknown`: the generic fields the broker (`tools/notification_center.py`,
  `snapshot()`) substitutes for a private or unknown sender ("Notification",
  "New notification", no icon). The banner shows exactly the fields of the
  broker's `preview` object and never reads history rows.

Limits: no Wayland connection, compositor stacking, touch, keyboard focus,
5 s expiry or glass was exercised. The background is Home, not a focused app;
over-an-app stacking (`Layer::Overlay`, `KeyboardInteractivity::None`)
is UNVERIFIED until a native `grim` capture on the board while the terminal is
focused, e.g. after a keyboard-base screenshot that emits "Screenshot saved".
