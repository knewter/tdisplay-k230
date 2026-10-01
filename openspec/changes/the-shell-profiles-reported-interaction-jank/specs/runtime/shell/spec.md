## ADDED Requirements

### Requirement: A cheap per-frame timing signal exists for the app drawer

<!-- UNVERIFIED: the signal is implemented, but sustained physical-board
measurement from parent task 5.2 has not been obtained. Transferred from
the-app-drawer-is-redesigned on operator-authorized closeout, 2026-10-01. -->

Whenever the app drawer route renders a frame, the userspace shell SHALL be
able to report that frame's render duration in milliseconds through its
existing log/journal output, at a bounded rate that does not flood the journal
during sustained scroll or fling. The 17.3–34.6 ms estimate and ~20 ms target
SHALL remain unmeasured until a recorded installed-board workload grounds them.

#### Scenario: An operator reads drawer frame cost from the journal

- **WHEN** an operator scrolls the drawer on the board and reads its process journal
- **THEN** a `K230_DRAWER_FRAME ms=` line appears at least once every few hundred milliseconds, reporting that frame's own render duration
- **AND** the record distinguishes client paint cost from presentation latency

### Requirement: Reported slow shell interactions are evaluated with measured evidence

<!-- UNVERIFIED: deferred board measurements; accepted functional reports
are not quantitative performance proof. -->

When investigating a reported slow interaction, the userspace shell's analysis
SHALL name the workload and installed identities and compare measured results
with the applicable existing shell responsiveness budgets. Keyboard visibility,
held/reversed drag and release settlement, and ordinary-card sub-400ms entry
and sub-100ms touch acknowledgement SHALL remain pending measurement;
static captures and qualitative acceptance SHALL NOT substitute for those
results. A failed budget SHALL remain a failed budget. Drawer damage-limited
blitting SHALL be proposed only if measurement justifies that next change.

#### Scenario: A keyboard interaction is reported slow

- **WHEN** an operator reports slow show, drag or hide behavior
- **THEN** its exact workload is measured using installed compositor instrumentation and compared with the existing budgets, with commands and limits committed

#### Scenario: Drawer scrolling misses the measured target

- **WHEN** the sustained drawer workload demonstrates a relevant rendering shortfall
- **THEN** the analysis records it and proposes a measured optimization follow-up, considering scroll-direction damage-limited blitting

#### Scenario: An ordinary-card interaction is reported slow

- **WHEN** entry or touch handling is reported slow with a live video or busy non-video app
- **THEN** the installed workload is measured against the retained entry and acknowledgement targets using real contact or persistent uinput injection
- **AND** per-sample subprocess overhead is not represented as compositor latency
