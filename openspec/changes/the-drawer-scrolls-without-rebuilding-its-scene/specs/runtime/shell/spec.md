## ADDED Requirements

### Requirement: A drawer scroll repaints only the scrolled band

*Grounding (2026-10-22): `docs/evidence/interaction-jank/drawer-profile/README.md`. On test-activated `z1basiwi…` in landscape, with injected native touch and no real glass, contact render had a median of 6.3 ms and sway received band-only damage. The fixed rebuild count is proven only by a host unit test. Persistent installation and portrait are unmeasured.*

When only the app drawer's scroll offset changes between frames, the userspace
shell SHALL repaint just the scrollable grid band of its cached frame. It SHALL
NOT rebuild the drawer's chrome, sheet or background. The repainted band SHALL
match a full rebuild at the same offset. The shell SHALL NOT resample the
cached grid per frame, and SHALL NOT reshape unchanged layout text on every
draw.

#### Scenario: A sustained drawer scroll

- **WHEN** a person drags the drawer's app grid with no tile pressed
- **THEN** each scroll frame repaints only the grid band, and the renderer's rebuild count does not grow
- **AND** the presented pixels equal a full rebuild at that scroll offset

### Requirement: An operator can capture a CPU flamegraph of a board workload

*Grounding (2026-10-22): `tools/board-profile.py` captures in `docs/evidence/interaction-jank/drawer-profile/` (profile-before, after1, after2).*

The repository SHALL provide a host tool that samples the call stacks of named
systemd units on the installed board while a workload runs, under the board
lock. It SHALL produce folded stacks, a flamegraph and time-ordered sample
text. It SHALL report unit restarts during the capture. It SHALL NOT publish
journal text or network addresses.

#### Scenario: Profiling a drawer scroll

- **WHEN** an operator runs the tool for `shell-ui` and `shell` with the drawer-scroll workload
- **THEN** the host receives a flamegraph whose stacks resolve from the process entry through the shell's Rust, pango, cairo and pixman frames
