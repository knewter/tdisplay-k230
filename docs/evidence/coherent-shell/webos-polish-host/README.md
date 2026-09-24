# webOS polish review: host renderer captures, after the fix

Native **host renderer** PNGs at 568×1232, captured 2026-09-24, source commit
`88736600` (the Rust half of the `docs/design/webos-polish-review.md` fixes),
using the same fixture and pinned theme generations as
[`../rust-visual-themes-host/README.md`](../rust-visual-themes-host/README.md)
("before" captures for the same screens). This is a host cargo test
fixture: it exercises the real render code but not a cross-built package, a
board, or a compositor.

```sh
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share \
  K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-catppuccin/generations/cd73257753c4a1a64fa092b3 \
  K230_VISUAL_FIXTURE_DIR=<dark output dir> K230_VISUAL_REQUIRE_ICONS=1 \
  cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline -q \
  themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share \
  K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-latte/generations/c55da9f13ae1265e4ff18435 \
  K230_VISUAL_FIXTURE_DIR=<latte output dir> K230_VISUAL_REQUIRE_ICONS=1 \
  cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline -q \
  themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles
```

Both runs passed (1 test each; full suite separately: 68 passed, 0 failed).

## What changed versus the "before" captures

- **settings.png** (P0-2, P0-4): the four capability rows now sit on an even
  110px-row/16px-gap rhythm instead of three different hand-typed gaps, and
  the panel is sized to the actual Power-section content instead of filling
  the full 1232px height; the freed area below is a dimmed scrim (renders
  as mid-gray here because this fixture composites over a plain background,
  not a live card -- in the compositor it dims whatever is behind the panel).
- **themes.png**: the Themes list panel likewise ends just below its two
  rows instead of filling the screen.
- **shade.png**: the notification count reads "1 notification" (singular),
  not "1 notifications"; the below-cap area gets the same dim scrim.
- **preview.png**: the Apply/Cancel footer floats up to sit just below the
  single background row instead of leaving a large gap above a
  screen-bottom-pinned footer. (The no-image hatch fallback for finding
  P1-3 is not visible in this specific fixture, since the real Totoro still
  decodes; it is confirmed instead in
  [`../../omarchy-themes/theme-preview-host/`](../../omarchy-themes/theme-preview-host/README.md)-style
  fixtures via source reading and the paired QEMU capture below.)
- **drawer.png**: unchanged in layout (out of this review's P0-2 scope); the
  "YOUR DEVICE" eyebrow label and the "Swipe down to return to cards" footer
  hint now use the medium-weight tier and unified sentence-case typography
  (P1-1, P1-2).

Both the dark (Catppuccin) and light (Catppuccin Latte) captures show the
same behavior with correct theme colors, confirming the fix is
theme-token-driven rather than hardcoded to one palette.

Cross-built package, installed board pixels, wallpaper composition, motion
quality, real touch, and optical contrast are separate open gates, same as
the "before" evidence this supersedes for these five screens.
