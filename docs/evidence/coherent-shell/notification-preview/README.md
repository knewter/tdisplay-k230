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

## Board (2026-10-14, **board-read**, native `grim`)

First board, landscape profile, system
`kwd0jxwwwmc5rsszqz4z4v02hwhsgy97-nixos-system-nixos-26.11.20260919.20b1ddd`.
With the terminal focused, as root:
`runuser -u shell -- k230-notifications emit --summary "Banner test" --tag t3`
(an unknown sender), then `grim` 1.5 s later:
`board-banner-over-terminal-grim.png` shows the generic "New notification"
banner over the terminal. The shell-ui journal logged
`notification-banner-map-request`, `configure 544x64`, `commit`, and
`unmap` 4.5 s later.

The first board image drew nothing: the banner's 64 px height failed the
full-panel size check in `lib::frame_bytes`, so configure and draw bailed out
after `map-request`. The banner now has its own bound.

Limits: no tap on glass (tap-to-shade is unit-tested only), no camera frame,
the banner is 544 px wide in landscape (the portrait width) rather than the
640 px the host render used, and an unknown sender such as the keyboard-base
screenshot helper only ever shows "New notification".
