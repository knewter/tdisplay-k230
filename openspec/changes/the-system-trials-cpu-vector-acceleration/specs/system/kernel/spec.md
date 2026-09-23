## ADDED Requirements

### Requirement: An optional vector system trial retains the normal recovery path

*Physical grounding: `docs/evidence/card-shell/kernel-rvv/board-trial/boot1.json`, `vector-state1.json` and `trial-normal-recovery.json` record one-time trial boot, matching running identity and normal shell/Wi-Fi return with protected hashes unchanged. Earlier failed load reports and recovery are retained in the same directory.*
*Grounding for the approach: the matching kernel/system/image builds and actual boot-artifact inspection are recorded in `docs/evidence/card-shell/kernel-rvv/`; storage first/repeat boot evidence is in `docs/evidence/storage-capacity/`. Host builds do not prove a trial kernel boots.*

The system SHALL provide an explicitly selected CPU-vector trial with matching kernel, external modules, initrd and userspace. Trial preparation and one-time boot SHALL retain the known normal persistent boot selection and protected credential procedure. The operator SHALL verify artifact identity before loading the trial and verify the normal system, shell and Wi-Fi after returning. A failed load SHALL stop trial execution and attempt normal recovery while the bootloader remains available. Recovery requiring an operator reset SHALL be reported rather than claimed as automatic success.

#### Scenario: A person returns from the vector trial
- **WHEN** the operator resets after a one-time trial without selecting a new persistent system
- **THEN** the known normal system boots with its protected boot data intact
- **AND** the shell and Wi-Fi recovery are recorded separately from trial success

#### Scenario: A staged artifact cannot be verified
- **WHEN** an artifact has an unexpected identity, size or loaded-memory checksum
- **THEN** the operator does not execute the trial kernel
- **AND** the failure and observed recovery outcome are retained

### Requirement: Vector execution is gated by actual kernel and context support

*Physical grounding: `docs/evidence/card-shell/kernel-rvv/board-trial/vector-state1.json` records hwprobe value 63 and a two-process PASS with 2,000 checks per process across signals and scheduling. This is representative state proof, not exhaustive ISA coverage.*
*Grounding: `docs/evidence/card-shell/pixman-rvv/kernel-probe.json` records successful hwprobe with value 59 and no standard V bit; `docs/evidence/card-shell/kernel-rvv/context-probe/board-skip.json` records safe SKIP/77. Full-system guest context and deliberate-corruption cases are separate diagnostic proof.*

The optional vector path SHALL require the kernel's runtime capability report and physical vector computation with preserved state across asynchronous signals and process scheduling. A processor name, ISA string, successful cross-build or guest result SHALL NOT substitute for that physical evidence. If capability is absent or the state check fails, rendering SHALL retain scalar fallback and the failed or skipped result SHALL remain visible. The trial SHALL NOT force vector instructions merely to bypass a failed runtime gate.

#### Scenario: The running kernel does not expose usable standard vectors
- **WHEN** the scalar capability query omits standard vector support or returns an error
- **THEN** the diagnostic skips vector execution and rendering retains its fallback
- **AND** no acceleration result is claimed

#### Scenario: The trial advertises usable vectors
- **WHEN** the trial kernel advertises standard vector support
- **THEN** representative vector computation must survive signals and scheduling on the physical board before vector rendering is evaluated

### Requirement: A vector rendering decision includes correctness and matched cost evidence

<!-- UNVERIFIED: physical vector-rendered pixel comparisons and paired card workloads remain open. -->

The optional userspace renderer trial SHALL compare its declared pixel cases against the scalar reference and measure the same live-card workload with vector dispatch enabled and disabled on the same trial kernel. It SHALL retain frame/update, input-latency, CPU and memory measurements and all existing card interaction budgets. A compiled vector path, isolated instruction test or faster synthetic operation SHALL NOT be presented as a card-shell speedup. The recorded decision SHALL preserve negative results and distinguish an optional experiment from a default image change.

#### Scenario: Vector operations are correct but do not improve the card workload
- **WHEN** the vector pixel cases pass but matched card measurements do not improve the declared costs
- **THEN** the result records that outcome and does not claim an accepted performance improvement
- **AND** the ordinary renderer remains unchanged

#### Scenario: Vector rendering is considered for future default use
- **WHEN** the optional trial passes correctness and shows a measured benefit
- **THEN** the evidence names the workload, repeated measurements and remaining compatibility limits
- **AND** default promotion remains a separate reviewed change
