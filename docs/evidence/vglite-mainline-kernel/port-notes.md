# VG-Lite driver port to mainline 7.3: differences from the vendor driver

Source: `drivers/gpu/vglite/*.[ch]` of `ruyisdk/linux-xuantie-kernel` @
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529` (the tree in `nix/kernel-src.nix`),
copied to `nix/patches/mainline/vglite/`. The ioctl ABI, `vg_lite_kernel.c`
and all headers are unchanged. Every change is in `vg_lite_hal.c`:

| Change | Why |
| --- | --- |
| `MODULE_IMPORT_NS("DMA_BUF")` (string) | Namespace argument is a string since 6.13; vendor line is the 6.6 spelling. |
| Dropped `#include <linux/of_gpio.h>` | Unused by the driver; header removed from newer trees. |
| `.remove` returns `void` | `platform_driver::remove` changed signature (6.11); wrapper `vg_lite_remove()` calls the old function. |
| `mmap_write_lock()/unlock()` instead of `down_write(&current->mm->mmap_lock)` | Use the accessor API; also unlock on the `find_vma()` failure return, which vendor code returned with the lock held. |
| `GFP_KERNEL` only for `dma_alloc_coherent` | `GFP_DMA` is not meaningful on riscv64; the 32-bit DMA mask already constrains placement. |
| Clock enabled in `vg_lite_hal_open()`, disabled in `_close()` | Vendor code fetched the `vglite` clock but never enabled it; on mainline the gate is off after boot (`display_gpu_gate` enable count 0 in `clk_summary`, board 2026-10-30). Register access with the gate off would hang the bus. |
| `devm_reset_control_get_exclusive()` with error handling; clock and reset errors fail probe (including `-EPROBE_DEFER`) | Vendor ignored errors. |
| `kzalloc`, NULL-ing `device` after free, `pm_runtime_disable()` on teardown, `-ENOMEM` returns | Probe/teardown robustness (vendor leaked on early failure). |
| `drv_open` allocation failure undoes `vg_lite_hal_open()` | Vendor leaked the power/clock reference. |

Unchanged on purpose (open questions, not claims): `flush_cache_all()` in
`vg_lite_hal_barrier()` and cached userspace mappings of
`dma_alloc_coherent` memory on a noncoherent T-Head system, `vm_mmap` +
`remap_pfn_range` mapping, `IGNORE_INTERRUPT` polling loop. These are the
cache-ownership questions of `the-shell-trials-vglite-composition` task 2.4.

`vglite_overlay.c` is new: a trial module that applies the node as a runtime
overlay (`of_overlay_fdt_apply`) so the driver can be probed without changing
`/boot`. The mainline GPU node is in
`nix/dts/k230-tdisplay-mainline-drm-common.dtsi`; its overlay twin is
`nix/dts/k230-vglite-gpu-overlay.dts`.
