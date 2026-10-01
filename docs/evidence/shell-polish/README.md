# Authored-theme shell polish: host review

These are **host Cairo/Pango renders**, not board captures, QEMU observations or real-glass proof. The same production `paint_home`, `RendererCache::draw`, asynchronous theme thumbnails and `BackgroundCache::render` paths paint them. Service text and the curated app catalog are nonsecret fixtures; icons, appearances, backgrounds and preview images are real pinned Omarchy inputs.

The [before images](before/) use production `render.rs` from `0ac61703c4423f50cf85d7691817bccc43d8d3de`, temporarily substituted in this change's own worktree while running the identical example. The [after images](after/) use this commit's renderer. Each pair has the same 568×1232 geometry, theme generation, wallpaper and service data. Clock time naturally differs between runs. The real physical problem was reviewed in [Home](../mainline-display/physical-2026-10-01/final-runtime-home.jpg) and [theme picker](../theme-picker/row-repaint/preflight.png).

Visible changes: Home artwork has no routine plate around each app; the dock has one quiet surface. Settings and notifications have filled rows without repeated border outlines, smaller titles, restrained label color and value text without repeated control names. The drawer retains every background/search brush stop and authored alpha, with a compact search glyph. Theme previews retain their skewed layout and hit targets with rounded clipping and a small centered selection cue.

The compositor overview remains a distinct renderer. Its [existing native capture](../home-screen/navigation/overview.png) records the established real layout and app content. The narrow compositor change removes unselected plate rims and uses authored selected text for the selected 1.5-pixel rim. No card geometry, live-source handling, damage scheduling, focus or input behavior changed. A fresh compositor/board capture is required before claiming an after observation for live cards.

## Reproduce

Use the existing native Cargo development environment with Cairo, Pango, librsvg, glib and xkbcommon; the proof used the repo's pinned buildPackages from flake revision `b57ba41ccf6755c54039fc85b0a54145001b186a` with two host build jobs and a private copied Cargo target. Icon input was `/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share` via `XDG_DATA_DIRS`. `K230_THEME_THUMBNAIL_SEED` may point at the pinned theme package's `share/omarchy/thumbs-by-hash`; missing seed data is decoded by the same worker. The example fails if its admitted thumbnails do not resolve within 45 seconds.

```sh
PROOF_STATE_ROOT=/path/to/proof-state
python3 tools/theme_activate.py catppuccin --prepare-only \
  --state-root $PROOF_STATE_ROOT \
  --builtins /nix/store/9c1i2zfliab82a80iv87929qkngn1ca0-handheld-theme-default-28ceaae7/share/omarchy/themes \
  --background backgrounds/2-waves.webp
python3 tools/theme_activate.py catppuccin-latte --prepare-only \
  --state-root $PROOF_STATE_ROOT \
  --builtins /nix/store/9c1i2zfliab82a80iv87929qkngn1ca0-handheld-theme-default-28ceaae7/share/omarchy/themes \
  --background backgrounds/1-color-fade.webp
cargo run --offline --manifest-path nix/rust-shell-client/Cargo.toml \
  --example render_polish_evidence -- OUT DARK-GENERATION LIGHT-GENERATION
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --test responsive_pixel_identity
python3 tests/test_card_shell_appearance.py
python3 tests/test_card_rounded_clip.py
```

The preparation commands only stage host files; they perform no activation. Appearance snapshots are read through the production bounded validator. Native Home/drawer/Settings pixel goldens in `docs/evidence/shell-responsive/` were deliberately refreshed for the new visual output; the existing pixel-identity regression itself is unchanged.

## Proof and limits

Host library: 415 passed, 1 ignored. Two added checks assert that a two-stop translucent drawer brush preserves both its alpha and its gradient and that a theme's explicit zero control tint is honored. Pixel identity: all four expected native snapshots match the reviewed new goldens. Card appearance socket suite: 10 passed. Rounded live-buffer clip oracle: 288 comparisons passed. These establish software behavior and paint geometry only.

An additional existing `python3 tests/test_card_shell_deck_title.py` invocation failed because its extracted fixture leaves `desktop_identity_icon` unused under `-Werror=unused-function`. The title/identity helper is untouched here; the unrelated fixture was not repaired as part of the visual pass.

The [exact coherent-configuration client and compositor cross-builds](cross-build.md) passed. Paired compositor installation and **real-glass dark/light readability, gestures and mouse review remain UNVERIFIED** until the coordinator commits their named proof. Task 6.4 stays open. No board, serial port or runtime secret configuration was accessed by this worker.

Host evidence generated 2026-10-01T17:49:21.727965+00:00 UTC.

Source/input hashes:

- `nix/rust-shell-client/src/render.rs`: `20d78fb1872454bdf562fde696ffba4848a34b8d49a4c7566e7112d2d4c36b65`
- `nix/card-shell/adapter.c`: `78bd8145c7a6a3676b770c03fca2d47c13cfc02e7ef511579f97fc9ead91e768`
- `nix/rust-shell-client/examples/render_polish_evidence.rs`: `233158892b9f946f8ae6fb647460ea3a56d24795219e773cf4e974e1c15fe445`
- dark: `6ae3582938d6ab4285d9e32d`, source SHA256 `72e8f8f39a1209893b30b651fece6c1d1ce47ec643df9e596c7cd282ea97d4c6`, selected `backgrounds/2-waves.webp`.
- light: `bc67f39ac422947f52040a19`, source SHA256 `11ea23e5a4659b09ecda0658dd86921489d6f536b86ffa60af2f601912a70cdc`, selected `backgrounds/1-color-fade.webp`.
