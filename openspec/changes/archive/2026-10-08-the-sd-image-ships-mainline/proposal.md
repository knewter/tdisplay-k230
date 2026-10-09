## Why

The board's installed default is now the mainline 7.3.0-rc5 coherent shell
(`docs/evidence/mainline-default-boot/`, `docs/evidence/mainline-sd-throughput/`),
but `nix build .#sdImage` still produces the vendor 6.6 kernel with the older bar
session. A freshly flashed card would not match the board everyone tests on.

## What Changes

- `.#sdImage` is built from `nixosConfigurations.k230-mainline-drm-shell`, with
  that system's mainline kernel and the mainline DRM device tree written as
  `k230-tdisplay.dtb`. Stage 1 and the card layout are unchanged.
- `mkBoardImage` takes the device tree as an optional argument (default: the
  vendor tree), so `sdImage-coherent`, `sdImage-rvv-trial` and the other vendor
  images are unchanged.
- The kernel spec's "does not affect the default system" requirement stops
  promising that `.#sdImage` is independent of the mainline build.

Non-goals: the release tool's `sdImage-coherent` target and published
releases; deleting the vendor images; changing stage 1.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `system/kernel`: the flashable default image ships the mainline kernel; the
  mainline-isolation requirement no longer covers `.#sdImage`.

## Impact

- `flake.nix` (`mkBoardImage`, `sdImage`). The image derivation changes; the
  boot partition (112 MiB) holds the 43 MiB mainline Image and 27 MiB initrd.
- Proving that a freshly flashed card boots needs a flash that erases the
  board's current card. That is an operator-scheduled hardware gate, left open.
