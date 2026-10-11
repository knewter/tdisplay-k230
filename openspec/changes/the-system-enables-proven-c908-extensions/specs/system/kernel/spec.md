## ADDED Requirements

### Requirement: The ordinary system exposes proven vector execution with a scalar fallback

*Grounding: `docs/evidence/card-shell/kernel-rvv/board-trial/README.md` records physical hwprobe V, representative signal/scheduling preservation and normal recovery; `docs/evidence/card-shell/pixman-rvv/pixel-trial/README.md` records 192 exact physical pixel comparisons and RVV callback execution. `docs/evidence/cpu-extensions/installed-mainline-2026-10-11/README.md` records the installed mainline ordinary system's identities, physical vector context, 192 equal pixel cases, mapped RVV Pixman and its scalar control. These do not prove complete ISA coverage or card acceptance.*

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

*Partial grounding: the pinned vendor `arch/riscv/boot/dts/canaan/k230.dtsi` lists base, vector, bit-manipulation, cache-block and supervisor extensions; `docs/evidence/card-shell/kernel-rvv/board-trial/boot1-selected.log` reports base `acdfimv` on this board. `docs/evidence/cpu-extensions/README.md` records the inventory and decisions, and `docs/evidence/cpu-extensions/installed-mainline-2026-10-11/README.md` records physical Zba/Zbb/Zbc/Zbs single-opcode execution on the mainline system. Safe default use of every listed extension remains <!-- UNVERIFIED -->.*

The system SHALL inventory useful CPU extensions named by its pinned device tree and relevant firmware, kernel, toolchain and library support. Each enabled non-baseline userspace instruction path SHALL have a supported execution environment, an appropriate runtime gate or explicit hardware restriction, and representative physical verification. The inventory SHALL explain exclusions and distinguish standard userspace instructions from privileged features, hints, and vendor-specific or version-dependent instructions. Unknown support SHALL remain explicitly unverified rather than trigger a global ISA build flag.

#### Scenario: Someone reviews an extension proposed for the ordinary image
- **WHEN** an extension is proposed for a kernel, toolchain or library path
- **THEN** its source declaration, execution privilege, runtime evidence, enablement layer and exclusion or inclusion reason are recorded

#### Scenario: An extension is not yet physically grounded
- **WHEN** source or emulation evidence exists without safe physical execution evidence
- **THEN** the inventory marks that extension unverified for default userspace use
- **AND** the ordinary image does not require it to boot

### Requirement: Default vector deployment retains a recovery route and honest workload results

*Grounding: `docs/evidence/cpu-extensions/installed-mainline-2026-10-11/README.md` records the installed mainline ordinary system's physical pixel/context proof, paired card workloads and a read-only check of its preserved rollback route. `docs/evidence/omarchy-themes/installed-consumers-2026-10-10/README.md` records how that system became persistent: one-time candidate boot, rollback roots and verified ordinary autoboot. A physical return to the earlier image was not exercised for this change (operator decision, 2026-10-11) and remains <!-- UNVERIFIED -->.*

The system SHALL reach a persistent vector-capable image only through a deployment that preserves a known-good rollback selection and protected boot data. It SHALL record representative console, shell, network and card workload results on the installed image without relaxing existing card budgets or calling an unproved speedup accepted. The preserved rollback route SHALL be checked and recorded on the board.

#### Scenario: The vector image is evaluated
- **WHEN** the vector-capable ordinary image runs on the physical board
- **THEN** its exact artifacts, observed boot and representative workloads are recorded
- **AND** any failing budget or interaction remains visible

#### Scenario: The vector image must be abandoned
- **WHEN** the operator needs to return to the preserved earlier selection
- **THEN** the rollback roots, staged boot-file backups and protected boot hashes it depends on have been recorded as intact
