# Omarchy drawer and card generation proof

Captured 2026-10-02 at 06:57 UTC. This closes the task's host rendering and
consumer checks; it does not claim physical panel or real-finger acceptance.

`dark-drawer-host.png` and `light-drawer-host.png` are the production Rust
`RendererCache`/Cairo drawer rendered from immutable Catppuccin and
Catppuccin-Latte generations prepared from the pinned `handheld-theme-default`
bundle (Omarchy revision `28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`). Their
reports select Yaru-purple and Yaru-blue respectively. The test requires the
real installed icon root, at least two successful icon decodes, a clear live
area, and launcher panel alpha matching the source generation. App names and
service values in this fixture are synthetic; only the selected theme assets,
appearance payload and production renderer are real.

`dark-card-qemu.png`, `light-card-qemu.png` and `light-drawer-qemu.png` are
headless QEMU Sway/Rust compositor captures from the paired appearance runtime
test. The dark card uses the pinned bundle's Catppuccin generation; the light
card and drawer use a freshly prepared Latte generation. The test checked
source-image pixel samples, both appearance endpoints, rollback after an
injected second-endpoint commit failure, and persistence across a Rust restart.
Its client/card data are public fixtures. These are QEMU composition captures,
not board scanout or a finger test. The Rust/Sway executables were the already
installed candidate in Nix store paths listed below, rather than a fresh build
from this evidence worktree; their exact hashes make that limit reviewable.

The native card appearance receiver test now carries `report.json`'s selected
`icon_theme` into its validated callback (`Yaru-blue` on the candidate,
fallback `-` when absent). A host probe compiles the production card icon
resolver and verifies both a theme-local SVG and an inherited SVG, then switches
themes and observes the new local asset. Rust's existing production resolver
test separately verifies inherited SVG lookup, cache hits, cache clearing on
theme change, and re-decode. The drawer-grid regression now confirms a changed
appearance generation rebuilds the cached grid even when app list, width and
query are unchanged.

Reproduce the host drawer captures and all named consumer checks from the repo
root (with the same pinned Nix store bundle available):

```sh
cap="$HOME/tmp/k230-theme-drawer-card-review"
bundle=/nix/store/9c1i2zfliab82a80iv87929qkngn1ca0-handheld-theme-default-28ceaae7
icons=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3
for theme in catppuccin catppuccin-latte; do
  python3 tools/theme_activate.py "$theme" \
    --source "$bundle/share/omarchy/themes/$theme" \
    --state-root "$cap/$theme-state" --user-themes "$cap/empty-user-themes" \
    --tools nix/omarchy-theme-tools/upstream --prepare-only
done
dark=$(find "$cap/catppuccin-state/generations" -mindepth 1 -maxdepth 1 -type d)
light=$(find "$cap/catppuccin-latte-state/generations" -mindepth 1 -maxdepth 1 -type d)
export TMPDIR="$HOME/tmp"
export CARGO_TARGET_DIR="$HOME/tmp/k230-theme-drawer-card-cargo-target"
export XDG_DATA_DIRS="$icons/share"
export K230_THEME_CAPTURE_DIR="$cap/captures"
export K230_THEME_DARK_GENERATION="$dark"
export K230_THEME_LIGHT_GENERATION="$light"
python3 tests/test_handheld_theme_rendering.py --surface drawer-card
```

The paired card captures were reproduced with:

```sh
python3 tests/test_real_theme_paired_runtime.py \
  --sway /nix/store/g7xzwwvr3x05mlmsab5jn5kn1sl41wjb-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/3hy6h165ii649z6vjzjd36jwg16d37rc-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/yjb89ap4bq5vb29szdzkr5sv9lpw1sz6-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --theme-bundle "$bundle" --icons "$icons" \
  --output "$HOME/tmp/theme-qemu-3-2" --check-restart
```

The probe client derivation was obtained and built with:

```sh
probe_drv=$(nix eval --impure --raw --expr 'let f = builtins.getFlake (toString ./.); p = import f.inputs.nixpkgs { system = "x86_64-linux"; }; in (p.callPackage (f.outPath + "/nix/card-composition-probe-client") {}).drvPath')
nix build --no-link --max-jobs 1 --cores 8 --print-out-paths "${probe_drv}^out"
```

This evaluated to derivation
`/nix/store/67c3mixvlwazmzxr3zjj9g8llrv8fcq1-card-composition-probe-client-0.1.drv`
and output
`/nix/store/yjb89ap4bq5vb29szdzkr5sv9lpw1sz6-card-composition-probe-client-0.1`.
The installed QEMU Rust executable is the earlier candidate from application
source revision `5bb67db128210f830dab4de0d20a4b0eca13c578`, not a build of this
checkout.

Source SHA-256 values at review time:

| Source path | SHA-256 |
| --- | --- |
| `nix/rust-shell-client/src/render.rs` | `bb9c97654658aaec7d440d57f0a3771923880e0b646383f66bda10e556f34780` |
| `nix/card-shell/appearance.c` | `35284642fe33cd9e8c201446026b0b78bb9a53ee51f254fd76ebf565ee3f2cf4` |
| `nix/card-shell/adapter.c` | `78bd8145c7a6a3676b770c03fca2d47c13cfc02e7ef511579f97fc9ead91e768` |
| `nix/card-shell/icon.c` | `4dd4ef3eb901d8254991bf04b90c2d4b2f1ab0d27f53fa7790b90572c049719c` |

Executable SHA-256 values:

| Nix-store executable | SHA-256 |
| --- | --- |
| `/nix/store/g7xzwwvr3x05mlmsab5jn5kn1sl41wjb-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway` | `3e12de25c17e22b02954466872a30cf7c11536801f53f5566d0cdf416acb7ebf` |
| `/nix/store/3hy6h165ii649z6vjzjd36jwg16d37rc-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust` | `e89ac92798d3ca2ad7286afd66cdccb68513dc40b64961ae2a2d0c0592d9d900` |
| `/nix/store/yjb89ap4bq5vb29szdzkr5sv9lpw1sz6-card-composition-probe-client-0.1/bin/card-composition-probe-client` | `1933c7fefe0bc6173bab2a88393abba3409a61259fc5b3afa14ebc20ffc93ec6` |

All PNGs are original production renderer or compositor outputs and were
visually reviewed. Their SHA-256 values are recorded in `docs/blob-inventory.md`.
