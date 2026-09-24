# Pinned Catppuccin to Latte: paired QEMU appearance proof

Run at 2026-09-24 06:59 UTC with test source `14a2bdc6b18265ddd378a3cc2a6b92a3699c210e`
on base `f4ce4eac050add3e3e4bd44036351bfcc5903588`. This is a headless QEMU
Sway/Rust composition test with a public synthetic live card and temporary
public desktop entries. The PNGs are original compositor captures, visually
reviewed. They contain no private application pixels. This is not a board,
glass, real-finger, latency, or CPU-budget result.

The exact Sway executable was
`/nix/store/ixamm5fj89083y41g55x8p46wfsgbllf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
(SHA256 `63f0ed98d62da4743b792fe46500aeae88948b7e12b0b044be06b6142fbd093c`).
The Rust executable was the realized coherent-image variant
`/nix/store/l8i7g4y9c18gm8l10m7a61cjbpgxvby4-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`
(SHA256 `5baa4a0806a04e16ced25449ae33c14101bfcc6e534a910abc4abcb7de0b16e6`).
The selected real icon root was
`/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3`.
The live card probe was
`/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`.

The immutable default bundle
`/nix/store/aajw0dknkkwx4mdswaa0vd52li64d6i7-handheld-theme-default-28ceaae7`
provided generation `0d16475245f13b3d7d3f036f` and the selected unchanged
`backgrounds/2-waves.webp`. Latte was prepared from that bundle's pinned
`share/omarchy/themes/catppuccin-latte` source (SHA256
`11ea23e5a4659b09ecda0658dd86921489d6f536b86ffa60af2f601912a70cdc`),
using the repository helper/adapter (SHA256
`bc877623871ab06a14cfa86501e4f54fd675d7173df7fe3b6c9553c17f3a1354` /
`685b28e48aa41b537a766ab667e89eed04eb267f8aaa02b25ec1268f3b3d0d86`).
Its prepared generation was `91f5df6022a0e2e7d6bee6a9`, selecting the
actual `backgrounds/1-color-fade.webp` and Yaru-blue.

Reproduce with:

```sh
python3 tests/test_real_theme_paired_runtime.py \
  --sway /nix/store/ixamm5fj89083y41g55x8p46wfsgbllf-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/l8i7g4y9c18gm8l10m7a61cjbpgxvby4-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --theme-bundle /nix/store/aajw0dknkkwx4mdswaa0vd52li64d6i7-handheld-theme-default-28ceaae7 \
  --icons /nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3 \
  --output /tmp/k230-real-theme-paired-qemu-prelim-01 --check-restart
```

The selected default waves image appeared through the live deck at `(10,700)`:
compositor RGB `(165,156,204)` equaled the centered-crop source sample.
After both appearance endpoints acknowledged Latte, its real still appeared at
`(10,300)` and `(10,700)` with RGB `(254,238,221)` and `(241,210,227)`, both
equal to source samples. The drawer adopted the authored Latte launcher brush
and the live app remained visible when expanded over the input-empty
wallpaper. An injected failed second commit restored both endpoints and the
active pointer to Latte; a Rust restart retained the same deck image and
drawer appearance. `result.json` records the measured values and exact paths.

The authored launcher background has alpha 0.95, so `latte-drawer.png` faintly
shows card text through its lower panel. That visible translucency is part of
the source theme and needs panel optical review; this fixture did not change
the theme. Physical appearance, touch routes, scanout, and budgets remain open.
