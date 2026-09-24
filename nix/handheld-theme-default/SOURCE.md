# Pinned Omarchy built-in themes

The Nix source is the immutable `omacom/omarchy` revision
`28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`, fetched by
`fetchFromGitHub` with fixed-output hash
`sha256-wxvTIkTGJCwQI65KxAErhXhTrnpbWgIvNfDLG4pfJKs=`. `ls themes/` against
that fetched source lists 22 members, every one with a `colors.toml`
palette; the package installs all 22 as built-ins, matching
`ALL_BUILTIN_THEMES` in `tests/test_handheld_theme_bundle.py`:
`catppuccin`, `catppuccin-latte`, `ethereal`, `everforest`, `flexoki-light`,
`gruvbox`, `hackerman`, `kanagawa`, `last-horizon`, `lumon`, `lupine`,
`matte-black`, `miasma`, `nord`, `osaka-jade`, `retro-82`, `ristretto`,
`rose-pine`, `solitude`, `tokyo-night`, `vantablack`, `white`.

`catppuccin` and `catppuccin-latte` are copied unchanged, byte for byte,
including their original static backgrounds and preview assets. Their 20
file hashes are in `source-inventory.json`; their framed tree digests are
`72e8f8f39a1209893b30b651fece6c1d1ce47ec643df9e596c7cd282ea97d4c6` and
`11ea23e5a4659b09ecda0658dd86921489d6f536b86ffa60af2f601912a70cdc`. Their
bundled/default generation identities are pinned to these exact bytes.

The other 20 built-ins are copied unchanged **except** for their
`backgrounds/` images. Upstream background art runs up to 7680x3215px and
sums to 66.4MB raw across all 22 themes (53MB of that is backgrounds alone);
this device is a 568x1232 portrait AMOLED panel with limited storage, the
downloadable image is required to stay compact (`openspec/specs/image/sd-layout/spec.md`),
and the runtime decoder already crops every background to exact output size
on every decode (`nix/rust-shell-client/src/background_decode.rs`), so
shipping full-resolution source pixels for 20 more themes buys nothing but
closure weight. `default.nix` runs each bounded theme's `backgrounds/*.{jpg,jpeg,png,webp}`
through `imagemagick mogrify -resize 'x1250>' -quality 82 -strip` at build
time: every one of the 92 upstream background images is landscape or
square (verified 2026-09-24), so capping *height* (not width) is correct
for all of them — a landscape source scaled to cover a portrait 568x1232
crop is height-constrained, and 1250px keeps a small margin over the
panel's 1232px long edge so the crop never has to upscale. Colors,
aliases, icon selectors, preview art and every non-background file in
those 20 themes stay byte-identical to the pinned upstream checkout; only
the background *pixels* are a build-time derivative, at their original
relative path and filename, so `theme_catalog.py`/`theme_activate.py` need
no change to discover, hash, stage or select them.

Measured impact (`nix build .#handheld-theme-default`,
`nix path-info -S`, 2026-09-24): the package closure is a single
self-contained store path (nothing else is referenced) at 28.7MB with all
22 themes bounded, versus a measured 66.4MB if all 22 shipped unresized —
a 58% reduction for 11x the theme count of the previous 2-theme, 1.5MB
package. `tests/test_handheld_theme_bundle.py`'s
`check_all_builtins_resolve` proves every one of the 22 still parses and
resolves through the real `theme_activate.prepare()` path, and that every
bounded background stays at or under 1300px tall in the installed package.
The upstream repository `LICENSE` is included in the package (MIT).

The fresh-home default is a derived Catppuccin generation with the original
`backgrounds/2-waves.webp` selected. Its `report.json` and `appearance.json`
are committed as `bundled-*.json`. The 24-character generation identity is the
first 24 hex digits of SHA-256 over sorted JSON containing the prior palette
generation ID, pinned source revision and framed tree digest, selected
background path, and format version 1. This identity describes our bundled
default; later `k230-theme` activation uses its own coordinator identity.

The previous palette-only generation remains in the package as a recovery
default. Its `default-*.json`, pinned `colors.toml`, `icons.theme`, and terminal
fragments remain available. The new default does not imply video playback,
full background previews, or device performance proof.
