## ADDED Requirements

### Requirement: A staged, evidence-gated bring-up plan exists before any second-hart execution is attempted

<!-- WITHDRAWN 2026-09-28: this requirement stages Linux SMP bring-up
specifically, which the user has formally redirected away from
(`the-small-core-runs-as-a-coprocessor`, citing `docs/closeout/second-core-
plan.md`'s recommendation). Kept here, not deleted, as the historical
record of what was staged and why it is no longer pursued; the analogous
AMP bring-up plan lives in the successor's own "The coprocessor stage
follows a staged, evidence-gated AMP bring-up plan" requirement. -->

*Grounding: `docs/research/second-core-feasibility.md`'s "minimal recoverable experiment" and "passive handoff audit" sections define the ordering this requirement records; `docs/evidence/second-core/README.md` records that today's readiness investigation is complete while second-core enablement is not.*

The project SHALL stage Linux SMP bring-up as read-only board/source probes, a pre-Linux CPU0/CPU1 coherency and identity diagnostic, a guarded OpenSBI-plus-device-tree hart-release experiment, and common-ISA Linux scheduling. Linux currently runs on physical CPU1; the target is physical CPU0. It SHALL NOT boot a shared Linux kernel on both cores before identity, interrupt/timer routing, and shared-memory coherence are grounded. Read-only probes SHALL NOT write MMIO, invoke a reset/power/mailbox/HSM operation, or change CPU online state. Only the guarded diagnostics and release phase SHALL write a reset or power register, after the recovery prerequisite below is met. A separate CPU0 payload does not meet this requirement.

#### Scenario: A phase is proposed out of order

- **WHEN** a change proposes a device-tree `cpu@1` node, a reset-register write, or SMP scheduling before the preceding phase's board evidence is committed
- **THEN** the change is not authorized to proceed, and the missing phase's evidence is named as the blocker

#### Scenario: Read-only probes are extended

- **WHEN** a new read-only field is added to the board's second-core collection tooling
- **THEN** it is verified against a host fixture before any board run, and the board run itself performs no MMIO write, reset, power, mailbox, or HSM operation

### Requirement: Second-hart scheduling accounts for heterogeneous ISA before it is enabled

<!-- WITHDRAWN 2026-09-28: Linux SMP scheduling across two harts is no
longer pursued; see the withdrawal note on the preceding requirement. Kept
as historical record, not deleted. -->

*Grounding: the K230 TRM section 1.3.2 assigns RVV 1.0 to CPU1 only; `the-system-enables-proven-c908-extensions` (modifying `system/kernel`) makes the ordinary kernel and Pixman RVV-by-default with a runtime capability gate. `docs/evidence/cpu-readiness.txt` records the current single Linux hart reporting RVV; if the second hart is the non-RVV core, as the current inference suggests, a kernel built with V compiles instructions that trap on a hart lacking that extension.*

For initial Linux SMP scheduling, the project SHALL use a scalar common-ISA kernel and userspace image with RVV execution disabled so ordinary unpinned processes can run on either physical core. It SHALL NOT enable unconstrained scheduling across two harts while the kernel or userspace may execute RVV on the non-RVV CPU0. A later RVV-capable image requires a proven per-hart scheduling and userspace capability contract; affinity for selected processes alone is insufficient for the ordinary migratable workload.

#### Scenario: A second hart is released without an ISA-aware scheduling constraint

- **WHEN** a released second hart lacks RVV and the image can execute RVV in ordinary migratable code
- **THEN** that hart is not made eligible for the general Linux scheduler, and the missing constraint is recorded as the blocker

#### Scenario: A vector-using task is dispatched under an ISA-aware constraint

- **WHEN** the scalar common-ISA image runs ordinary unpinned tasks repeatedly under scheduling pressure
- **THEN** both Linux CPUs execute those tasks and zero illegal-instruction traps are observed across the recorded repeats

### Requirement: A hart-release write requires explicit authorization and a rehearsed recovery path

<!-- WITHDRAWN 2026-09-28 as an SMP hart-release requirement (see the
withdrawal note on the first requirement in this file): no `cpu@1`
hart-release write is pursued. Its underlying recovery obligation is also
superseded on its own terms by a further 2026-09-28 operator waiver: "we
can easily fix the sd card damn. don't worry about recovery we've
literally done that fine already before. i don't want to do a heartbeat
test on a spare card." No spare/disposable card or external-reader
rehearsal is required for this project's second-core work; the fallback is
the proven U-Boot one-shot/`ums`/reimaging routes on the normal card. The
analogous, currently-live requirement for AMP register writes is the
successor's own "A CPU0 register write requires explicit authorization and
a proven fallback recovery route." Kept here as historical record, not
deleted. -->

*Grounding: pinned U-Boot `arch/riscv/cpu/k230/cpu.c:125-160` defines CPU0 reset/vector writes and `nix/stage1.nix:176-180` puts SPL at raw SD-card offsets. `docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md` records a U-Boot one-shot recovery for a Linux boot failure, while `docs/uboot-ums.md` documents external card-reader and U-Boot `ums` routes.*

Before any change writes a CPU0 reset, power, or reset-vector register, the board operator SHALL have the user's explicit authorization for that session. Recovery, if a write fails or hangs the board, SHALL use the already-proven U-Boot one-shot boot from `boot-prev` or `ums`/flash reimaging, on the normal card; no separate spare or disposable card SHALL be required.

#### Scenario: A register write is attempted without authorization

- **WHEN** the operator has not obtained the user's explicit authorization for the current board session
- **THEN** the reset/power register write does not proceed

#### Scenario: A hart-release write fails or hangs the board

- **WHEN** the CPU1 release write does not produce the expected second enumerated hart
- **THEN** the operator restores the board using the U-Boot one-shot or `ums`/flash reimaging route and records the outcome separately from the release attempt's own result
