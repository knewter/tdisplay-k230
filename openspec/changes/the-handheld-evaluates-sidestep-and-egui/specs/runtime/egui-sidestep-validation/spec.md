## Purpose

Provide reproducible, opt-in egui and Sidestep trials so toolkit choices for the handheld rest on observable rendering, cost and port-feasibility evidence.

## ADDED Requirements

### Requirement: The egui trial identifies its renderer and measures cost

<!-- UNVERIFIED -->
The system SHALL offer an opt-in egui Wayland client that renders on the CPU and presents through `wl_shm`, and SHALL record its egui and backend versions and that no OpenGL or Vulkan library was used. Its startup, commit interval and render-time percentiles, process and combined CPU, memory and input-to-commit proxy SHALL be recorded per matched run against the shared baseline client, with the budgets fixed before execution.

#### Scenario: The client is slower than the budget
- **WHEN** egui draws the correct scene but a declared cost gate fails
- **THEN** functional rendering is reported separately from the failed cost gate, with the failing measurements retained

#### Scenario: Only commits are observed
- **WHEN** instrumentation records surface commits without optical timing
- **THEN** the result names that boundary and does not claim input-to-photon latency

### Requirement: The Sidestep riscv64 port is assessed before it is attempted

<!-- UNVERIFIED -->
The system SHALL record, from source at a named revision, which Sidestep runtime pieces are architecture specific, their size, and whether each has a portable fallback, and SHALL state a go or no-go for a riscv64 port. A port SHALL be reported as working only with its conformance tests passing; QEMU user-mode results SHALL be labelled as such and SHALL NOT be used as performance or board evidence.

#### Scenario: The port is not bounded
- **WHEN** the assessment finds the port large or uncertain
- **THEN** the estimate is recorded, dependent board tasks remain unperformed, and no Sidestep performance is claimed

#### Scenario: The port builds but fails a test
- **WHEN** a cross-built conformance test fails under QEMU user mode
- **THEN** the failure is retained and the port is not reported as working

### Requirement: Board trials are transient and restore the session

<!-- UNVERIFIED -->
Every board trial SHALL run as transient processes under the board lock with a fixed deadline, SHALL NOT change the boot default or user settings, and SHALL record the compositor identity and boot ID before and after. Injected events, native captures, QEMU user runs and host checks MUST stay distinct evidence classes.

#### Scenario: A trial is interrupted
- **WHEN** the controller disappears or the deadline passes
- **THEN** only the owned processes are removed and the original session is verified before the lock is released
