## ADDED Requirements

### Requirement: The ordinary system exposes proven vector execution with a scalar fallback

*Grounding: `docs/evidence/card-shell/kernel-rvv/board-trial/README.md` records physical hwprobe V, representative signal/scheduling preservation and normal recovery; `docs/evidence/card-shell/pixman-rvv/pixel-trial/README.md` records 192 exact physical pixel comparisons and RVV callback execution. These do not prove complete ISA coverage or card acceptance.*

The system SHALL include a matching vector-capable kernel, modules, initrd and userspace renderer in its ordinary image. The renderer SHALL require the running kernel's vector capability before executing vector instructions and SHALL retain scalar fallback and a runtime disable control. The system SHALL record exact artifact and runtime identities; a processor name, device-tree string, host build or emulated run SHALL NOT replace physical default-image proof.

#### Scenario: A person starts the ordinary system on the board
- **WHEN** the ordinary image boots and reports vector capability
- **THEN** representative vector state preservation and exact declared pixel cases are observed on the physical board
- **AND** the recorded renderer identity shows runtime-gated vector dispatch

#### Scenario: Vector capability is unavailable
- **WHEN** the kernel does not report usable vectors or the operator disables vector dispatch
- **THEN** the renderer uses its scalar path without requiring vector execution
- **AND** that fallback remains visible in the recorded result

### Requirement: Extension enablement follows an auditable evidence boundary

*Partial grounding: the pinned vendor `arch/riscv/boot/dts/canaan/k230.dtsi` lists base, vector, bit-manipulation, cache-block and supervisor extensions; `docs/evidence/card-shell/kernel-rvv/board-trial/boot1-selected.log` reports base `acdfimv` on this board. The full physical extension inventory and safe execution of every listed extension are <!-- UNVERIFIED -->.*

The system SHALL inventory useful CPU extensions named by its pinned device tree and relevant firmware, kernel, toolchain and library support. Each enabled non-baseline userspace instruction path SHALL have a supported execution environment, an appropriate runtime gate or explicit hardware restriction, and representative physical verification. The inventory SHALL explain exclusions and distinguish standard userspace instructions from privileged features, hints, and vendor-specific or version-dependent instructions. Unknown support SHALL remain explicitly unverified rather than trigger a global ISA build flag.

#### Scenario: Someone reviews an extension proposed for the ordinary image
- **WHEN** an extension is proposed for a kernel, toolchain or library path
- **THEN** its source declaration, execution privilege, runtime evidence, enablement layer and exclusion or inclusion reason are recorded

#### Scenario: An extension is not yet physically grounded
- **WHEN** source or emulation evidence exists without safe physical execution evidence
- **THEN** the inventory marks that extension unverified for default userspace use
- **AND** the ordinary image does not require it to boot

### Requirement: Default vector deployment retains physical recovery and honest workload results

*Grounding for the recovery method and measurement limits: `docs/evidence/card-shell/kernel-rvv/board-trial/README.md` and `docs/evidence/card-shell/kernel-rvv/card-cost/README.md`. The future normal-image boot and recovery are <!-- UNVERIFIED -->.*

The system SHALL stage a changed normal image through a one-time physical boot while preserving the known-good persistent selection and protected boot data. It SHALL record representative console, shell, network and card workload results without relaxing existing card budgets or calling an unproved speedup accepted. A separate return to the known-good image SHALL be observed before selecting the candidate persistently.

#### Scenario: A candidate is evaluated
- **WHEN** the new image is tried on the physical board
- **THEN** its exact artifacts, observed boot and representative workloads are recorded
- **AND** any failing budget or interaction remains visible

#### Scenario: The candidate fails or the trial ends
- **WHEN** the operator returns to the known-good persistent image
- **THEN** boot selection, protected hashes, shell and network recovery are checked and recorded separately
