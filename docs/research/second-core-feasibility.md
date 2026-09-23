# K230 second-core feasibility

This is a source and boot-record audit. It does not claim that the second core
can be enabled safely, and it does not change the kernel, device tree, OpenSBI,
or firmware.

## Silicon and vendor architecture

Canaan's primary documents describe two heterogeneous Xuantie C908 CPUs:

- [K230 product datasheet, CPU subsystem](https://github.com/kendryte/k230_docs/blob/main/zh/00_hardware/K230_datasheet.md): CPU0 is a 64-bit RISC-V core up to 800 MHz with 32 KiB L1 caches and 128 KiB L2; CPU1 is a 64-bit RISC-V core up to 1.6 GHz with RVV 1.0, 32 KiB L1 caches, and 256 KiB L2. The datasheet also documents separate CPU timers and a mailbox capable of CPU0/CPU1 interrupts.
- [K230 power-management guide](https://github.com/kendryte/k230_docs/blob/main/en/01_software/board/mpp/K230_PM_Usage_Guide.md): the SDK's documented split assigns CPU0 to Linux and CPU1 to RT-Smart; the large core also owns display, multimedia, and AI power domains.
- [K230 SDK user manual](https://github.com/kendryte/k230_docs/blob/main/en/01_software/board/K230_SDK_User_Manual.md): the SDK is organized as a Linux little-core side and an RT-Smart big-core side.
- [K230 RVV description](https://www.kendryte.com/k230/en/v1.7/02_applications/tutorials/K230_RVV_optimization_performance_description.html): confirms the C908 dual-core design and identifies RVV 1.0 as the large-core feature.

These documents establish hardware capability and the vendor SDK's AMP
design. They do not establish which physical core the current Xuantie Linux
image uses, or that Linux can safely take the other core.

## What the pinned image exposes

The pinned Linux source is `nix/kernel-src.nix`, from
`ruyisdk/linux-xuantie-kernel` revision
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`. The evaluated source path was
`/nix/store/hn11x8zd5linl193d8q0k9k99b46zqbm-linux-xuantie-k230-src`.
`arch/riscv/boot/dts/canaan/k230.dtsi:28-69` declares only `cpu@0`, with
`reg = <0>`, `thead,c908`, Sv39, and one cache description. There is no
`cpu@1`. Its PLIC at `:210-218` references only `cpu0_intc`, and its CLINT at
`:255-259` references only CPU0 software/timer interrupt lines.

The project image is the K230 Linux SDK/Xuantie Linux path, not a complete
Linux-plus-RT-Smart image. `nix/stage1.nix:140-142` carries OpenSBI, its U-Boot
header, and the kernel-side boot files; it does not carry an RT-Smart payload.
`nix/kernel.nix` uses the vendor `k230` kernel defconfig and sets SMP support,
but the DT presents one hart.

The [boot-path comparison](../evidence/boot-path-differences.md) and
[hardware userspace evidence](../evidence/hardware-userspace.md) record
`nproc = 1` and only processor 0. Fresh physical evidence in
`docs/evidence/cpu-readiness.txt` records `CONFIG_SMP=y`, `NR_CPUS=64`,
`RISCV_SBI=y`, only CPU0 present/possible, live DT only `cpu@0`, and a Linux
hart reporting `thead,c908`, vector support, and a 256 KiB L2. That is
consistent with the datasheet's big-core description, so it is unsafe to
label logical hart 0 as physical CPU0 or CPU1 without a register/firmware
observation.

The current boot transcript says:

```text
Platform HART Count       : 1
Platform IPI Device       : aclint-mswi
Platform Timer Device     : aclint-mtimer @ 27000000Hz
Platform HSM Device       : ---
Domain0 HARTs             : 0*
[    0.015...] smp: Brought up 1 node, 1 CPU
```

See `docs/evidence/boot-from-source-cold.txt:104-125,230-231`. The source
and logs establish one enumerated HART, not the physical-core identity and not
that RT-Smart is running on the other core in this image.

## OpenSBI and SMP barriers

The [official OpenSBI README](https://github.com/riscv-software-src/opensbi/blob/master/README.md)
and [official SBI HSM specification](https://github.com/riscv-non-isa/riscv-sbi-doc/blob/master/src/ext-hsm.adoc)
describe HSM hart start/stop/status calls required for normal Linux multi-hart
boot. In the pinned OpenSBI source
`/nix/store/k6kih6q1vh5nashsgaz96ch012742s8z-source`,
`lib/sbi/sbi_ecall_hsm.c:19-67` implements the HSM SBI calls and
`lib/sbi/sbi_init.c:98-100` prints `Platform HSM Device`. That line reports a
platform-specific HSM device pointer; `---` is not proof that the SBI HSM
extension is absent. The current log proves only that one HART was enumerated
and assigned to the root domain.

Adding a `cpu@1` node alone is therefore insufficient:

1. **Physical mapping and ownership are unknown.** The current carried image
   has no RT-Smart payload. The SDK's CPU0/Linux, CPU1/RT-Smart mapping is a
   reference architecture, not proof for this image. The live hart's RVV and
   L2 size make big-core execution plausible, but no source or current log
   maps logical hart 0 to a physical core. Display, multimedia, KPU, mailbox,
   and power-domain ownership must be established separately.
2. **HART discovery and start:** OpenSBI must enumerate a second unique hart,
   assign it to Linux, and provide a valid hart-start path. The current
   `/chosen/opensbi-domains` node (`k230.dtsi:21-26`) does not describe a
   second-HART domain or ownership contract.
3. **Interrupts and timers:** the K230 DTS PLIC and CLINT target CPU0 only.
   CPU1 needs verified local interrupt, software/timer interrupt, and K230
   timer/IPI wiring. The datasheet mailbox proves an inter-core mechanism, but
   not a Linux SBI IPI implementation.
4. **ISA and MMU:** CPU1 has RVV 1.0 and a different cache topology. Linux
   needs an accurate CPU1 ISA/MMU/cache description and a common ISA baseline
   for SMP code.
5. **Coherency and shared memory:** the repository has no proof of the cache
   coherency contract needed for Linux shared page tables and SMP atomics.
   This must be established from the K230 programming/reference material or a
   controlled firmware experiment before any Linux shared-memory test.

## Options

The lowest-risk option is to leave this single-hart Linux image unchanged.
The vendor SDK's AMP split is a separate reference architecture; this image
contains no RT-Smart payload, and its physical-core mapping and peripheral
ownership remain unknown.

A Linux SMP option needs a coordinated patch family, not one DTS edit:

- DT CPU1 with verified hart ID, ISA, MMU, cache, local interrupt, and timer
  data;
- PLIC/CLINT or K230 interrupt-controller support for both harts;
- OpenSBI domain and hart-start support with generic HSM calls verified;
- kernel SMP bring-up with common-ISA handling; and
- an ownership decision for display, multimedia, KPU, mailbox, and power
  domains after removing the current single-hart/SDK assumptions.

An AMP Linux-plus-RT-Smart option would require adding and validating the
RT-Smart payload and its ownership contract. It is not evidence about this
image, and no ready Linux-side API for it is present here.

## Minimal recoverable experiment

Do not experiment on the only working card. Preserve the current image and use
a second card or reversible UMS image. Before attempting Linux SMP or shared
memory:

1. Establish the physical-to-hart map and ownership from the K230 reference
   manual and a controlled firmware/register observation. Confirm unique hart
   IDs, reset release, interrupt/timer routes, cache hierarchy, and the
   coherency/atomic-sharing contract.
2. Only then prepare an experimental DT with CPU1 and those verified
   descriptions; do not infer routes from the CPU count.
3. Generic SBI HSM is already compiled and detected in this image
   (`docs/evidence/boot-from-source-cold.txt:173`). Investigate whether the
   verified second hart can use OpenSBI's existing raw-IPI start path or needs
   a platform HSM start device, then build a variant that enumerates it.
   Retain the Canaan MAEE quirk and a rollback image. Treat
   `Platform HSM Device: ---` as informational, not as the acceptance test.
4. Boot with early serial logging and require HART count 2, Linux
   `smp: Brought up 1 node, 2 CPUs`, and successful CPU status checks. Stop on
   any hang, missing HART, or interrupt/timer failure. Only after that test
   shared-memory/cache behavior and peripheral ownership.
5. Restore the known-good stage-1/kernel image over the proven UMS path after
   any failed experiment.

This would prove only that Linux can start a uniquely identified second hart
after the coherency and ownership prerequisites are established. It would not
prove RT-Smart AMP operation, display ownership, or the full vendor SDK. No
board experiment was run for this audit.

## 2026-09 evidence update and decision

The primary [K230 Technical Reference Manual v0.3.1 (TRM)](https://kendryte-download.canaan-creative.com/developer/k230/HDK/K230%E7%A1%AC%E4%BB%B6%E6%96%87%E6%A1%A3/K230_Technical_Reference_Manual_V0.3.1_20241118.pdf)
resolves part of the physical mapping which the earlier audit deliberately
left open. Section 1.3.2 identifies CPU0 as the 800 MHz/128 KiB-L2 small core
and CPU1 as the 1.6 GHz/256 KiB-L2 RVV big core. Section 1.4.1 says BootROM
starts CPU0 after reset deassertion and CPU0 controls CPU1 reset deassertion.
That establishes reset ownership, but it does **not** assign Linux hart IDs or
describe a Linux secondary-hart release protocol.

The current Linux hart reports RVV and a 256 KiB L2 while the TRM assigns both
features to CPU1. This makes CPU1 execution a strong inference for the
current Linux handoff. It remains an inference, not a basis to add a guessed
`cpu@1`: the physical-core-to-hart mapping is not in the captured handoff.

### What the vendor register map proves—and does not

The TRM provides real CPU1 controls:

- RMU is at `0x91101000`; `CPU1_RST_CTL` is offset `0x0c`. Its reset value is
  `0x00002001`; bit 0 is `cpu1_reset_req` (one means reset). Bit 4 requests
  an L2 flush and bits 12--13 are write-one-to-clear reset-done flags (TRM
  section 2.1.4).
- PWR is at `0x91103000`; CPU1 control/status are offsets `0x18`/`0x1c`
  (TRM section 2.3.4). The CPU power-flow text requires a completed NOC
  low-power handshake before a power transition (section 2.3.3).
- The interrupt table lists distinct mailbox sources in both CPU0-to-CPU1 and
  CPU1-to-CPU0 directions (TRM section 2.4).

Those facts rule out a speculative register poke: a write would be an actual
reset or power transition, and reads of the W1C-containing reset register must
not be turned into read-modify-write operations. The TRM does not publish a
CPU1 reset vector, physical hart ID, PLIC context mapping, ACLINT wiring, or
an SBI HSM implementation for this device.

It also does not establish the condition Linux SMP actually needs: coherent
shared memory for page tables, spinlocks, and secondary-start data. The
existing DT's `dma-noncoherent` property concerns DMA; it neither proves nor
disproves CPU-to-CPU cache coherence. The TRM describes per-C908 cache control
and an instruction-cache/data-cache snoop control, but contains no CPU0/CPU1
coherency or shared-atomic contract. This is a blocking absence of evidence,
not a demonstrated hardware impossibility.

### Linux SMP is a different project from AMP

The pinned Linux code makes the integration requirements concrete. Its
[`cpu_ops_sbi.c`](https://github.com/ruyisdk/linux-xuantie-kernel/blob/7d4e1f444f461dbe3833bd99a4640e7b6c2cd529/arch/riscv/kernel/cpu_ops_sbi.c)
starts a secondary with `SBI_EXT_HSM_HART_START`; its
[`cpu.c`](https://github.com/ruyisdk/linux-xuantie-kernel/blob/7d4e1f444f461dbe3833bd99a4640e7b6c2cd529/arch/riscv/kernel/cpu.c)
requires a valid ISA description for each DT CPU; and the K230 DTS supplies
only one CPU interrupt controller to its PLIC and CLINT. Therefore Linux SMP
needs a verified second hart, HSM start path, timer/IPI routes, CPU ISA/MMU and
cache description, and coherency contract before a DT change is even useful.

AMP has a different boundary: separate firmware images, mailbox notifications,
explicitly managed shared buffers, and exclusive peripheral ownership. Canaan
documents separate Linux little-core and RT-Smart big-core SDK images, which
is evidence for an AMP model, not for Linux SMP. This image has neither the
RT-Smart payload nor a Linux-side video-offload protocol, so AMP cannot yet
improve the running video workload. A second core can help video only after a
measured offload design exists; two cores alone do not improve a single-thread
renderer or prove shared-memory safety.

### Proposed safe next step: passive handoff audit

No boot configuration, device tree, CPU online state, or MMIO register is
changed by this proposal. The integration operator should collect the following
from a known-good board when it is free; this investigation does not take the
serial device.

1. Preserve a cold-boot console capture containing OpenSBI platform HART
   count, domain HART list, HSM/IPI/timer device lines, and Linux's `smp:`
   result. This separates a firmware one-hart declaration from a Linux
   secondary-start failure.
2. Capture the live `cpus` DT subtree, PLIC/CLINT `interrupts-extended`,
   `/sys/devices/system/cpu/{possible,present,online}`, and per-CPU ISA/cache
   reports. These no-write facts identify the handoff Linux actually received.
3. Only with the operator's established **read-only** MMIO capture method,
   record values at `0x9110100c`, `0x91103018`, and `0x9110301c`. Do not use
   a tool mode that writes, performs read-modify-write, clears W1C status, or
   probes adjacent registers. These values may show reset/power state; they
   cannot establish hart identity or coherency.
4. Obtain a Canaan statement or shipped stage-1 source proving the CPU1
   release sequence and vector, physical hart IDs, PLIC/ACLINT contexts, and
   CPU-to-CPU coherency contract. An undocumented release sequence is a stop
   condition.

Only after step 4 should a separate rollback-card SMP proposal exist. It must
first make OpenSBI enumerate and HSM-start both verified harts, then add the
complete DT routes, then enable Linux SMP. Its acceptance criteria begin with
two OpenSBI harts, `smp: Brought up 1 node, 2 CPUs`, timer/IPI stress, and a
shared-memory atomic test. Video benchmarking comes after correctness, not
before it. No board experiment was performed for this update.

## Vendor AMP source establishes a release contract, not SMP support

A further source review found the vendor's concrete Linux-to-RT-Smart AMP path
in [`k230-amp.c`](https://github.com/kendryte/k230_sdk/blob/main/src/little/linux/drivers/misc/canaan/k230-amp.c)
and its [`amp_test`](https://github.com/kendryte/k230_sdk/blob/main/src/little/buildroot-ext/package/amp_app/src/amp_test.c)
client. This is primary vendor source, but it is not part of this NixOS image.

The client opens `/dev/k230-amp`, maps a device-tree-selected RT-Smart memory
region, loads a firmware image there, then invokes `AMP_CMD_BOOT`. The driver
writes that region back from the running Linux CPU's cache, programs the CPU1
reset-vector register, and performs the CPU1 reset-control writes. Mapping the
region first holds the large core in reset. The companion README calls this
"small-core Linux controls big-core restart". That is direct evidence that the
vendor AMP boundary requires an explicit firmware payload, memory reservation,
cache maintenance, reset vector, and reset protocol.

It does not establish Linux SMP. The driver hardcodes vendor addresses and does
not create a Linux CPU, an OpenSBI domain, a PLIC/ACLINT route, or shared Linux
page-table coherency. Its actual reset writes are why this project will not use
it as a probe or copy it into the image.

The vendor's generic OpenSBI platform independently counts harts by iterating
`/cpus` in [`platform/generic/platform.c`](https://github.com/kendryte/k230_sdk/blob/main/src/common/opensbi/platform/generic/platform.c).
The pinned handoff supplies only `cpu@0`, so the observed OpenSBI platform
count of one follows from the handoff description. OpenSBI's generic HSM ecall
handler being linked only means it can dispatch `HART_START` for an assigned,
known hart; it does not manufacture CPU1 release support.

The publicly documented DRAM RAW/WAR coherency guarantees apply to the memory
controller interfaces and are conditional on configuration for AXI. They are
not a documented CPU0/CPU1 cache-coherency or atomic-sharing contract. This
remains a blocker for Linux SMP, while the AMP source shows cache maintenance
must be part of any separately designed shared-buffer protocol.
