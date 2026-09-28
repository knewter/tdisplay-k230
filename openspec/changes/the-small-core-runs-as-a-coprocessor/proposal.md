## Why

Right now every background job on the handheld — Wi-Fi association, a video
decode helper, the Python theme helper, a udev-triggered script — competes
with the Sway compositor for the same single Linux hart, and a person notices
it as the shell stuttering. The board's second physical core, CPU0, has sat
in `wfi` since BootROM released CPU1 into Linux
(`board/canaan/common/k230_img.c:276-285`). `the-system-runs-on-both-cores`
proposed to close that gap by letting Linux itself schedule ordinary
processes on CPU0 (SMP). After two rounds of board-grounded investigation
(`docs/research/second-core-feasibility.md`,
`docs/closeout/second-core-plan.md`), the user has now decided, on
2026-09-28, to stop pursuing that outcome and to formally redirect the
second-core project to a coprocessor (AMP) model instead: Linux keeps its one
hart, and CPU0 runs a separately loaded, explicitly managed program that
Linux talks to over shared memory, coordinated by hand, not by the scheduler.
This proposal records that redirection as the accepted plan.

The decision rests on three board-grounded facts, all already established
by the prior investigation and not reopened here:

- **Both physical cores read `CSR.MHARTID = 0`.**
  `docs/evidence/second-core/cpu0-identity-physical-trial.md` measured
  `CPU0_SPL_IDENTITY mhartid=0x0` on physical CPU0 directly, and pinned
  OpenSBI source traces the CPU1-side `Boot HART ID : 0` banner to the same
  CSR (`sbi_init.c:534,394,169`, `riscv_asm.h:166`). OpenSBI's hart table,
  its warm-entry scratch/stack selection, and its HSM/IPI targeting all
  resolve through `CSR_MHARTID` as a unique key
  (`platform/generic/platform.c:95-132`, `sbi_scratch.c:24-32`,
  `firmware/fw_base.S:441-462`, `sbi_hsm.c:300-361`); a duplicate ID breaks
  all of them before interrupts or coherency are even reached. No document in
  hand — not the TRM, not the pinned vendor overlay, not the public SDK —
  supplies a second per-core identity signal to fix this.
- **No proven cache coherency between the two cores' private L2s.** Neither
  the TRM nor the vendor SDK states a CPU0/CPU1 cache-coherency or
  shared-atomic contract; the DT's `dma-noncoherent` property
  (`arch/riscv/boot/dts/canaan/k230.dtsi:207`) is about DMA, not CPU-to-CPU
  access. The vendor's own working AMP driver
  (`k230-amp.c`) flushes shared buffers by hand around every access, and this
  project's own heartbeat payload (`tools/small-core-heartbeat.S:25-28`)
  issues the pinned `l2cache.ciall` encoding after every write for the same
  reason. A working system's own hand-flushing is adverse evidence against
  implicit coherency, not proof of an incidental one.
- **CPU0 has no vector unit; this project's kernel is RVV-by-default.**
  `the-system-enables-proven-c908-extensions` (modifying `system/kernel`)
  makes the ordinary kernel and Pixman RVV-by-default. Linux's scheduler has
  no notion of "this hart lacks an extension the running binary needs" — a
  migrated vector instruction on CPU0 traps, it does not fall back. SMP would
  need a scalar-everywhere kernel and userspace image before any workload
  became migratable, which throws away the vector work this project already
  proved.

None of this is new: `docs/closeout/second-core-plan.md`'s own
"Recommendation" section already reaches "AMP/heartbeat-style offload is the
practical route." What changes here is that the choice is now the user's
formal decision rather than an open question, and this proposal turns it
into an enforceable, staged plan the way `the-system-runs-on-both-cores` did
for SMP.

## What Changes

- Redirect the second-core objective from Linux SMP to a coprocessor (AMP)
  model: Linux enumerates one hart; CPU0 runs firmware Linux loads, starts,
  and stops through a proper Linux-side driver, communicating over an
  explicitly non-cacheable shared region.
- Record why no existing driver is reused as-is: neither the pinned vendor
  kernel nor the public `k230_sdk` has a K230 remoteproc or mailbox driver
  (confirmed by reading the pinned kernel source; see `design.md`), and the
  vendor's own `k230-amp.c` is a raw misc-device loader/reset driver, not a
  `remoteproc`/`rpmsg` consumer — its release sequence (write CPU0's
  reset-vector register, then the RMU `CPU0_RST_CTL` sequence) is reusable
  knowledge, not reusable code.
- Recommend bare-metal firmware (extending the already host- and
  board-proved `tools/small-core-heartbeat.{S,ld}`) as the first firmware
  step, over Zephyr, FreeRTOS, or the vendor's RT-Smart, on build-complexity
  and evidence grounds (`design.md`).
- Stage the work as: (0) source/register grounding, (1) the external-reader
  recovery rehearsal both parent changes already required and left open,
  (2) a step-zero echo/ping service over a polling shared-memory ring (no
  mailbox hardware dependency, since the K230 mailbox register layout is not
  yet read into this project), (3) a reserved-memory carveout and a
  read-only remoteproc driver skeleton, (4) the Linux-driven runtime
  start/stop of CPU0 (replacing the idea of patching SPL to auto-start it),
  and (5) a first useful workload: CPU0 as a liveness watchdog for Linux,
  detecting and recording a hang without itself resetting anything.
- Every task that writes a CPU0 reset, vector, or reset-controller register
  is marked `BOARD-GATED` and `AUTHORIZATION-REQUIRED` and depends on the
  recovery rehearsal, per AGENTS.md.

**Non-goals**, named explicitly per `.skills/k230-spec-change/SKILL.md`'s
proposal rule: this change does not add `cpu@1` to any device tree, does not
pursue Linux SMP in any form, does not bring up the vendor RT-Smart image,
does not pick a K230 mailbox hardware driver (its register layout is
unread), does not decide LoRa, battery/charger, or keyboard-base peripheral
ownership, and does not give CPU0 the ability to reset CPU1 or Linux
automatically — a detected hang is recorded, not acted on, in this change.

## Relationship to the two open second-core changes

Both `the-system-runs-on-both-cores` and
`the-small-core-runs-a-recoverable-heartbeat` remain open. Per AGENTS.md,
this proposal does not archive or withdraw either one; it adds a dated note
to each recording how this change relates to it, and leaves every task
unticked. The user confirms before either parent change is archived,
withdrawn, or otherwise closed.

- **`the-system-runs-on-both-cores`.** Its stage-a read-only board probes
  (tasks 1.1-1.6, already complete) and its recovery-rehearsal requirement
  (tasks 2.1/2.2, still open) are exactly the right foundation and are
  carried into this change's own task list as the same rehearsal, not
  duplicated work. Its SMP-specific stages — the OpenSBI/DT hart-release
  experiment (task 3.1/3.2), the pre-Linux coherency validation gating a
  *Linux-shared* boot (task 4.1), and ISA-aware SMP scheduling (task 5.1) —
  are obsoleted by this redirect: they exist only to make Linux itself treat
  CPU0 as a peer hart, which is no longer the goal. They are recorded as
  superseded, not deleted, not ticked, and the change stays open per
  AGENTS.md's "keep incomplete changes open" rule until the user authorizes
  archiving it (likely alongside a decision to withdraw the SMP-specific
  requirement from `system/second-core-readiness` in a later, separate
  change once this AMP work is itself landed).
- **`the-small-core-runs-a-recoverable-heartbeat`.** Its "Linux SMP is not an
  acceptance path" framing is now moot, because Linux SMP is no longer the
  target of *any* change — what this proposal wants is exactly the kind of
  independent physical execution that change already proved on the host and
  partially rehearsed. Its ready payload and host evidence
  (`tools/small-core-heartbeat.{S,ld}`, `docs/evidence/second-core/heartbeat-host.md`)
  and its board-gated tasks 3.1 (recovery rehearsal) then 3.2 (release and
  observe) are resequenced as this change's own stage-1 and stage-2 tasks, in
  that same order. Its coexistence stage (task family 4: patch the CPU0 SPL
  parking loop to run a heartbeat unconditionally after every boot) is
  **not** reused as designed: `design.md` explains that a proper
  remoteproc-shaped driver lets Linux start and stop CPU0 on demand once
  booted, which needs no stage-1/SPL change at all and is both more flexible
  and lower-risk than making CPU0 run unconditionally on every boot. That
  proposal's task family 4 is recorded as superseded by this change's stage-4
  task, not deleted.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/second-core-readiness`: turns the existing "a separate AMP path
  SHALL additionally define its firmware image, reserved memory, cache
  maintenance, mailbox protocol, and exclusive peripheral ownership" clause
  from a one-line placeholder into the actual staged, evidence-gated AMP
  bring-up plan, its authorization/recovery gate, its cache-maintenance
  contract, and the requirement that AMP execution not be read as Linux SMP
  or as an unreviewed peripheral-ownership grant.

## Impact

No boot image bytes change in this proposal. The existing heartbeat payload
and its host tooling are extended, not replaced. This proposal's own tasks
are source/documentation/design work plus, further out, board-gated
hardware-writing steps that require the still-unperformed external-reader
recovery rehearsal and the user's explicit authorization before any register
is written, exactly as AGENTS.md and the two parent changes already require.
