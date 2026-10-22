## ADDED Requirements

### Requirement: A drawer scroll repaints only the scrolled band

UNVERIFIED: no installed-board measurement of this change exists yet.

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

UNVERIFIED: the tool's first committed before/after capture is pending.

The repository SHALL provide a host tool that samples the call stacks of named
systemd units on the installed board while a workload runs, under the board
lock. It SHALL produce folded stacks, a flamegraph and time-ordered sample
text. It SHALL report unit restarts during the capture. It SHALL NOT publish
journal text or network addresses.

#### Scenario: Profiling a drawer scroll

- **WHEN** an operator runs the tool for `shell-ui` and `shell` with the drawer-scroll workload
- **THEN** the host receives a flamegraph whose stacks resolve from the process entry through the shell's Rust, pango, cairo and pixman frames
