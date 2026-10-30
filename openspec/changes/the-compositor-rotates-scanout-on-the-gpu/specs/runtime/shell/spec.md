## ADDED Requirements

<!-- UNVERIFIED: no GPU rotation has run on the mainline board; the saving is an estimate from CPU profiles. -->
### Requirement: An opt-in compositor profile may rotate the output on the GPU

The compositor SHALL keep rotating its landscape frame into the portrait scanout buffer on the CPU by default. An explicitly selected profile MAY perform that rotation with VG-Lite when the source and destination are both compositor-owned and physically contiguous, and SHALL rotate each frame entirely on the GPU or entirely on the CPU, returning to the CPU for the frame on any unproved condition or error.

*Grounding (2026-10-30): `K230_PIXMAN_OUTPUT_TURN ... rotation_cpu_ns` of 3.4 ms median and rotation at 28.9% of sway's sampled CPU on drawer scroll (`docs/evidence/vglite-uses/README.md`, from `docs/evidence/interaction-jank/compositor-repaint/`); padded BGR565 scanout accepted by the GPU path in `docs/evidence/vglite-scene-board/padded/`.*

#### Scenario: Default session

- **WHEN** the shell starts without the profile
- **THEN** the compositor rotates on the CPU and never opens the GPU device

#### Scenario: GPU turn error

- **WHEN** the GPU rotation fails to complete for a frame
- **THEN** that frame is presented from the CPU rotation and the profile stays on the CPU path

#### Scenario: Measured saving

- **WHEN** the drawer-scroll workload runs under the profile and under the default on the same boot
- **THEN** the committed comparison records sway CPU and repaint wall per presented frame for both, and the profile is promoted only if it reduces them
