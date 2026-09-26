## ADDED Requirements

### Requirement: A staged, evidence-gated bring-up plan exists before any second-hart execution is attempted

*Grounding: `docs/research/second-core-feasibility.md`'s "minimal recoverable experiment" and "passive handoff audit" sections define the ordering this requirement records; `docs/evidence/second-core/README.md` records that today's readiness investigation is complete while second-core enablement is not.*

The project SHALL stage second-core bring-up as four ordered phases — read-only board probes, an OpenSBI-plus-device-tree hart-release experiment, coherency validation, and ISA-aware SMP scheduling — and SHALL NOT begin a later phase before the preceding phase's board evidence is committed under `docs/evidence/second-core/`. Read-only probes SHALL NOT write MMIO, invoke a reset/power/mailbox/HSM operation, or change CPU online state. Only the hart-release experiment phase SHALL write a reset or power register, and only after the interrupt-routing and reset-vector prerequisite in the existing "Bring-up is gated by firmware, interrupt, and coherency evidence" requirement is met.

#### Scenario: A phase is proposed out of order

- **WHEN** a change proposes a device-tree `cpu@1` node, a reset-register write, or SMP scheduling before the preceding phase's board evidence is committed
- **THEN** the change is not authorized to proceed, and the missing phase's evidence is named as the blocker

#### Scenario: Read-only probes are extended

- **WHEN** a new read-only field is added to the board's second-core collection tooling
- **THEN** it is verified against a host fixture before any board run, and the board run itself performs no MMIO write, reset, power, mailbox, or HSM operation

### Requirement: Second-hart scheduling accounts for heterogeneous ISA before it is enabled

*Grounding: the K230 TRM section 1.3.2 assigns RVV 1.0 to CPU1 only; `the-system-enables-proven-c908-extensions` (modifying `system/kernel`) makes the ordinary kernel and Pixman RVV-by-default with a runtime capability gate. `docs/evidence/cpu-readiness.txt` records the current single Linux hart reporting RVV; if the second hart is the non-RVV core, as the current inference suggests, a kernel built with V compiles instructions that trap on a hart lacking that extension.*

Before Linux SMP scheduling is enabled across a released second hart, the project SHALL have in place at least one of: hard CPU affinity keeping vector-using code paths off a non-RVV hart, a kernel-level per-hart capability gate so vector-dependent code observes the executing hart's own extension support rather than a system-wide value, or an explicit exclusion of the second hart from the general scheduler. The project SHALL NOT enable unconstrained scheduling across two harts of differing ISA while the default kernel and userspace assume every hart has RVV.

#### Scenario: A second hart is released without an ISA-aware scheduling constraint

- **WHEN** a released second hart lacks RVV and no affinity, per-hart capability gate, or scheduling exclusion has been verified on the board
- **THEN** that hart is not made eligible for the general Linux scheduler, and the missing constraint is recorded as the blocker

#### Scenario: A vector-using task is dispatched under an ISA-aware constraint

- **WHEN** the verified affinity or per-hart gate is active and a synthetic vector-using task runs repeatedly under scheduling pressure
- **THEN** it does not execute on a hart lacking RVV, and zero illegal-instruction traps are observed across the recorded repeats

### Requirement: A hart-release write requires explicit authorization and a rehearsed recovery path

*Grounding: the TRM documents `CPU1_RST_CTL` (RMU `0x9110100c`) and PWR CPU1 control/status (`0x91103018`/`0x9110301c`) as real, writable state whose reset value and W1C bits make a speculative write an actual reset/power transition, not a probe. `docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md` records a proven U-Boot one-shot recovery from `/var/lib/k230/boot-prev` used 2026-09-25; `docs/uboot-ums.md` records an independent SD card-reader / U-Boot `ums` recovery route.*

Before any change writes a CPU1 reset, power, or reset-vector register, an operator SHALL have explicit user authorization for that specific write, and SHALL have rehearsed and confirmed on the board, in that session, at least one working recovery path: the U-Boot one-shot boot from `/var/lib/k230/boot-prev` with a matching `SHA256SUMS` check, or the SD card-reader / U-Boot `ums` fallback. The experiment SHALL run only against a disposable rollback card, never the board's only working card, until the release mechanism is proven.

#### Scenario: A register write is attempted without rehearsed recovery

- **WHEN** no recovery path has been rehearsed and confirmed working in the current board session
- **THEN** the reset/power register write does not proceed

#### Scenario: A hart-release write fails or hangs the board

- **WHEN** the CPU1 release write does not produce the expected second enumerated hart
- **THEN** the operator restores the board using the rehearsed recovery path and records the outcome separately from the release attempt's own result
