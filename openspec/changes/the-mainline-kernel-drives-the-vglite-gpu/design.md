## Context

Layers: kernel (driver), device tree, Nix. The vendor tree (`ruyisdk/linux-xuantie-kernel` @ `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`) carries `drivers/gpu/vglite/{vg_lite_hal.c,vg_lite_kernel.c,...}` and a `gpu@90800000` node in `arch/riscv/boot/dts/canaan/k230.dtsi` (compatible `verisilicon,gc8000ul`, IRQ 135, DISP power domain, reset `K230_RESET_V2P5D_*`, clock `disp_gpu`). The platform driver exposes `/dev/vg_lite` through `register_chrdev` and `device_create`; the userspace SDK library opens that node and uses ioctl.

The pinned mainline tree (7.3-rc5) already has what the node needs: `K230_DISPLAY_GPU_GATE` (136) and `K230_DISPLAY_GPU_RATE` (184) in `include/dt-bindings/clock/canaan,k230-clk.h`, and `RST_GPU` (31, register 0x98) in `canaan,k230-rst.h` and `drivers/reset/reset-k230.c`. The DISP power domain comes from `nix/patches/mainline/k230-power-domains.c`, carried for the DRM port. The running board's device tree exposes the symbols `sysclk`, `rst`, `sysctl_power` and `plic`. The running kernel (`/nix/store/21lz5c6pkk329c0xcac9bzlx40dplrlk-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`) has `OF_OVERLAY=y`, `MODVERSIONS` unset, `RISCV_DMA_NONCOHERENT` with the T-Head CMO and MAE errata, and a 64 MiB CMA area; `OF_CONFIGFS` is not set.

## Decisions

### Out-of-tree module, not a kernel patch

The Wi-Fi driver is already carried as an out-of-tree module against the same kernel (`nix/k230-wifi-driver.nix`, `boot.extraModulePackages`). Doing the same for `vglite.ko` leaves the kernel Image byte-identical, so no Image replacement, kernel rebuild or initrd change is needed; the permanent change on the board is one DTB plus a system closure containing the module. Rejected: an in-tree `drivers/gpu/vglite` patch in `kernel-mainline-drm.nix`, which rebuilds the whole kernel and forces an Image install for no benefit.

### Port the driver faithfully, fix only what the 7.3 API forces

Keep the vendor ioctl ABI so the pinned SDK library and the existing renderer work unchanged. Changes are limited to API drift (for example `MODULE_IMPORT_NS` takes a string since 6.13) and to two points the vendor code left implicit: the driver enables the `vglite` clock around device use, and resets through the mainline reset-controller binding. The reset stays in the open path as in the vendor driver. Any behaviour difference is recorded in `docs/evidence/` with the vendor source line it departs from.

### Device-tree node shared by every mainline display DTB

The node goes in `nix/dts/k230-tdisplay-mainline-drm-common.dtsi` next to the carried `sysctl_power`, clocked by `&sysclk K230_DISPLAY_GPU_GATE` and reset by `&rst RST_GPU`. A present node with no driver loaded is inert, so it needs no opt-in.

### A no-reboot bounded trial route

Because `__symbols__` exposes the needed labels, a small companion module can apply the same node as a device-tree overlay at load and remove it at unload. That lets the driver be probed on the running board without touching `/boot`. It is a trial tool, never loaded at boot, and does not replace the permanent DTB node, which is what the acceptance gates verify after a reboot.

### Cache and DMA behaviour is carried, not claimed

The vendor HAL calls `flush_cache_all()` and maps `dma_alloc_coherent` memory to userspace cached; on a noncoherent T-Head system that is exactly the open cache-ownership question (`the-shell-trials-vglite-composition` task 2.4). This change provides the device and makes no coherency claim.

## Risks / Trade-offs

- Touching the GPU register window with its clock gated or its power domain off hangs the bus. Probe therefore only maps registers and registers the node; the first register access happens in `open`, after clock enable, power-domain resume and reset.
- DTB replacement is a boot-file change on the only board: install with `tools/push-file.py`, roll back by restoring the previous DTB (backed up first), recover over U-Boot `ums` via J3 per `docs/uboot-ums.md`.
- The driver is single-context by vendor design; concurrent opens are not supported. Access control stays with the broker of `the-shell-trials-vglite-composition`.
