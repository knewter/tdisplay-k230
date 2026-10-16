# Background fit modes: host renders

Evidence class: **host render** (headless Cairo/`image` pixels from the
production placement code). Not a QEMU run, not a native `grim` capture and not
a panel photograph; task 3.2 of
`openspec/changes/the-background-chooser-supports-fill-solid-and-video` stays
open until the same five modes are captured on the board.

Base revision: `0785fc711838` (`master`), candidate: the commit that adds this
directory on branch `bg-fill-solid`.

Sources (pinned built-in themes, `omacom/omarchy` revision
`28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`, as packaged by
`nix/handheld-theme-default`; see `../bundled-backgrounds-host.md`):

| Theme | Mode | Source image | `background` role |
| --- | --- | --- | --- |
| `catppuccin` | dark | `backgrounds/2-waves.webp` (landscape) | `#1e1e2e` |
| `catppuccin-latte` | light | `backgrounds/1-color-fade.webp` (1536x1024) | `#eff1f5` |

Command (from the repository root, host `cargo`, store path of the packaged
default):

```sh
T=/nix/store/1aq21qmfshf527fy6r62h39crfkpi1px-handheld-theme-default-28ceaae7/share/omarchy/themes
cargo run --offline --manifest-path nix/rust-shell-client/Cargo.toml \
  --example render_background_fit_evidence -- \
  docs/evidence/omarchy-themes/background-fit-modes-host \
  dark-catppuccin $T/catppuccin/backgrounds/2-waves.webp '#1e1e2e' \
  light-catppuccin-latte $T/catppuccin-latte/backgrounds/1-color-fade.webp '#eff1f5'
```

Each PNG is 284x616 (the 568x1232 panel at half size, to keep committed bytes
small; the placement is scale-invariant). The harness writes a generation
`report.json` carrying `fit_mode` and the palette's `background`, reads it with
`appearance::generation_wallpaper_fit` (the function the shell uses) and renders
through `BackgroundCache::render`, so the colour and mode come through the real
resolution path.

What each image shows for a landscape source on a portrait canvas:

- `crop`: aspect-preserving cover, centred; the sides are trimmed.
- `fit`: aspect-preserving, whole image visible, black bars above and below
  (the pre-existing letterbox colour).
- `center`: native pixels, centred, no scaling; black outside the source.
- `fill`: stretched to the full canvas, no bars and no crop; the picture is
  distorted (new in this change).
- `solid`: no image at all, the theme's own `background` role (new in this
  change).

Limits: panel colour, gamma and AMOLED appearance are not represented; no
touch interaction, no chooser rendering and no helper round trip is exercised
here. The chooser control (tapping the "Backgrounds" heading) is covered by
`theme_ui` unit tests only.
