# How the QEMU boot and the hardware boot differ

Required by `image/boot-chain`: *"The project SHALL record what differs between
the two paths, so that a failure on hardware after a success under emulation is
diagnosed against a written expectation rather than from memory."*

Started during `a-riscv-nixos-closure-cross-builds`, which can only observe the
QEMU side. The hardware column is completed by
`the-board-boots-what-we-built`.

| | QEMU `-machine k230` | The board |
| --- | --- | --- |
| Stage 1 | **None.** QEMU loads the kernel directly. | BootROM → U-Boot SPL (+ DDR PMU training blob) → U-Boot 2022.10 → OpenSBI v0.9 |
| How the kernel is found | `-kernel` on the command line | Vendored U-Boot reads an extlinux config from the SD card |
| Root filesystem | **Initrd only.** The machine models no block device. | ext4 on the SD card, `/dev/disk/by-label/NIXOS_SD` |
| NixOS module | `nix/qemu.nix` (`netboot-minimal`) | `nix/hardware.nix` (`generic-extlinux-compatible`) |
| Kernel | Stock nixpkgs riscv64 | Xuantie, once `the-screen-comes-up-under-linux` lands |
| Page tables | Standard RISC-V PTE bits **required** | T-HEAD C9xx MAEE extensions available |
| RAM | 2 GiB given, because the whole system is in the ramdisk | 1 GiB, fixed |
| Console | Emulated UART at `ttyS0` | CH342 bridge → `/dev/ttyACM0`, 115200 8N1 |
| Cores | 1 (the little C908) | 2 (C908 at 1.6 GHz and 800 MHz) |
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
