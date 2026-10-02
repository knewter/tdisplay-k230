# Mainline restart-path source audit

This is a read-only source audit of the reset path relevant to the physical
minimal-initrd run recorded in
[`minimal-probe-2026-10-02/README.md`](minimal-probe-2026-10-02/README.md).
It separates that run's observed `systemctl` refusal from what the pinned
kernel sources imply would happen if a later request reached the kernel restart
path.

The run used controller source `d209a062f6826877173a7d2669d99b18c82c6416`
and the candidate bundle
`/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-k230-mainline-drm-trial-boot-files`.
Its `Image-mainline-drm` SHA-256 is
`befebfd67ea9aa829ace3bfd97d12ced42068ab412b9789221d90028a1328426`; it
matches `/nix/store/i77i3ppi72k9hw0v2xmnhilc3q7rvv50-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/Image`.
The kernel source pin is Linux commit
`72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` from
[`nix/kernel-mainline-src.nix`](../../../../nix/kernel-mainline-src.nix).
The matching kernel build configuration is available in the dev output of the
same `linux-riscv64-unknown-linux-gnu-7.3.0-rc5.drv` as
`lib/modules/7.3.0-rc5/build/.config`.

The physical run established receipt in the initrd shell, `/bin/true` returning
zero, and `/proc/uptime` failing because `/proc` was absent. `/bin/reboot -ff`
then printed the systemd chroot refusal and returned to the shell; it did not
issue a kernel reboot request. Normal-login recovery timed out and the
observation was `pending-physical-reset` when the controller stopped. A later
[operator power cycle and protected postflight](minimal-probe-recovery-2026-10-02/README.md)
verified normal-system recovery. This is not a physical test of the candidate
kernel's reset behavior.

The exact 7.3-rc5 boot logs report SBI specification 2.0 and detect TIME, IPI,
RFENCE, DBCN, and HSM, but do not report `SBI SRST extension detected`
([`serial-boot.txt`](serial-boot.txt#L450),
[`serial-diagnostic-boot.txt`](serial-diagnostic-boot.txt#L452)). In the pinned
kernel source at
[`arch/riscv/kernel/sbi.c`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/arch/riscv/kernel/sbi.c#L682),
SRST is probed and the SBI restart notifier registered only inside the success
branch (lines 682–689). The candidate's generated `.config` has
`CONFIG_RISCV_SBI=y`, so this code is present; `System.map` also contains
`sbi_srst_reboot`, which proves linkage, not that the conditional notifier was
registered on this firmware. The same boot logs say UEFI is absent. Without a
different restart handler,
[`arch/riscv/kernel/reset.c::machine_restart()`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/arch/riscv/kernel/reset.c#L19)
calls `do_kernel_restart()` and then loops forever.

The candidate trial reused the protected normal stage-one wrapper, whose
manifest SHA-256 is
`9627edbeea9b115d7040beea27cc61b23b6aca61cd502fd7760d7ee179f42c99`.
[`nix/opensbi-k230.nix`](../../../../nix/opensbi-k230.nix) pins OpenSBI v1.4
with the Canaan overlay and builds `PLATFORM=generic`; the exact board boot log
reports implementation ID 1, version `0x10004` (OpenSBI 1.4). This identifies
the loaded stage-one artifact and observed SBI response; it does not claim
what an unadvertised firmware extension might do if called directly.

The generated `.config` has `CONFIG_RESET_K230=y`,
`CONFIG_POWER_RESET=y`, `CONFIG_POWER_RESET_GPIO_RESTART=y`,
`CONFIG_POWER_RESET_SYSCON=y`, `CONFIG_POWER_RESET_SPACEMIT_P1=y`, and
`CONFIG_WATCHDOG=y`. The generic GPIO/syscon reset drivers need matching
device-tree nodes to register hardware handlers. The mainline board DTS
([`k230-tdisplay-mainline.dts`](../../../../nix/dts/k230-tdisplay-mainline.dts))
and included `k230.dtsi` contain no `gpio-restart`, `syscon-reboot`, or
watchdog node; the `spacemit,p1` handler is for a different platform. The K230
node is a normal `canaan,k230-rst` reset controller.
Mainline's
[`drivers/reset/reset-k230.c`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/reset/reset-k230.c#L324)
provides reset-control assert/deassert/reset operations but has no restart
registration. `CONFIG_RESET_K230=y` therefore does not provide a system
restart handler.

This differs from the pinned vendor kernel's
[`drivers/reset/reset-k230.c`](https://github.com/ruyisdk/linux-xuantie-kernel/blob/7d4e1f444f461dbe3833bd99a4640e7b6c2cd529/drivers/reset/reset-k230.c#L328):
its probe calls `k230_restart_register()`, which registers a K230 restart
notifier before registering the peripheral reset controller. The archived
normal-system serial evidence shows the vendor kernel's restart path reaching
U-Boot SPL after `reboot: Restarting system`
([`serial-boot.txt`](serial-boot.txt#L260)). That is evidence for the vendor
kernel path, not for mainline.

**Source prediction, not board proof:** after `/proc` is mounted and the
systemd chroot guard is cleared, the current mainline image may emit its
restart message and remain in the RISC-V restart loop because this boot did
not detect SBI SRST and the mainline DT/reset driver provides no replacement
handler. The reboot marker observed before systemd's refusal cannot establish
that the kernel can reset. This risk does not explain the prior systemd
initrd's missing login and must not be presented as its cause.

The next kernel-side requirement is a documented system restart mechanism for
this board: either make OpenSBI expose and implement SRST for the loaded K230
platform, or forward-port a reviewed K230 restart handler alongside the
mainline reset driver. Do not write the reset register from an ad-hoc initrd
command. The controller's `/proc` setup correction can be reviewed and landed
independently; this audit does not authorize another board trial or claim
successful mainline restart. No board, serial, build, or kernel source change
was used for this audit.
