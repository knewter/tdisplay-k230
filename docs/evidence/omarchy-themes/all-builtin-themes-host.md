# All 22 Omarchy built-in themes, host and package checkpoint

The person reported seeing only three themes (the two bundled built-ins plus
one community clone they added). `ls themes/` against a fresh checkout of the
pinned `omacom/omarchy` revision `28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`
lists 22 members, every one with a `colors.toml` palette:

```
catppuccin catppuccin-latte ethereal everforest flexoki-light gruvbox
hackerman kanagawa last-horizon lumon lupine matte-black miasma nord
osaka-jade retro-82 ristretto rose-pine solitude tokyo-night vantablack white
```

`nix/handheld-theme-default/default.nix` previously installed only the first
two into `$out/share/omarchy/themes` (the `--builtins` directory `k230-theme`/
`omarchy-theme-set` and `tools/theme_catalog.py` read). It now installs all 22.

## Real-resolution-path probe found a genuine parser gap, not a skip

Before touching Nix, every theme was run through the actual
`tools/theme_activate.prepare()` path (the same code `k230-theme`/
`omarchy-theme-set` use) against a plain checkout of the pinned revision:

```sh
python3 - <<'EOF'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, "tools")
import theme_activate as activation
SRC = Path("<checkout>/themes")
for theme_dir in sorted(SRC.iterdir()):
    with tempfile.TemporaryDirectory() as tmp:
        activation.prepare(theme_dir.name, source=theme_dir,
                           state_root=Path(tmp) / "state",
                           user_themes=Path(tmp) / "user", builtins=None,
                           tools=activation.HOST_TOOLS)
EOF
```

19 of 22 resolved cleanly. Three did not: `hackerman`, `last-horizon`,
`solitude` all failed in `theme_tokens.compile_tokens` with
`invalid color: rgba(26a269ee)` (or equivalent). Their `colors.toml` sets
`hyprland_active_border`/`hyprland_inactive_border` to a Hyprland-syntax
gradient, e.g. (`themes/hackerman/colors.toml`):

```
hyprland_active_border = "rgba(26a269ee) rgba(2ec27eee) 45deg"
```

`shell.toml.tpl`'s `{{ shell_gradient hyprland_active_border accent }}`
copies that value verbatim into the generated `shell.toml`'s `[hyprland]
active-border`, so `tools/theme_tokens.py`'s `_argb` had to parse Hyprland's
compact `rgba(RRGGBBAA)`/`rgb(RRGGBB)` hex form (alpha trailing, no commas),
which is a different grammar from the CSS decimal `rgba(r, g, b, a)` form it
already handled. The same raw value also reaches
`nix/rust-shell-client/src/appearance.rs`'s `palette_value` through
`report["palette"]["hyprland_active_border"]` (the flat map read by the Rust
appearance receiver); that function already special-cased a *single*
`rgba(RRGGBBAA)` value for these two keys (fixed earlier for a community
theme, see `community-rgba-host.md`) but rejected the *multi-stop* gradient
form these three built-ins actually use.

Both parsers were fixed, not the themes skipped:

- `tools/theme_tokens.py`: added `HEX_RGBA` (`rgba(HEX8)` / `rgb(HEX6)`,
  matched separately so each keeps its own required length) alongside the
  existing CSS-decimal `RGBA` regex.
- `nix/rust-shell-client/src/appearance.rs`: `palette_value`'s
  `hyprland_active_border`/`hyprland_inactive_border` branch now finds the
  first `rgba(...)`/`rgb(...)` token in a (possibly multi-stop) value and
  decodes that as the representative color; the full gradient (every stop
  and the angle) is unaffected and still renders through the resolved
  `shell.toml` brush tokens, which already supported multi-stop gradients.

New tests: `tests/test_handheld_theme_rendering.py::test_hyprland_hex_gradient_and_bare_rgb_are_distinct_from_css_decimal_form`
and `nix/rust-shell-client/tests/appearance_module.rs::builtin_multi_stop_hyprland_gradient_palette_uses_first_stop_color`
(the latter using hackerman's/solitude's exact strings). Both keep the
existing CSS-decimal and single-hex-form cases passing and keep rejecting
the same spelling on unrelated keys (`background`, etc.).

Re-running the probe after the fix: all 22 themes resolve.

## Background size measurement and mitigation

Upstream backgrounds run up to 7680x3215px (`themes/tokyo-night/backgrounds/*`)
and 3840x2160/4K is common; raw size across all 22 themes' `themes/` trees is
66.4MB, of which 53MB is `backgrounds/` (92 image files, `du -sb` on the
fetched checkout). The panel is a 568x1232 portrait AMOLED with limited
storage, and `openspec/specs/image/sd-layout/spec.md` requires the
downloadable image stay compact. The runtime background decoder
(`nix/rust-shell-client/src/background_decode.rs`) already crops every
background to exact output size on every decode (`BackgroundCache::render`),
so shipping full-resolution source pixels for 20 more themes buys nothing but
closure/rootfs weight, matching design decision 6 in this change's
`design.md` ("lazy-generate bounded previews, decode static images once at
output size").

Checked what "unchanged theme checkout is a usable source" actually
requires first (`specs/runtime/shell-themes/spec.md`): its scenarios are
about a *selected* checkout not being mutated at use time ("leaves its
tracked and untracked source files unchanged"), and the design explicitly
plans "derived generations" and bounded background previews as build-time/
runtime artifacts separate from the source. Nothing in the spec requires our
own Nix-packaged built-in copy to mirror upstream pixel-for-pixel at full
resolution; it requires that the theme *source a person points at* (a
community clone, or one of these built-ins once installed) is not edited as
a side effect of using it. **No spec change was made or is needed** for this
slice: only background *pixels* are a build-time derivative, staged at the
same relative path/filename; palette, icon selector, preview art and every
other file stay byte-identical to the pinned upstream checkout.

`catppuccin`/`catppuccin-latte` are left untouched (still full upstream
resolution) because their bytes are pinned into this package's `bundled-
report.json`/`bundled-appearance.json`/`default-report.json` generation
identities; regenerating those was out of scope for this slice and the two
themes are a small fraction (1.5MB) of the total. The other 20 built-ins'
`backgrounds/*.{jpg,jpeg,png,webp}` are resized in `default.nix`'s
`installPhase` with:

```sh
magick mogrify -auto-orient -resize 'x1250>' -quality 82 -strip <files>
```

Every one of the 92 upstream background images is landscape or square
(checked with `identify -format '%w %h %f\n'` over the whole fetched
checkout, 2026-09-24: zero images have height > width). A crop-to-cover onto
the portrait 568x1232 panel is therefore height-constrained for all of them,
so capping *height* (not width, and not both) is the correct bound — it
cannot cause an upscale on any of the 92 images at output size, only a
downscale for oversized ones. 1250px keeps a small margin over the panel's
1232px long edge.

## Measured result

```sh
nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#handheld-theme-default
# /nix/store/rya33fd7vgcgp0vnydzgsrvznzx5pj15-handheld-theme-default-28ceaae7
nix path-info -S /nix/store/rya33fd7vgcgp0vnydzgsrvznzx5pj15-handheld-theme-default-28ceaae7
# 29737592  (28.7MB; a single self-contained store path -- nothing else is
# in this package's runtime closure)
python3 tests/test_handheld_theme_bundle.py --package /nix/store/rya33fd7vgcgp0vnydzgsrvznzx5pj15-handheld-theme-default-28ceaae7
# PASS: 20 unchanged source files, two generations, selected backgrounds/2-waves.webp
# PASS: all 22 built-ins resolve and stage through theme_activate.prepare(); bounded backgrounds stay <= 1300px tall
```

| | Size |
| --- | --- |
| Raw upstream `themes/` (all 22, unresized) | 66.4MB (53MB backgrounds) |
| Shipped package (22 themes, 20 bounded) | 28.7MB closure |
| Estimated if all 22 shipped unresized | ~66-67MB closure |

A 58% reduction versus shipping all 22 unresized, for 11x the theme count of
the previous 2-theme, ~1.5MB package. `catppuccin`'s/`catppuccin-latte`'s
installed bytes were verified unchanged (`hashlib.sha256` over every
installed file matches the pre-existing `source-inventory.json`); every
built-in's whole-directory content digest (`theme_sources.source_digest`,
including the 20 post-resize trees) is recorded in the same file for future
verification.

`nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#handheld-theme-command .#handheld-shell-rust`
and `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`
were also run and succeeded (2026-09-24); see the handoff report for their
exact output paths. `cargo test --offline --locked` in
`nix/rust-shell-client` (58 lib tests + all integration suites, including the
two new/changed tests above) and every `tests/test_handheld_theme_*`,
`tests/test_omarchy_theme_*`, `tests/test_theme_*` host suite pass.

## What remains open

No board or real-panel evidence exists for the 20 newly bundled themes'
readability, background quality on glass, or storage footprint on an actual
flashed card -- that is task group 5's reserved-board gate in this change's
`tasks.md`, unrelated to and not advanced by this host/package slice. A QEMU
capture specific to the newly bundled themes was not produced in this
session (the existing `tests/rust_theme_chooser_qemu.py` already exercises
theme and background selection generically and was not re-run here, since
neither it nor the touch UI it exercises were changed by this slice).
