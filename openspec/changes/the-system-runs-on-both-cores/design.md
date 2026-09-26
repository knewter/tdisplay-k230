## Context

See proposal.md and `docs/research/second-core-feasibility.md` (the full
source and boot-record audit this design continues), and the existing
`openspec/specs/system/second-core-readiness/spec.md` capability, which this
change modifies rather than replaces.

Established facts, all source- or board-grounded:

- The K230 TRM (v0.3.1, section 1.3.2) assigns CPU0 the 800 MHz/128 KiB-L2
  little core and CPU1 the 1.6 GHz/256 KiB-L2 RVV big core. Section 1.4.1:
  BootROM starts CPU0; CPU0 controls CPU1's reset deassertion.
- `docs/evidence/cpu-readiness.txt` and `docs/evidence/second-core/*` record
  the current Linux hart reporting RVV and a 256 KiB L2, `possible`/
  `present`/`online` all `0` (i.e. only hart 0 exists in this handoff), a live
  device tree with only `cpu@0`, `CONFIG_SMP=y`/`NR_CPUS=64` compiled in but
  unused, and an OpenSBI banner reporting `Platform HART Count : 1`,
  `Domain0 HARTs : 0*`, `Platform HSM Device : ---`.
- The pinned kernel's DT (`arch/riscv/boot/dts/canaan/k230.dtsi:28-69`)
  describes one CPU; its PLIC (`:210-218`) and CLINT (`:255-259`) reference
  only that CPU's interrupt controller.
- The TRM documents real CPU1 controls — RMU `CPU1_RST_CTL` at
  `0x9110100c` (reset value `0x00002001`; bit 0 `cpu1_reset_req`; bit 4 L2
  flush request; bits 12-13 write-one-to-clear reset-done flags) and PWR
  CPU1 control/status at `0x91103018`/`0x9110301c` — but no CPU1 reset
  vector, physical hart ID, PLIC context mapping, ACLINT wiring, SBI HSM
  implementation, or CPU0/CPU1 cache-coherency contract.
- The vendor's `k230-amp.c` driver is direct evidence of a working CPU1
  release: it maps a reserved region, writes an RT-Smart image back from
  cache, programs a CPU1 reset-vector register, and performs the
  `CPU1_RST_CTL` writes — under an AMP contract (separate firmware image,
  explicit shared-buffer cache maintenance, exclusive peripheral ownership),
  not a Linux SMP one.
- `the-system-enables-proven-c908-extensions` (`system/kernel`, modified)
  makes the ordinary kernel and Pixman RVV-by-default with a physically
  proved fallback. That is the concrete reason a naive second Linux hart is
  dangerous now: today every hart Linux schedules onto is CPU1-shaped, so
  vector code paths never meet a hart that lacks V. A second hart that is
  physically CPU0 breaks that invariant silently unless scheduling accounts
  for it.

## Goals / Non-Goals

**Goals:** record the staged, evidence-gated plan as enforceable
requirements; state honestly which physical core the second hart probably
is and what kind of workload it plausibly helps; specify the two hart-
release mechanism options and what each needs before it can be chosen;
name the authorization and recovery gate every hardware-writing stage
must clear.

**Non-Goals:** adding `cpu@1` to any device tree in this change; writing to
`CPU1_RST_CTL`, the PWR CPU1 registers, or any reset-vector register in this
change; choosing between the OpenSBI-platform-start and U-Boot-spin-table
release mechanisms (an open decision for stage (b)); bringing up the vendor
RT-Smart AMP payload (a different project with a different boundary, per
`docs/research/second-core-feasibility.md` "Vendor AMP source establishes a
release contract, not SMP support"); promising a performance number before
correctness and coherency are proven, matching the acceptance discipline
`the-system-enables-proven-c908-extensions` already established for RVV.

## Decisions

1. **Layer: `tools/` read-only collection, no kernel/DT/firmware change
   (stage a).** `tools/second-core-readiness.sh` already collects CPU
   possible/present/online, the live `cpus` DT subtree, PLIC/CLINT
   `interrupts-extended`, `/proc/cpuinfo`, and SBI/SMP kernel log lines,
   entirely from files under `/sys` and `/proc` — no MMIO, no ecall, no CPU
   state change. This design adds two more read-only fields to that same
   script family, gated the same way the research doc already gates them:
   - Three register reads at `0x9110100c` (`CPU1_RST_CTL`), `0x91103018`
     and `0x9110301c` (PWR CPU1 control/status), using only the operator's
     already-proven **read-only** MMIO method (`/dev/mem` opened read-only,
     or a `devmem2`-style tool's read path). No read-modify-write, no clear
     of the W1C reset-done bits, no probe of adjacent registers. A reset
     register read is informational only: it can show whether CPU1 is
     currently held in reset, which is a fact worth having (it would falsify
     "Linux already runs on CPU1" if CPU1 reads as still fully asserted while
     Linux runs on the only enumerated hart) but it cannot itself establish
     hart identity or a release protocol.
   - A query for whether this kernel build exposes an OpenSBI HSM
     hart-status ecall through any read-only Linux-side interface (for
     example a debugfs SBI passthrough) without transitioning a Linux CPU
     up or down. If no such interface exists in this kernel, that is
     recorded as `<!-- UNVERIFIED -->`, not inferred as absent capability —
     `Platform HSM Device : ---` in the OpenSBI banner is already documented
     as informational, not an acceptance test
     (`docs/research/second-core-feasibility.md`, "OpenSBI and SMP
     barriers").
   The alternative — skipping straight to a DT edit because the silicon
   datasheet says two cores exist — is exactly what the existing
   `second-core-readiness` capability already forbids ("A second-core
   decision distinguishes handoff evidence from silicon capability").

2. **Layer: OpenSBI platform + device tree, hart-release mechanism (stage
   b, not implemented by this change).** Two candidate mechanisms, neither
   selected:
   - **OpenSBI platform code writes the release.** OpenSBI's generic
     platform (`platform/generic/platform.c` in the vendor SDK) counts harts
     from `/cpus`; a K230-specific platform module would perform the
     `CPU1_RST_CTL` deassertion and program the CPU1 reset vector itself,
     inside `hsm_start`, the same shape as the vendor `k230-amp.c` driver's
     writes but issued by firmware instead of a Linux driver, and gated by a
     verified physical hart ID and reset vector address this change does not
     yet have. This keeps the release inside the firmware layer Linux
     already trusts for HSM, at the cost of a K230-specific OpenSBI patch
     this project would carry and maintain.
   - **U-Boot releases CPU1 into a spin-table before OpenSBI/Linux start.**
     U-Boot already runs on this board pre-OpenSBI and could perform the
     reset-vector and `CPU1_RST_CTL` writes earlier, publishing a
     `riscv,spin-table` `cpu-release-addr` the way non-HSM RISC-V platforms
     do, then handing OpenSBI a device tree describing an already-parked
     hart. This avoids an OpenSBI platform patch but requires U-Boot on this
     board to gain the same CPU1-specific register knowledge, and it commits
     to spin-table rather than HSM semantics for the second hart.
   Both need the same missing prerequisite: a documented (Canaan-stated or
   read-only-register-derived) physical hart ID, reset-vector address, and
   PLIC/ACLINT context for CPU1. Per the existing capability's requirement
   ("Bring-up is gated by firmware, interrupt, and coherency evidence"),
   this change does not pick one; a later change picks one once stage (a)
   and a vendor statement or shipped source close that gap.

3. **Layer: kernel/firmware coherency validation (stage c, not implemented
   by this change).** Before any Linux shared-memory use of a second hart,
   run an atomics/litmus-style stress (concurrent load-reserve/store-
   conditional or AMO stress from both harts against shared cache lines) and
   a timer/IPI stress (repeated cross-hart IPI and ACLINT timer delivery
   under load). Neither the TRM nor the vendor SDK documents a CPU0/CPU1
   cache-coherency or atomic-sharing contract; the DT's `dma-noncoherent`
   property is documented as concerning DMA only, not CPU-to-CPU coherence.
   This stage is where that gap gets an empirical answer instead of staying
   an assumption.

4. **Layer: kernel scheduler, ISA-aware constraint (stage d, not
   implemented by this change).** Once (a)-(c) pass, Linux SMP scheduling
   is enabled only alongside one of:
   - Hard CPU affinity (`sched_setaffinity`/cpuset) that pins every task
     whose code path can execute a vector instruction to the RVV-capable
     hart, enforced at the point those tasks are spawned (systemd unit
     `CPUAffinity=`, or an equivalent cgroup/cpuset default) rather than
     left to voluntary opt-in.
   - A kernel-level per-hart-safe gate: reporting `hwprobe` capability
     per-hart instead of system-wide, so a task that checks vector
     capability before using it (the same discipline
     `the-system-enables-proven-c908-extensions` already requires of Pixman)
     gets a correct per-hart answer instead of one that is only true for the
     hart it happened to probe on.
   A blanket `nosmt`-style exclusion is the fallback if neither is ready:
   keep the second hart present but not eligible for the general scheduler,
   using it only for explicitly pinned, known-scalar workloads (network
   servicing, non-vector decode helpers, the theme helper) until affinity or
   per-hart hwprobe exists.

## Risks / Trade-offs

- **A vector-using task migrates onto a non-RVV hart** → illegal-instruction
  trap, potentially in a helper process rather than somewhere visible;
  mitigated only by decision 4's affinity/gate, which is why stage (d) is
  ordered last and is not optional.
- **A register read is treated as harmless and grows into a write** →
  decision 1 names the exact three addresses, the read-only method
  requirement, and explicitly forbids read-modify-write or clearing the
  W1C reset-done bits; the same discipline the TRM review already applied.
- **Stage (b)'s first reset/vector write hangs or corrupts the running
  system** → gated by explicit user authorization (Risk and recovery,
  below) and a rehearsed recovery path before any such write is attempted,
  on a card the operator can also pull and rewrite externally.
- **Undocumented coherency contract makes stage (c) pass by luck on one
  boot and fail on another** → stage (c) explicitly repeats the litmus and
  IPI/timer stress rather than accepting a single clean run, matching this
  project's existing standard of repeated physical measurement
  (`the-system-enables-proven-c908-extensions`'s six-run card-cost
  discipline).
- **Scope creep into the vendor AMP path** → explicitly out of scope
  (Non-Goals); this design is Linux SMP only, and the vendor AMP boundary
  (separate firmware image, reserved memory, cache-maintained shared
  buffers, mailbox protocol, exclusive peripheral ownership) is a distinct,
  larger project this change does not start.

## Migration Plan

This change lands as specification only: an updated
`system/second-core-readiness` capability recording the staged plan.
Stage (a)'s script extension is source work for a later, separately
authorized change (it touches `tools/second-core-readiness.sh`, a Nix-built
board tool, and needs its own host fixture test before any board run).
Stages (b)-(d) each become their own later change, opened only once the
preceding stage's evidence is committed under `docs/evidence/second-core/`.
No stage in this migration is reversible by "just not landing the next
change" once a reset/power register has been written on the shared board —
that is exactly why Risk and recovery in proposal.md/tasks.md requires a
rehearsed recovery path before stage (b), not after.
