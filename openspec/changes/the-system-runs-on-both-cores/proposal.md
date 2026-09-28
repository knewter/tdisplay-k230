## Why

**2026-09-28 scope decision — Linux SMP redirected to AMP, this change stays
open.** The user has now formally decided against the Linux SMP outcome
this change describes and redirected the second-core project to a
coprocessor (AMP) model instead; see
`the-small-core-runs-as-a-coprocessor/proposal.md` for the decision and its
grounding. This change is **not** archived or withdrawn by that decision —
per AGENTS.md, only the user's explicit confirmation closes it, and every
task below stays exactly as ticked or unticked as it was. What changes is
which of its stages remain live work: stage (a)'s read-only board probes
(tasks 1.1-1.6, complete) and the recovery rehearsal (tasks 2.1/2.2, still
open) are the shared foundation and are carried into the new change's own
task list rather than duplicated. Stage (b)'s OpenSBI/DT hart-release
experiment (tasks 3.1/3.2), stage (c)'s pre-*Linux-shared-boot* coherency
validation (task 4.1), and stage (d)'s ISA-aware **SMP scheduling**
(task 5.1) are recorded as superseded: they exist only to make Linux itself
address CPU0 as a peer hart, which is no longer the goal. They are not
deleted, not ticked, and not claimed done — they remain honestly open,
pending the user's decision on whether to archive this change once the AMP
work has landed.

**2026-09-26 source correction.** Pinned stage 1 boots Linux on physical
CPU1 (the large, RVV-capable core):
`board/canaan/common/k230_img.c:276-285` releases CPU1 from CPU0, then
parks CPU0. The extra Linux CPU sought here is physical CPU0. The current
device-tree `cpu@0` and OpenSBI hart 0 name Linux's *logical* hart, not the
physical CPU0. This proposal remains the Linux SMP objective: both physical
cores must appear as Linux CPUs and ordinary scalar processes must be
schedulable on either. The separate CPU0 heartbeat/AMP proposal is suspended;
it does not satisfy this objective.

The [K230 QEMU board author](https://www.mail-archive.com/qemu-devel@nongnu.org/msg1188749.html)
reports that both physical cores read `mhartid=0`; the [Linux DTS author](https://lkml.rescloud.iu.edu/2403.3/00159.html)
reports that physical CPU1 reads 0 and that inter-core coherence is unknown.
Those are firsthand reports, not measurements on this board. In pinned
OpenSBI 1.4, `platform/generic/platform.c:95-132` reads DT `reg` for each
hart, while `lib/sbi/sbi_scratch.c:24-32` returns the first table entry for
a given hart ID and `include/sbi/riscv_asm.h:166` reads `CSR_MHARTID` for
the current hart. If the duplicate ID is confirmed, adding `cpu@1` cannot
work: a K230-specific identity scheme must first be proven end-to-end in
OpenSBI, its HSM/IPI/timer paths, and Linux's CPU entry path. The normal
boot image remains unchanged while this is investigated.

Right now every background job — Wi-Fi association, a video decode helper, a
Python theme helper, a udev-triggered script — competes with the Sway
compositor for the same single hart. A person notices this as the shell
stuttering while the theme helper regenerates a wallpaper cache, or a decode
helper stealing frames from the compositor during a card animation. A second
usable hart would let that background work run without taking cycles from the
thing being looked at.

Be honest about what that second hart actually is. `docs/evidence/cpu-readiness.txt`
records the current Linux hart reporting RVV and a 256 KiB L2; the K230 TRM
section 1.3.2 assigns exactly that RVV/256 KiB profile to the 1.6 GHz CPU1.
Pinned stage-1 release source and the live ISA/cache observation establish
that Linux runs on physical CPU1, although this board's `mhartid` value has
not been measured in M-mode. **The second core is the 800 MHz little core**,
not a matching twin of the one running the shell today. Plain-terms benefit:
a background core for decode assistance, network/SDIO servicing, Python
helpers and the theme helper, run at half the clock of the compositor's core
and — per the TRM's CPU0/CPU1 split — without a vector unit. It is a place to
put work that should not stall the display, not a second compositor engine
and not a path to double interactive throughput.

That last property is also the main hazard. This project's kernel now
carries an RVV path by default (`the-system-enables-proven-c908-extensions`,
modifying `system/kernel`: "the ordinary system uses physically proved
vectors"). A kernel built with V compiles vector instructions into library
and userspace code paths that assume the executing hart has RVV. RISC-V does
not require every hart in an SMP system to share the same instruction-set
extensions, and this SoC's own two cores do not: CPU1 has RVV 1.0, CPU0 does
not (K230 TRM section 1.3.2; `docs/research/second-core-feasibility.md`).
Linux's generic scheduler has no built-in concept of "this hart lacks an
extension the running binary needs" — a task or library call that uses a
vector instruction, migrated onto a hart without RVV, takes an illegal-
instruction trap, not a graceful fallback. Any SMP plan for this board is
therefore a heterogeneous-ISA scheduling problem before it is a throughput
problem.

## What Changes

The normal boot image does not add a `cpu@1` node, write a reset or power
register, or change OpenSBI, U-Boot, or the kernel. A separately selected,
default-off SPL diagnostic has been built on the host and packaged for a
possible board trial; it is not installed. This change records a staged, evidence-gated
plan and the decision-quality bar each stage must clear before the next one
is attempted, matching `.skills/k230-spec-change/SKILL.md`'s grounding order
and `docs/research/second-core-feasibility.md`'s "minimal recoverable
experiment" and "passive handoff audit" sections:

- **(a) Read-only board probes.** No reset, power, or CPU-state write.
  Extend the existing read-only collector
  (`tools/second-core-readiness.sh`) to add the two documented read-only RMU/
  PWR register reads (`0x9110100c`, `0x91103018`, `0x9110301c` — TRM sections
  2.1.4 and 2.3.4) taken with a proven read-only MMIO method, and record
  whether the kernel exposes an OpenSBI HSM hart-status query without a
  Linux CPU up/down transition. Cross-check `/proc/cpuinfo`'s `misa`/`uarch`
  and the live L2 size against the TRM's CPU0/CPU1 table to sharpen, not
  replace, the existing inference.
- **(b) An OpenSBI + device-tree experiment.** First establish physical
  CPU0's `mhartid`, its known CPU0 reset vector/release controls, and
  per-core PLIC/ACLINT or other usable IPI/timer routing. If the two
  physical cores share `mhartid=0`, prove an alternate unique logical
  identity from early M-mode through OpenSBI HSM, IPI, timer and Linux CPU
  entry; DT `reg = <1>` alone is insufficient. Only then prepare a guarded
  CPU0 release and two-CPU Linux DT. This stage is the first one that may
  write a reset register and requires the recovery rehearsal below.
- **(c) Coherency validation.** Establish a CPU0/CPU1 shared-memory and
  atomic contract before the Linux kernel shares page tables, locks and
  runqueues across both cores. A bounded pre-Linux diagnostic may test it;
  Linux SMP itself must not be the first coherency test. The vendor AMP
  driver's explicit cache maintenance is adverse evidence, not proof that
  ordinary cached Linux SMP is safe.
- **(d) Common-ISA SMP scheduling.** The initial two-CPU image must use a
  scalar common ISA baseline across kernel and userspace, with RVV execution
  disabled while ordinary processes can migrate between cores. Per-hart RVV
  use is later optimization work requiring a proven scheduler/userspace
  contract. CPU affinity alone cannot protect every ordinary process in an
  RVV-by-default image.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/second-core-readiness`: records the staged evidence-gated bring-up
  plan itself — what each stage requires before the next may start, which
  stages write hardware state, and the heterogeneous-ISA scheduling
  constraint — as requirements the project is held to, not only a readiness
  snapshot.

## Impact

The existing read-only collector has host fixtures and a partial board
capture; two PWR reads returned EPERM and remain unproven. This change also
adds a default-off `uboot-k230-cpu0-identity-probe` and a BootROM-loadable
`stage1-cpu0-identity-probe` package. Its source and host build evidence
are in `docs/evidence/second-core/`; the ordinary U-Boot and stage-1
derivations are unchanged. No experimental SPL has been installed, no CPU0
CSR has been measured on the board, and no second Linux CPU is enabled.
The physical trial awaits the current card's verified raw-stage-1 backup
and external reader recovery route, then a board-operator session. Later
OpenSBI, DT and kernel work awaits identity, interrupt and coherency proof.
