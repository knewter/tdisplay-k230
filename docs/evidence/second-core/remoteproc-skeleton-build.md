# CPU0 carveout and read-only remoteproc skeleton (tasks 4.1-4.3)

**Evidence class: host device-tree build and cross kernel build, 2026-10-12.
No board.** Nothing here has booted; task 5.1 is the first board use.

## 4.1 Carveout and node (DT build proof)

`nix/dts/k230-tdisplay-mainline-cpu0-rproc.dtsi`, included only by the
opt-in `nix/dts/k230-tdisplay-mainline-drm-hotplug-cpu0.dts`
(`.#deviceTreeMainlineDrmHotplugCpu0`). The daily tree is untouched:
`deviceTreeMainlineDrmHotplug` and `mainlineDrmHotplugDeviceTreeNormalName`
evaluate to the same derivations as master `a486398a`
(`2nf5ryig…-k230-tdisplay-mainline-drm-hotplug.dtb.drv`,
`k5939fzs…-k230-mainline-drm-hotplug-dtb-normal-name.drv`), as does the daily
system toplevel (`lhdphdj8…-nixos-system-…drv`).
`nix/device-tree-mainline-drm.nix` gained `extraIncludes` (empty default,
byte-identical script) so the variant can include the hotplug dts.

Decompiled `k230-tdisplay-mainline-drm-hotplug-cpu0.dtb` (`fdtget`):

| Node | Property | Value |
| --- | --- | --- |
| `/reserved-memory/cpu0-firmware@7000000` | `reg` | `0 7000000 0 100000` (1 MiB) |
| | `no-map` | present |
| `/reserved-memory/framebuffer@10000000` | `reg` | `0 10000000 0 400000` (splash, unchanged, disjoint) |
| `/soc/remoteproc@91102100` | `compatible` | `canaan,k230-cpu0-rproc` |
| | `reg` | `0 91102100 0 4` (CPU0 boot vector, outside `sysclk` `0x91102000+0x40`) |
| | `resets` | `<7 0>`: phandle 7 = `/soc/reset-controller@91101000`, index 0 = `RST_CPU0` |
| | `memory-region` | phandle `0x13` = `cpu0-firmware@7000000` |

The carveout covers the window the heartbeat and echo payloads already ran
in (image at `+0`, slot page at `+0x2000`), which Linux could otherwise
allocate. `0x07000000` holds only U-Boot's `bootargs.txt` before `bootm`.

Limit: deviation from the task text, which names `nix build .#deviceTree`
(the vendor tree); the decision note moved this work to the mainline tree
the board runs.

## 4.2 Driver skeleton (cross-build proof)

`nix/patches/mainline/k230_cpu0_rproc.c`, built in-tree by
`nix/kernel-mainline-drm-rproc.nix` (`.#kernelMainlineDrmRproc`): the daily
DRM kernel plus `CONFIG_REMOTEPROC=y` and `CONFIG_K230_CPU0_REMOTEPROC=m`.
The daily kernel is not changed.

What it does at probe: refuses any `resets` other than a single
`<&rst RST_CPU0>`; `devm_reset_control_get_exclusive()`; one read-only
`reset_control_status()` (reset-k230.c registers no `.status`, so an error
code is expected and reported); maps the vector register with
`devm_platform_ioremap_resource()` and the carveout with `devm_memremap(WC)`;
registers a remoteproc with `auto_boot = false` and `sysfs_read_only = true`.
`.start`/`.stop` return `-EOPNOTSUPP`. A `cpu0_status` attribute reports the
vector register, the reset status code, the carveout and the slot-page magic.
It contains no `writel`, no `reset_control_reset/assert/deassert`.

Proofs:

- `scripts/checkpatch.pl --no-tree --strict -f`: 0 errors, 0 warnings,
  0 checks.
- Early out-of-tree compile against the daily kernel's headers
  (`gcc 15.3.0`, the kernel's own compiler): compiles with no warnings;
  modpost lists only `devm_rproc_alloc`/`devm_rproc_add` undefined, because
  the daily kernel has no `CONFIG_REMOTEPROC`. That is why the in-tree
  variant exists.
- In-tree build, `nix build .#kernelMainlineDrmRproc` (2026-10-12, under the
  build lock, `--max-jobs 1 --cores 4`): exit 0, kernel
  `/nix/store/qawjbc553pihf38izgf5v0qmwb4h3sgl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`;
  `CC [M] drivers/remoteproc/k230_cpu0_rproc.o` with no compiler warning,
  no modpost warning. Its `.config` has `CONFIG_REMOTEPROC=y` and
  `CONFIG_K230_CPU0_REMOTEPROC=m`.
- Module `…-7.3.0-rc5-modules/lib/modules/7.3.0-rc5/kernel/drivers/remoteproc/k230_cpu0_rproc.ko.xz`
  (SHA-256 `19a6ff34bb073b442f3bef125ee388edeec6d952460d586f9b0dc5b0ab1feda8`):
  `modinfo` vermagic `7.3.0-rc5 SMP preempt mod_unload riscv`, alias
  `of:N*T*Ccanaan,k230-cpu0-rproc`. Its only reset-API imports (`nm -u`)
  are `__devm_reset_control_get` and `reset_control_status`: no
  `reset_control_reset`, `_assert` or `_deassert` is linked, so the module
  cannot pulse CPU0. The source has no `writel`.

## 4.3 Why no mailbox yet

Stated in the driver's header comment: the TRM's mailbox map (section 2.9)
lacks the interrupt-group wiring, lock semantics and CPU0 routing
(`docs/research/second-core-feasibility.md`, UNVERIFIED), so the transport
stays the polled slot page until a firmware speaks virtio/rpmsg; then a
poll-mode (`txdone_poll`) mailbox controller attaches through `.kick`
(design.md Decisions 1 and 5), replaceable by the hardware mailbox later.

## Successor

Task 5.1 extended this driver to load and start CPU0; its board run and the
new module hash are in `linux-start-2026-10-12/README.md`. The module hash
above is the read-only skeleton's.
