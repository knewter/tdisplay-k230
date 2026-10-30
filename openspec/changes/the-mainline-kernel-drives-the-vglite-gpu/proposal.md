## Why

The handheld cannot use its 2D GPU at all on the kernel it boots today. The board has booted mainline Linux 7.3 by default since 2026-10-08, and on that system `/dev/vg_lite` does not exist, the device tree has no GPU node and no GPU driver is built (read-only board observations, [`docs/evidence/vglite-mainline-blocker/README.md`](../../../docs/evidence/vglite-mainline-blocker/README.md)). Every GPU result recorded so far was taken on the earlier vendor kernel, so the open question of whether VG-Lite reduces real shell rendering cost (`the-shell-trials-vglite-composition`) cannot even be asked of the current system.

**User decision, 2026-10-30:** "we have to get a gpu node back in the mainline kernel ... that's the most important thing, we should have the gpu in the kernel." The GPU driver and its device-tree node are therefore a requirement on the mainline system in their own right, ahead of any further renderer work.

## What Changes

- Port the vendor `drivers/gpu/vglite` driver (about 2,500 lines, `gc8000ul` platform driver exposing `/dev/vg_lite`) to the pinned mainline 7.3 tree, built as an out-of-tree module against the exact kernel the board already boots, using the repo's existing `boot.extraModulePackages` pattern.
- Add a `gpu@90800000` node to the mainline display device tree using the mainline K230 clock (`K230_DISPLAY_GPU_GATE`), reset (`RST_GPU`) and the carried DISP power domain.
- Provide a bounded way to try the driver on the running board without a reboot or `/boot` change, and a DTB-only install route for the permanent node.
- Keep the opt-in `shell-compositor-vglite` renderer working against the new device; the default shell stays on Pixman.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/kernel`: the mainline system exposes the VG-Lite GPU as `/dev/vg_lite`.

## Impact

Touches the Nix kernel-module list of the mainline shell system, one device-tree include and a vendor-derived driver source set. Needs the physical board for the probe, smoke test and regression gates; the kernel, DTB and module builds are host work. The existing kernel Image is unchanged, so rollback of a DTB-only install is the previous DTB.

Non-goals: changing the default renderer, claiming any rendering speedup, an upstreamable DRM (etnaviv-style) driver, GPU access for ordinary clients (the access broker of `the-shell-trials-vglite-composition` still applies), the NPU or video blocks.
