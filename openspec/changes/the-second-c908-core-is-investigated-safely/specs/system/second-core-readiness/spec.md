## Purpose

Preserve the working single-hart handheld while giving operators a reproducible,
read-only basis for deciding whether a future second-core project is safe.

## ADDED Requirements

### Requirement: Second-core evidence is collected without changing execution state

The system SHALL provide a board-side collection command that reads Linux CPU
state, the live CPU and interrupt device-tree descriptions, and already emitted
SBI/SMP kernel messages without writing MMIO, changing CPU online state, loading
modules, or invoking a reset, power, mailbox, or HSM start operation.

#### Scenario: Coordinator collects a readiness snapshot

- **WHEN** the coordinator runs the documented collection command on a known-good board
- **THEN** it emits a timestamped snapshot containing only read-only CPU, device-tree, and kernel-log data, and leaves the running shell and its CPU state unchanged

### Requirement: A second-core decision distinguishes handoff evidence from silicon capability

The project SHALL record whether stage 1 and the live device tree enumerate a
second hart separately from vendor claims about two physical C908 cores. It
MUST NOT identify a Linux logical hart with a physical core from CPU count alone
or treat a compiled SBI HSM extension as proof that another hart can start.

#### Scenario: One-hart firmware handoff is observed

- **WHEN** the OpenSBI banner, live `/cpus` tree, and Linux CPU masks each describe one hart
- **THEN** the decision records second-core Linux SMP as blocked rather than proposing a guessed `cpu@1` node or a hart release

### Requirement: Bring-up is gated by firmware, interrupt, and coherency evidence

Before a later change may release a second core for Linux SMP, it SHALL have
source- or board-grounded evidence for the second hart ID and reset/vector
protocol, OpenSBI domain/HSM behavior, local timer and IPI/PLIC routes, CPU ISA
and cache description, and a CPU-to-CPU shared-memory coherency contract. A
separate AMP path SHALL additionally define its firmware image, reserved memory,
cache maintenance, mailbox protocol, and exclusive peripheral ownership.

#### Scenario: A prerequisite remains undocumented

- **WHEN** the reset/vector protocol, interrupt route, or coherency contract has not been established
- **THEN** the project retains the single-hart image and records the missing evidence and safe next action without attempting a core release
