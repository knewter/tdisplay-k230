# K230 second-core feasibility

This is a source and boot-record audit. It does not claim that the second
core can be enabled safely on this board, and it does not change the kernel,
device tree, OpenSBI, or firmware.

## What the chip provides

Canaan's primary documents describe two heterogeneous Xuantie C908 CPUs:

- [K230 product datasheet, CPU subsystem](https://github.com/kendryte/k230_docs/blob/main/zh/00_hardware/K230_datasheet.md): CPU0 is a 64-bit RISC-V core up to 800 MHz with 32 KiB L1 caches and 128 KiB L2; CPU1 is a 64-bit RISC-V core up to 1.6 GHz with RVV 1.0, 32 KiB L1 caches, and 256 KiB L2. The datasheet also documents separate CPU timers and a mailbox capable of CPU0/CPU1 interrupts.
- [K230 power-management guide](https://github.com/kendryte/k230_docs/blob/main/en/01_software/board/mpp/K230_PM_Usage_Guide.md): the supported heterogeneous split is CPU0 for Linux and CPU1 for RT-Smart; the large core also owns display, multimedia, and AI power domains.
- [K230 SDK user manual](https://github.com/kendryte/k230_docs/blob/main/en/01_software/board/K230_SDK_User_Manual.md): the SDK is explicitly organized as a Linux little-core side and an RT-Smart big-core side.
- [K230 RVV description](https://www.kendryte.com/k230/en/v1.7/02_applications/tutorials/K230_RVV_optimization_performance_description.html): confirms the C908 dual-core design and identifies RVV 1.0 as the large-core feature.

These documents establish hardware capability and the vendor AMP design. They
do not establish that this board's current Linux image can safely take CPU1.

## What the pinned image actually exposes

The pinned Xuantie kernel source is
`nix/kernel-src.nix` (the evaluated source path used here was
`/nix/store/hn11x8zd5linl193d8q0k9k99b46zqbm-linux-xuantie-k230-src`). Its
`arch/riscv/boot/dts/canaan/k230.dtsi:28-69` declares only `cpu@0`, with
`reg = <0>`, `thead,c908`, Sv39, 32 KiB I/D caches, and a 256 KiB unified L2
node. There is no `cpu@1`. The same file's K230 interrupt topology is
single-hart: the PLIC at `:210-218` references only `cpu0_intc`, and the CLINT
at `:255-259` references only CPU0's software/timer interrupt lines.

The repository's [boot-path comparison](../evidence/boot-path-differences.md)
and [hardware userspace evidence](../evidence/hardware-userspace.md) record
`nproc = 1`, `/proc/cpuinfo` containing only processor 0, and the reason:
the vendor AMP split reserves the other C908 for RT-Smart. The fresh physical
observation in `docs/evidence/cpu-readiness.txt` records the same state:
`CONFIG_SMP=y`, `NR_CPUS=64`, `RISCV_SBI=y`, but `/sys/devices/system/cpu`
has only CPU0 present/possible and the live DT has only `cpu@0`.

The current boot transcript is equally explicit:

```text
Platform HART Count       : 1
Platform IPI Device       : aclint-mswi
Platform Timer Device     : aclint-mtimer @ 27000000Hz
Platform HSM Device       : ---
Domain0 HARTs             : 0*
[    0.015...] smp: Brought up 1 node, 1 CPU
```

See `docs/evidence/boot-from-source-cold.txt:104-125,230-231` and the
OpenSBI/kernel configuration in `nix/opensbi-k230.nix` and `nix/kernel.nix`.
The kernel already has SMP, SBI, and a large `NR_CPUS` setting; the missing
piece is the platform description and firmware ownership, not a userspace
switch. The current OpenSBI build is generic OpenSBI 1.4 with the Canaan MAEE
quirk overlay, and the boot log shows no HSM device and only HART 0 in the
root domain.

The [official OpenSBI README](https://github.com/riscv-software-src/opensbi/blob/master/README.md)
states that Linux needs the HSM extension to boot multiple harts under modern
OpenSBI. The [official SBI HSM specification](https://github.com/riscv-non-isa/riscv-sbi-doc/blob/master/src/ext-hsm.adoc)
defines the start/stop/status calls. Our boot log demonstrates that the
current firmware/image path does not expose a second HART to Linux; it does
not prove that the silicon lacks HSM hardware.

## Barriers to Linux SMP

Adding a `cpu@1` node alone is not a sufficient or safe patch:

1. **Ownership:** Canaan documents CPU1 as the RT-Smart core. A Linux SMP
   experiment would take it away from the vendor AMP system and may also take
   display/multimedia control away from the firmware that currently owns those
   domains.
2. **OpenSBI/HSM:** the current platform reports one HART and no HSM device.
   OpenSBI must enumerate HART 1, assign it to the Linux domain, and provide a
   valid hart-start path. The `/chosen/opensbi-domains` node currently requests
   only the existing generic setup (`k230.dtsi:21-26`); no second-HART domain
   or ownership contract is present.
3. **Interrupts and timers:** the K230 DTS PLIC and CLINT bindings currently
   target CPU0 only. CPU1 needs a correctly described local interrupt
   controller, software/timer interrupt routes, and the right K230 timer/IPI
   hardware. The datasheet's mailbox is evidence of an inter-core mechanism,
   but it is not automatically a Linux SBI IPI implementation.
4. **ISA and MMU:** CPU1 has RVV 1.0 and different cache topology. The current
   kernel DT advertises only CPU0's ISA and cache description. A Linux SMP
   kernel must use a common ISA baseline or keep vector use conditional; it
   must also describe CPU1's MMU and cache hierarchy accurately.
5. **Coherency and shared memory:** the official material documents separate
   L2 sizes and inter-core messaging, but the repository contains no proof of
   the cache-coherency contract needed for Linux's shared page tables and SMP
   atomics. This must be established from the K230 programming/reference manual
   or a controlled experiment before treating Linux SMP as viable.

## Viable options

The lowest-risk option is to keep the supported AMP split: Linux remains on
CPU0 and RT-Smart remains on CPU1. This is the only configuration evidenced by
the current board and vendor software, and it preserves the display and
multimedia ownership expected by the SDK.

A Linux SMP option would require a coordinated patch family, not one DTS edit:

- a K230 DT CPU1 node with its actual hart ID, ISA, MMU, cache, local
  interrupts, and timer/IPI wiring;
- PLIC/CLINT or K230 interrupt-controller updates for both harts;
- OpenSBI platform/domain configuration that discovers and starts HART 1 and
  assigns it to Linux, with HSM calls working;
- kernel SMP bring-up validation, common-ISA handling, cache/coherency tests,
  and removal or replacement of the RT-Smart ownership path; and
- a decision about which core owns the display, multimedia, KPU, mailbox, and
  power domains after the split is removed.

An AMP-with-Linux-plus-RT-Smart option is more plausible if the goal is to
use CPU1's compute capability: keep CPU1 under RT-Smart and communicate through
the vendor mailbox/shared-memory APIs. That is a separate integration project,
not Linux SMP, and no current repository source exposes a ready Linux-side API
for it.

## Minimal recoverable experiment

Do not experiment on the only working card. Preserve the current image and
use a second card or a reversible UMS image. The first experiment should be a
firmware/DT bring-up with no display or shell changes:

1. Create an experimental DT that adds CPU1 and only the verified local
   interrupt/timer descriptions from the K230 reference material; do not guess
   register routes from the CPU count.
2. Build an OpenSBI variant that reports HART 1 and HSM status, while retaining
   the Canaan MAEE quirk and a known-good rollback image.
3. Boot with early serial logging and require, in order, `Platform HART Count:
   2`, a non-`---` HSM path, Linux `smp: Brought up 1 node, 2 CPUs`, and
   successful CPU hotplug/status checks. Stop immediately on a hang, missing
   HART, or interrupt/timer failure.
4. Only after that should cache/coherency stress and display/multimedia
   ownership tests begin. A failed experiment must be restorable by flashing
   the preserved known-good stage-1/kernel image over the already-proven UMS
   path.

This experiment would prove only Linux can start CPU1. It would not prove that
the RT-Smart AMP workload, display ownership, cache coherency under load, or
the full vendor SDK still works. No board experiment was run for this audit.
