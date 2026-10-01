# Live card UI: accepted scope and remaining ownership

Recorded 2026-10-01 from the project operator's conversation. Evidence classes:
physical operator report, supplemented by the already committed injected board
trials. No new camera recording, timing measurement, image build, flash or QEMU
boot was performed for this closeout.

The operator previously accepted ordinary cards, including video (see
`ordinary-cards.md`), and live card composition (see `card-composition.md`). They
also accepted coherent shell behavior and explicitly waived difficult additional
captures. After the coordinator proposed archiving the functional live card UI
while retaining failed performance budgets and unfinished full-image/non-fixture
QEMU proof in the existing performance follow-up, the operator replied:

> yeah archive cards and let's sort home and settings next plz go

This accepts the functional card entry, live deck selection, expand, close and
recovery experience. It does not supply a new per-case physical test of privacy,
close refusal, timeout, or throw reliability. Those cases retain the recorded
injected-board evidence and its limits in
`docs/evidence/card-shell/injected/README.md`,
`docs/evidence/card-shell/throw-sampling/README.md` and
`docs/evidence/card-shell/throw-fixture-sync/README.md`. Earlier failed throws
remain recorded, rather than erased by this acceptance.

## Authorized scope boundary

The archived parent `the-shell-manages-apps-as-cards` owns the functional UI,
its existing implementation/injected proof, the optional renderer decision and
this operator acceptance. Its former camera task is reconciled to this report
under the operator's capture waiver; no camera command is claimed to have run.

The existing, still-open `the-card-deck-still-misses-its-frame-budget` now owns
both original unresolved tasks in full:

- Parent 4.2: measure default Pixman composition at 568x1232 RGB565 with one and
  multiple cards; decide a measured optimization or explicit budget acceptance
  while preserving live cards, direct manipulation, selection, expansion and
  recoverable close. Its task 4.2d retains the board benchmark and panel-refresh
  capture commands. CPU/tracking budget failures remain failures; the measured
  ~57.48ms tracking p95 does not meet the 33.334ms target.
- Parent 5.1: integrate the card component into the selected real system
  configuration, cross-build its full closure and run the non-fixture
  `tools/qemu-k230.sh --card-shell-smoke`. Existing fixture success does not
  complete this gate. The successor retains the full system build command and
  dependency on resolving the budget decision.

The canonical measured-budget requirement stays UNVERIFIED for acceptance.
Archiving the functional UI is neither a performance pass nor full-image/QEMU
proof. The successor cannot archive until those requirements are resolved.

Worktree: `/home/jadams/tmp/k230-card-ui-closeout`; branch
`closeout/accepted-live-card-ui`; base
`c0e338a4f63c2f159d27cfd5ac36659c3bf9de08`. No board reservation was needed.
