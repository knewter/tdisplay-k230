# How the QEMU boot and the hardware boot differ

Required by `image/boot-chain`: *"The project SHALL record what differs between
the two paths, so that a failure on hardware after a success under emulation is
diagnosed against a written expectation rather than from memory."*

Started during `a-riscv-nixos-closure-cross-builds`, which can only observe the
QEMU side. The hardware column is completed by
`the-board-boots-what-we-built`.

Transcripts cited throughout: QEMU in `qemu-boot.txt`, hardware in
`hardware-boot.txt` (the boot chain, including the failures that preceded a
working one) and `hardware-userspace.md` (commands run on the booted board).

| | QEMU `-machine k230` | The board |
| --- | --- | --- |
| Stage 1 | **None.** QEMU loads the kernel directly. | BootROM → U-Boot SPL (+ DDR PMU training blob) → U-Boot 2022.10 → OpenSBI v1.4 |
| How the kernel is found | `-kernel` on the command line | Vendored U-Boot runs its `blinux` environment variable, which `ext4load`s each file from the boot partition by name. **Not extlinux** |
| Root filesystem | **Initrd only.** The machine models no block device. | ext4 on the SD card, `/dev/disk/by-label/NIXOS_SD` |
| NixOS module | `nix/qemu.nix` (`netboot-minimal`) | `nix/hardware.nix`, with `generic-extlinux-compatible` explicitly **disabled** |
| Kernel | Stock nixpkgs riscv64 | Xuantie, once `the-screen-comes-up-under-linux` lands |
| Page tables | Standard RISC-V PTE bits **required** | T-HEAD C9xx MAEE extensions available |
| RAM | 2 GiB given, because the whole system is in the ramdisk | 1 GiB, fixed |
| Console | Emulated UART at `ttyS0` | CH342 bridge → `/dev/ttyACM0`, 115200 8N1 |
| Kernel command line | `-append`, taken as given | Set by U-Boot, **not** by `/chosen/bootargs` in our DTB. See below |
| Cores | 1 | **1 under Linux.** The SoC has two C908s, but no K230 device tree declares a `cpu@1`; the second is Canaan's AMP core for RT-Smart. Confirmed by `nproc` on the board |
| Panel, touch, radios, SD | **Not modelled at all** | Present |

## The two that will actually bite

**Page tables.** QEMU does not implement the T-HEAD C9xx MAEE page-table
extensions that Canaan's SDK kernels use. A kernel built for the board may
therefore fail under QEMU even though it is correct, and the stock kernel that
boots under QEMU is not the one the board will eventually run. These are not
interchangeable artifacts, and a green QEMU run says nothing about the Xuantie
kernel.

**Stage 1 is entirely absent under QEMU.** Every bug in the vendored chain —
DDR training, the image header, U-Boot's environment, where it looks for a
kernel — is invisible here and appears for the first time on hardware. This is
the single largest gap between the two, and it is why a QEMU boot is not
evidence about the board.

## What a QEMU boot does prove

That the closure cross-builds, that the kernel and initrd are coherent, that
init runs, and that userspace reaches a prompt. That is genuinely worth having
before touching hardware — it means a hardware failure is a *boot chain*
problem rather than a userspace one.

## Two QEMU constraints found while implementing

**The `k230` machine generates no FDT.** `-machine k230,dumpdtb=...` answers
`This machine doesn't have an FDT`, so a device tree must be supplied with
`-dtb`. `tools/qemu-k230.sh` looks for one under the kernel's `dtbs/` and
fails with an explanation rather than booting without it. On hardware the
device tree is `ext4load`ed from the boot partition by name and handed to
`bootm` as its third argument.

**The whole system must be in the initrd.** The machine models no block
device, so `nix/qemu.nix` uses the `netboot-minimal` profile. On hardware
`nix/hardware.nix` mounts an ext4 root from the card. These produce different
closures, and only the hardware one is what eventually ships.

## Why the QEMU boot uses `virt` and not `k230`

Found while implementing, and it is a fact about mainline rather than a
convenience.

Linux 6.18.52 has **partial** K230 support: `drivers/pinctrl/pinctrl-k230.c`,
`drivers/reset/reset-k230.c`, and DT bindings for both. It has **no bootable
K230 platform**:

- `arch/riscv/boot/dts/canaan/` contains only K210 device trees
  (`k210.dtsi`, `canaan_kd233.dts`, `sipeed_maix_*`). There is no K230 DTS.
- `arch/riscv/Kconfig.socs` has `SOC_CANAAN_K210` and no `SOC_CANAAN_K230`,
  and the K210 entry is `depends on !MMU`.

So a stock nixpkgs kernel cannot boot QEMU's `k230` machine, which is also
why supplying a `-dtb` would not have rescued it.

A `k230`-machine boot needs the Xuantie kernel, built with
`CONFIG_ERRATA_THEAD_PBMT=n` — that errata is the T-Head memory-type
page-table extension ("non-standard memory type bits in page-table-entries on
T-Head SoCs") that QEMU does not implement. Packaging that kernel belongs to
`the-screen-comes-up-under-linux`, which needs it anyway.

`a-riscv-nixos-closure-cross-builds` is asking whether the closure builds and
starts, which is machine-independent, so `virt` answers it today and
`tools/qemu-k230.sh` grows a `MACHINE=k230` path for when the Xuantie kernel
lands.


## Corrections made after the first hardware boots

Three claims above were written from the QEMU side before the board had ever
run our image, and hardware disproved them. They are corrected in place; they
are recorded here because each one cost a boot cycle.

**OpenSBI is v1.4, not v0.9.** `output/k230_canmv_v3_defconfig/build/opensbi-1.4`
and `buildroot-overlay/boot/opensbi/opensbi-1.4-overlay`.

**There is no extlinux anywhere in this boot path.** The vendored U-Boot runs
`blinux`, an environment variable holding a chain of `ext4load` commands that
fetch each file from the boot partition by literal filename, ending in `bootm`.
Nothing parses `extlinux.conf`, and `nix/hardware.nix` therefore sets
`boot.loader.generic-extlinux-compatible.enable = false`. Anything that assumes
extlinux — a generation menu, an `APPEND` line — does not exist here.

**The device tree does not carry the kernel command line.** This is the
sharpest difference from QEMU, where `-append` is simply honoured. On the board
`board_fdt_chosen_bootargs()` overwrites `/chosen/bootargs` with a hardcoded
vendor string unless the U-Boot environment defines `bootargs`. The full
analysis is in `stage1-emergency-mode.md`; the consequence for this table is
that **the kernel command line is a property of the U-Boot environment and the
boot partition, not of the DTB we build.**

## Still unproven on hardware

This document cannot be finished until a boot reaches userspace. Outstanding:

- `Page tables` remains an expectation. No Xuantie kernel has been run under
  QEMU, so the MAEE/PBMT claim is untested in both columns. This is now the
  only row in the table that rests on reading rather than observation.

Two entries that were listed here as unproven have since been settled on
hardware, in `hardware-userspace.md`:

- **Cores.** Resolved, and not as expected — Linux gets one hart, by device
  tree design rather than by misconfiguration. The table row is corrected.
- **Root filesystem.** Resolved. `/proc/cmdline` carries no explicit `root=`,
  yet `/` is mounted from `/dev/mmcblk1p2`, so the `NIXOS_SD` label path did
  the work.
