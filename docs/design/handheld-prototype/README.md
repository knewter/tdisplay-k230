# Handheld interaction study

The browser prototype is at `/tdisplay-k230/design/handheld/`. Its reference
screen is 568 × 1232. It studies the proposed gesture model and visual
continuity; it is not installed shell UI or board evidence. App output, CPU
readings, time, notifications, and network state inside the frame are sample
content.

Home is a live-card overview. A bottom-edge upward drag shrinks an app toward
its card. Horizontal drags move through cards; tapping one expands it. Dragging
a card upward closes it, while the Monitor example refuses and settles back.
Another upward drag from the lower part of Home reveals installed apps. A
top-edge downward drag reveals notifications and a Settings mockup. Settings
can return to notifications or Home. The six controls beside the frame replay
these motions for review; pointer gestures work with mouse or touch. There is
no permanent in-frame navigation bar.

The installed-app identities shown here match the offline image catalog:
Foot (Terminal), htop (Monitor), mpv (Video), nano (Editor), nnn (Files), and
the built-in Help. Their presence does not imply that this proposed layout is
installed. The page repeats an app icon in the drawer, card header, expanded
app, and app-specific notification where that identity is known. Editor,
Files, Help, and Settings use original line icons made for this study.

## Icon provenance

The three upstream icons were copied unchanged from the same Nix store
packages available to the shell. Original paths and SHA-256 values:

| Asset | Original path | SHA-256 | Attribution / license record |
| --- | --- | --- | --- |
| `foot.svg` | `/nix/store/spn1xzg7rfnffadkf4r3giv8vawgx2y3-foot-riscv64-unknown-linux-gnu-1.28.0/share/icons/hicolor/scalable/apps/foot.svg` | `afd748355f6feffb2203982abc963d9c503121b8fb394c23dbbcc9ba546e6e04` | SVG metadata credits Lennard Hofmann, sources [FreeSVG human footprints](https://freesvg.org/human-footprints), and declares [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). |
| `htop.svg` | `/nix/store/nyy80gvhfcalcm8g9x3fcx3bgilllj3g-htop-riscv64-unknown-linux-gnu-3.5.3/share/icons/hicolor/scalable/apps/htop.svg` | `91bd25b2d2717993f6989e49bbedcadd0c9583f9b5b58a28f6d2d5e5c5e28703` | Bundled [htop project icon](https://github.com/htop-dev/htop); Nixpkgs package metadata declares GPL-2.0-only. The SVG does not contain an icon-specific license notice. |
| `mpv.svg` | `/nix/store/4sx1s01fbcsjdsqs7c7smyi4ldhxqxm9-mpv-riscv64-unknown-linux-gnu-0.41.0/share/icons/hicolor/scalable/apps/mpv.svg` | `bf6082c81dcc8b8c6351326b53530f461258af9ca71c4642372654eba29c598f` | Bundled [mpv project icon](https://github.com/mpv-player/mpv); [upstream copyright record](https://github.com/mpv-player/mpv/blob/master/Copyright) covers the project under GPLv2+ / LGPLv2.1+ terms depending on build. The SVG metadata does not declare a separate icon license. |

The other four SVGs are original work for this study. No third-party fonts or
image-generation output were added. The page uses the site's existing fonts.

## Verification

From the repository root:

```sh
python3 scripts/build_site.py
python3 site/tests/handheld_design_browser.py
```

The second command uses Python Playwright and `/usr/bin/chromium` to exercise
the built route. It checks icon loading, live pointer movement and release,
pointer cancellation, app return, drawer, shade, Settings, throw/refusal,
close/reopen, repeatability, and mobile overflow. The first command checks the
site's 8 MiB output and 120-second build budgets. No board was used.
