# Theme chooser parity with Omarchy Quattro's picker: host+QEMU checkpoint

Captured 2026-09-24 against this change's Rust/Python source (branch
`fix/quattro-theme-picker`, base `0fbe79d7`). **Host and headless-QEMU
screenshots only — no board, no real finger, no physical panel.**

## What Omarchy Quattro's picker actually is

"Quattro" is Omarchy's fourth generation (DHH, `github.com/omacom/omarchy`,
MIT). It replaced the old bash/Walker desktop with a single long-running
Quickshell (QML) process and a plugin architecture
(`github.com/omacom/omarchy/tree/quattro/shell/plugins`). The theme picker and
the background picker are the *same* QML component,
[`shell/plugins/image-picker/ImagePicker.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/plugins/image-picker/ImagePicker.qml),
fed a different image directory by two thin bash wrappers,
[`bin/omarchy-theme-switcher`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-theme-switcher)
and
[`bin/omarchy-theme-bg-switcher`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-theme-bg-switcher),
both of which call
[`bin/omarchy-menu-images`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-menu-images)
to build a thumbnail row set and hand it to the QML overlay over Quickshell IPC
(`omarchy-shell image-selector open ...`). Keybindings: theme picker
`Super+Ctrl+Shift+Space`, background picker `Super+Ctrl+Space`
(`omarchy.org/manual/themes`,
[`manual/06-themes.md`](https://github.com/omacom/omarchy/blob/quattro/manual/06-themes.md)).

Read directly from `ImagePicker.qml` at our pinned revision:

- **Layout**: a horizontal "Cover Flow"-style carousel, not a grid or a plain
  list. Off-center items are narrow, skewed parallelograms
  (`sliceWidth: 108`, `sliceHeight: 432`, `skewOffset: 28`, overlapped by
  `sliceSpacing: -30`); the centered/selected item expands to
  `expandedWidth: 768` / `expandedHeight: 475`. Only items within 16 positions
  of the selection render at all, and each thumbnail texture is loaded once
  and then kept resident rather than torn down while scrolling.
- **Imagery**: each visible slice *is* a photo — the theme's own
  `preview.png` (searched in the order `preview.{png,jpg,jpeg,webp,gif,bmp,
  mp4,m4v,mov,webm,mkv,avi}`, then the theme's first background file sorted,
  per `bin/omarchy-theme-switcher`'s `find_preview()`), or a background image
  itself on the background picker.
- **Selection**: browse-then-explicit-confirm. Arrow keys/Tab/Shift+Tab (or a
  tap on a side slice) move the carousel; Enter, or tapping the already-
  centered item, applies; Escape cancels (or first clears an active
  type-to-filter field). The current/selected item gets a thicker,
  accent-colored border (`selectedBorder` vs `unselectedBorder`); non-selected
  items are dimmed by an alpha overlay tied to the theme's own background
  color. An optional name label sits below the carousel; an optional
  type-to-filter text field appears below that.
- **Colors** come from `shell.toml`'s `[image-picker]` section — `scrim`
  (=background) at `scrim-alpha`, `text` (=foreground), `selected-border`
  (=accent), `unselected-border` (=foreground at low alpha). Our renderer
  already reads this exact section (`nix/rust-shell-client/src/render.rs`'s
  `visual_style(theme, "image-picker")` / `theme_brush(..., "image-picker",
  ...)`), so the color-role mapping already lined up before this change; what
  it lacked was the imagery itself.
- No auto-cycling/timer was found at this revision; background switching is
  an explicit action (`bin/omarchy-theme-bg-next` cycles once per invocation,
  matching our existing `--background` selection design).
- No built-in/user badge exists in the picker itself — entries from a cloned
  theme just appear as additional carousel items.

**Pin status**: `nix/handheld-theme-default/default.nix` pins
`omacom/omarchy@28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`. A full clone of that
exact commit confirms `shell/plugins/image-picker/ImagePicker.qml` is already
present there, and `git rev-list --count 28ceaae7..origin/quattro` is `0` —
**our pin already is the current tip of `origin/quattro` (which is
`origin/HEAD`)**, one commit past "Merge quattro and preserve per-theme
wallpaper memory". `v4.0.4` (the latest numbered tag, 2026-09-14) is a
*different*, older-diverged line that also already has `shell/plugins/`. **No
pin bump is recommended or needed for picker parity** — the pinned revision
already carries Quattro's 22-theme set, its `preview.png`/`preview-unlock.png`
convention, and the Quickshell picker this document describes. A bump would
only matter for the newer 24-key semantic palette / `shell.toml` role-override
convention noted upstream, which is out of scope for this picker-visuals
change and affects other in-flight work
(`openspec/changes/the-shell-loads-omarchy-themes/`).

## What we changed to match it, adapted to touch

Our chooser is a **touch-first, portrait (568×1232), scrolling list**, not a
horizontal coverflow carousel — Quickshell/QML and Hyprland-style compositor
tricks are an explicit non-goal, and a swipe-driven vertical list is the
already-established, tested interaction model for this shell (theme rows,
background rows, and everything else in Settings). What we adopted from
Quattro is its **information design**, not its skeuomorphic geometry:

- **Per-theme preview imagery in the list itself.** Previously the theme list
  (`ThemePage::List` in `nix/rust-shell-client/src/render.rs`) was text-only —
  name and "Built in"/"User theme"/"Current theme". It now shows a small
  (64px) rounded thumbnail per row, decoded from the theme's own
  `preview.png` when the theme ships one, or a representative background
  image when it doesn't — exactly Omarchy's own fallback rule, not an
  invented one. New module `nix/rust-shell-client/src/theme_thumbnails.rs`
  (`ThemeThumbnailCache`) does the bounded, cached, off-thread decode;
  `tools/theme_catalog.py`'s `find_preview()` resolves the path upstream-side
  (`preview.png`/`.jpg`/`.jpeg`/`.webp`/`.gif`/`.bmp`, else the first sorted
  still background) and reports it as each `ThemeEntry`'s `preview_path`.
- **Per-background thumbnails in the background list** (Preview page), same
  mechanism, keyed by each background's own opaque id — so the background
  chooser is no longer text-only either.
- **Current-theme mark**: kept the existing highlighted-card + "Current
  theme" label (a persistent list needs a durable marker; Quattro's carousel
  only marks "currently browsing," which doesn't translate to a scrollable
  list), and added a small accent-colored checkmark badge on the thumbnail
  itself so the mark reads at a glance next to the imagery, closer to how a
  bordered/highlighted slice reads in the carousel.
- **Flow preserved as already built and tested**: tap a row to preview
  (stages the generation, no activation), palette swatches plus a big
  screen-crop background preview, tap a background row to re-preview with
  that background selected, explicit Cancel/Apply — this already matches
  Quattro's browse-then-explicit-confirm model (never live-apply-on-touch),
  just with taps and a scrollable list standing in for arrow keys/Tab and a
  carousel.
- **Fixed a real integration bug found while building this evidence**: the
  new `RendererCache::poll_theme_thumbnails()` was only ever invoked from
  inside `draw()`, so a completed background-thread decode had no way to
  mark the running shell's main loop dirty on its own — thumbnails would
  only "pop in" as an accidental side effect of some unrelated redraw
  (a touch, the single wallpaper-preview poll). Added the same
  `poll_theme_thumbnails()` call the main loop already makes for the single
  wallpaper preview (`nix/rust-shell-client/src/main.rs`), so thumbnails
  actually progress on their own.
- Not changed: the palette-swatch row on the Preview page, which Quattro's
  picker doesn't show at all. It predates this change, is genuinely useful
  on a touch device that can't easily launch every themed app just to see its
  colors, and isn't in tension with anything Quattro's picker does — kept as
  a deliberate touch-specific addition, not a deviation to fix.

## Side-by-side

| | Omarchy Quattro (`ImagePicker.qml`) | This handheld chooser |
| --- | --- | --- |
| Invocation | `Super+Ctrl+Shift+Space`, or Omarchy Menu → Style → Theme | Tap the Themes control in Settings |
| Layout | horizontal skewed "Cover Flow" carousel, ~1 expanded + up to 16 visible slices each side | vertical scrolling list, ~11 rows visible at once |
| Per-item imagery | full-bleed photo per slice (`preview.png`, else first background) | 64px rounded thumbnail per row, same source-file rule |
| Current-theme mark | thicker accent border while browsing (not persistent) | highlighted card + "Current theme" label + accent checkmark badge on the thumbnail |
| Selection model | browse (arrow keys/Tab/tap-a-slice) then confirm (Enter/tap-center-again) | tap a row to preview, explicit Cancel/Apply buttons |
| Background choice | separate keybinding, same carousel component fed `backgrounds/` | same Preview page, a second scrollable list of background rows with their own thumbnails |
| Built-in vs user themes | no visual distinction, just more carousel entries | "Built in" / "User theme" caption kept (a deliberate addition; harmless, more legible on a list) |
| Palette swatches | none | kept, useful for glanceable color info without launching an app |
| Filter/search | optional type-to-filter text field | not applicable — a fixed list of 22 built-ins plus a handful of user clones; scroll replaces search |
| Transition/animation | no explicit QML `Behavior`/`Animation` found; likely immediate reposition | immediate repaint on tap; no timed transition either |

Upstream reference screenshots/manual: `omarchy.org/manual/themes`,
`github.com/omacom/omarchy/blob/quattro/manual/06-themes.md` — not committed
here; follow the links above rather than a copy of upstream art.

## Exact commands and artifacts

Cross-built (all reused the already-cached dependency closure; only this
change's own crates recompiled):

```sh
nix build --no-link --print-out-paths --max-jobs 1 --cores 4 \
  .#handheld-shell-rust .#handheld-theme-default .#card-shell
```

- `handheld-shell-rust` → `/nix/store/s203d1l9h8l9xlxfrxp7i7npsxk8qn2j-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`
- `handheld-theme-default` → `/nix/store/rya33fd7vgcgp0vnydzgsrvznzx5pj15-handheld-theme-default-28ceaae7` (all 22 built-ins, each with a real `preview.png`, verified by querying `tools/theme_catalog.py list --json` against this exact package: every entry's `preview_path` resolved)
- `card-shell` → `/nix/store/zk7g16sasa5vkqqfcd70n5kbnn9jzang-k230-card-shell`; its `sway-unwrapped` (not the wrapper) is `/nix/store/wwsspnnab2q0gp47fcqb8qyh0l6w2mkd-sway-unwrapped-riscv64-unknown-linux-gnu-1.12` (`nix-store -qR` on the card-shell output)

`nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`
→ `/nix/store/xcv4xsgrmx5q03j8zgpb54253j0zrx3p-nixos-system-nixos-26.11.20260919.20b1ddd.drv`.

Regression proof, synthetic backend (unchanged mechanism, now with real
decodable fixture art so the thumbnail path is exercised, not just its JSON
plumbing):

```sh
python3 tests/rust_theme_chooser_qemu.py --sway <sway-unwrapped> --rust <k230-shell-rust>
# PASS paired Sway/Rust theme chooser QEMU touch, synthetic backend; no physical touch
```

The five screenshots in this directory are a **separate one-off capture**,
not the committed regression test: the real, installed `tools/theme_catalog.py`
was run inside the same paired headless-Sway/Rust-under-`qemu-riscv64-static`
harness as `tests/rust_theme_chooser_qemu.py`, against the real 22-theme
`handheld-theme-default` package above and the real
`omarchy-theme-tools-28ceaae7` helper package, through a thin logging proxy
(not committed — a one-off tool) standing in for the trusted `k230-theme`
binary. Synthetic touch via Sway's `card_shell test-touch` IPC command; no
physical touch; captured with `grim` against the compositor's own headless
Wayland output.

- [`theme-list.png`](theme-list.png) — Settings → Themes, real 22-theme list,
  every visible row showing its own real preview thumbnail (catppuccin,
  catppuccin-latte, ethereal, everforest, flexoki-light, gruvbox, hackerman,
  kanagawa, last-horizon, lumon, lupine visible without scrolling).
- [`dark-catppuccin-preview.png`](dark-catppuccin-preview.png) — tapped
  `catppuccin` (dark): real palette swatches (`accent`, `background`, `bg`,
  `blue`, `bright_blue`), its 4 real backgrounds listed with thumbnails
  (Totoro, Waves, Blue eye, Omarchy), "Totoro" selected by default.
- [`dark-catppuccin-background-selected.png`](dark-catppuccin-background-selected.png)
  — tapped the "Waves" background row: big screen-crop preview and the
  "Selected background" label both updated to Waves, "Waves" row now marked
  "Selected still".
- [`light-catppuccin-latte-preview.png`](light-catppuccin-latte-preview.png)
  — tapped `catppuccin-latte` (light): real light palette (white
  `background`/`bg`, blue `accent`), its 2 real backgrounds ("Color fade",
  "Omarchy").
- [`light-catppuccin-latte-background-selected.png`](light-catppuccin-latte-background-selected.png)
  — tapped the "Omarchy" background row: big preview and label switch to the
  Omarchy wordmark art, row marked selected.

**Important scope note**: these five captures are all *Preview*, never
*Apply* — no real theme activation ran, so the Settings chrome around the
chooser (top bar, Cancel/Apply buttons, card backgrounds) stays in whatever
theme was already active in this throwaway state root (the pinned Catppuccin
default) throughout, including in the "light" captures. What changes between
dark/light above is each theme's own reported palette and its own background
art — exactly what a person deciding between two themes needs to see — not
the picker's own chrome, since actually relighting the picker chrome would
require a completed two-phase activation against a live appearance receiver,
which this capture deliberately did not exercise (no state mutation, no
wallpaper change, nothing to roll back).

## What still needs the real board

Touch latency/feel, panel color reproduction (the palette swatches and
photographic previews on the actual AMOLED), real-finger row selection and
scroll inertia, and whether 22 thumbnails decoding at chooser-open time is
perceptible on real hardware are all `<!-- UNVERIFIED -->` and reserved for
`openspec/changes/the-shell-loads-omarchy-themes/tasks.md` task group 5's
board trial. This document proves the mechanism and the visual/information
parity with Quattro's picker under QEMU and on the host; it does not claim
either.
