## Final scope (2026-10-01)

The operator authorized functional UI archive and transfer of unresolved budget
and integrated image/QEMU work to the existing performance successor. The
completed handoff tasks below replace the original measurement/boot tasks;
their original requirements remain unchecked in the successor. Historical
progress notes below describe the evidence state at their recorded revisions,
not current ownership. See `docs/evidence/proposal-closeout/2026-10-01/live-card-ui.md`.

## 1. Decisions and interaction contract

- [x] 1.1 Land and review the composition-boundary decision from `the-shell-has-a-card-composition-plan`; record the chosen owner, live-surface eligibility, input/focus handoff, privacy behavior, and failure boundary in this change before implementing live capture or composition; verify with `openspec validate the-shell-has-a-card-composition-plan --strict` and review its committed evidence.
- [x] 1.2 Read the landed and archived `the-handheld-has-a-coherent-ux-plan` findings and record the accepted card hierarchy, direct-manipulation behavior, and throw-close feedback in this change; verify the resulting interaction contract with `openspec validate docs/handheld-ux-plan --type spec --strict` and the committed coordinator review in `docs/research/handheld-ux/design-review.md`. This does not wait for all audit successor changes.

## 2. Card state and recovery model

- [x] 2.1 Implement a host-testable card-deck state model for enter, shrink, horizontal drag, release/expand, unavailable/private state, graceful-close request, refusal, timeout, and restore; verify with `python3 tests/test_card_shell_state.py`. Coordinator proof: `docs/evidence/card-shell-policy-host.md`.
- [x] 2.2 Implement global edge-gesture entry from an arbitrary eligible running application and a persistent button entry/recovery route, while retaining Apps, Windows/Home, Keyboard, System, Help, terminal, monitor, and Back semantics; verify with the proposed-to-create `python3 tests/test_card_shell_recovery.py` plus existing `python3 tests/test_touch_menu.py`.

## 3. Selected live composition boundary

- [x] 3.1 Implement the live-content source and card compositor chosen by task 1.1, including explicit eligibility and a non-live private/unavailable card; verify with the proposed-to-create `python3 tests/test_card_shell_composition.py` using eligible and denied fixture surfaces.
- [x] 3.2 Implement direct finger-following deck movement, tap-to-expand, and upward graceful-close request with bounded refusal/timeout recovery; verify with the proposed-to-create `python3 tests/test_card_shell_gestures.py` and native test surface traces.
- [x] 3.3 Package only the chosen userspace component and its declared dependencies; verify the proposed-to-create narrow derivation with `nix build .#card-shell` and record its closure difference from the current system.

## 4. Cost decision

- [x] 4.1 Declare card interaction frame/update, input-to-visible-update, and incremental-memory budgets before acceptance; implement the proposed-to-create `tools/card-shell-benchmark.py` and verify its parser with `python3 tools/card-shell-benchmark.py --self-test`.
- [x] 4.2 Preserve the unresolved native Pixman budget measurement/decision in `the-card-deck-still-misses-its-frame-budget` tasks 4.2a–e under the operator-authorized 2026-10-01 scope split. Verify the retained criteria/commands and ownership against `docs/evidence/proposal-closeout/2026-10-01/live-card-ui.md` and `openspec validate the-card-deck-still-misses-its-frame-budget --strict`. This is a completed scope handoff, not a passing measurement.
- [x] 4.3 Decide and record whether to pursue the optional VGLite path. If pursued, measure it against the same workload without making it a prerequisite for Pixman acceptance; verify with the proposed-to-create `python3 tools/card-shell-benchmark.py --board --renderer vglite --output docs/evidence/card-shell/vglite.json`. If not pursued, record that decision in the Pixman evidence so this optional path does not remain an archive gate.

## 5. Integration and board acceptance

- [x] 5.1 Preserve the unperformed integrated full-closure build and non-fixture `tools/qemu-k230.sh --card-shell-smoke` in the existing performance successor task 5.1 under the operator-authorized split. Verify retained build/QEMU commands and dependency against `docs/evidence/proposal-closeout/2026-10-01/live-card-ui.md`. No image or non-fixture boot success is claimed.
- [x] 5.2 On the physical board, record native captures and injected-touch evidence for two eligible cards, horizontal deck movement, tap-to-expand, unavailable/private state, close refusal, timeout recovery, and every persistent control route; verify with the proposed-to-create `python3 tools/card-shell-acceptance.py --execute --provenance injected-touch --output docs/evidence/card-shell/injected`.
- [x] 5.3 Commit the operator acceptance of the functional live-card UI, reconciled to their explicit waiver of difficult additional captures, alongside prior injected-board proof and unreported-case limits. Verify `docs/evidence/proposal-closeout/2026-10-01/live-card-ui.md` against `ordinary-cards.md`, `card-composition.md` and the operator closeout instruction. No new real-touch camera trial is claimed.

## 6. Proposal validation

- [x] 6.1 Validate this change and preserve all unresolved hardware requirements as unverified until their named evidence exists; verify with `openspec validate the-shell-manages-apps-as-cards --strict`. Passed 2026-09-28 on `close/shell-umbrella`. Each requirement's marker now names its injected-touch or failing board-cost evidence and keeps real-finger use and the budget decision UNVERIFIED (tasks 4.2 and 5.3). Validation must be rerun before archive.

Host implementation evidence for tasks 2.2 and 3.1–3.3: `docs/evidence/card-shell/headless/README.md`. Actual compositor runtime and narrow build pass; diagnostic headless frame-interval budget fails and isolated session memory is incomplete. Product board cost, every physical control route, image integration, and real-finger acceptance remain open in groups 4–5.

Coordinator reran the final adapter through actual wlroots touch routing (17
checks) and the independent native Wayland receiver pairing suite (7 checks).
Review and exact artifacts: `docs/evidence/card-shell/coordinator-review.md`.
Budget declaration/parser and actual producer integration complete 4.1; the
recorded headless cadence failure and all board cost/physical gates remain open.

Task 5.2: `docs/evidence/card-shell/injected/README.md` records thirteen observed
injected interaction checks and coordinator review of native captures from the
opt-in product package on DSI-1 RGB565. Both live parent/child surfaces are
visible during a held drag, expansion/privacy/close recovery and persistent
controls are covered, and normal-shell restoration passed. The first failed
trial remains committed. The repeat uses the old telemetry producer, so cost
parsing still rejects it; tasks 4.2, 5.1 and 5.3 remain open.

Task 4.2 remains open: `docs/evidence/card-shell/board-cost/long-trace/README.md`
records adequate frame coverage but failed CPU/tracking budgets. Twelve repeated
interaction checks were observed; upward throw missed once, so repeatability
also remains unresolved despite the earlier successful task 5.2 evidence.

The source-timestamp correction now has a failing old-adapter negative control,
passing delayed-input/native-routing tests and one board repeat observing all
13 interaction checks. `docs/evidence/card-shell/touch-timestamps/board/README.md`
retains the repeat's still-failing frame costs. Tasks 4.2, 5.1 and 5.3 stay open;
one injected repeat does not establish physical throw reliability.

The repeated-millisecond velocity correction is independently reproduced against
old policy/runtime and passes new sanitizer/native-routing checks. Three normal
board repeats observe all 13 injected checks apiece; evidence and retained
budget failures are in `docs/evidence/card-shell/throw-sampling/README.md`.
This does not establish historical failure attribution or physical-finger
reliability. Tasks 4.2, 5.1 and 5.3 remain open.

The following repaint-stage profile correlates all 268 submitted board frames
and attributes about 98% of repaint CPU to output-state construction/painting.
`docs/evidence/card-shell/repaint-stages/README.md` records both failed cost
budgets and a renewed upward-throw check failure (12/13 observed checks), with
successful normal-system restoration. This diagnostic does not establish the
failure's cause or accept performance; task 4.2 remains open.


The corrected fixture now waits for live classification before starting its
throw. `docs/evidence/card-shell/throw-fixture-sync/README.md` preserves two
setup failures and the following same-package board run with all 13 checks
observed, 277 fully correlated submitted frames, and independent normal-system
restoration. Frame CPU and tracking budgets still fail; this supports the
fixture-race diagnosis without completing performance or physical-touch gates.


The same-package scaled-cache off/on physical pair observed all 13 checks in
both arms, but increased p95 CPU cost and left tracking cadence unchanged.
`docs/evidence/card-shell/scaled-cache-board/README.md` preserves all 662
submitted frames and independent normal-system restoration. The cache remains
disabled; task 4.2 is still open with unchanged limits.


Task 4.3: `docs/evidence/card-shell/renderer-decision.md` and
`docs/evidence/card-shell/renderer-decision.json` record the decision not to pursue the
optional GPU path within this card acceptance change. Existing GPU synthetic
scene measurements are explicitly not represented as a card comparison. The
separate GPU proposal retains every open gate; task 4.2 and image/real-finger
acceptance remain incomplete. The separate user-authorized RVV promotion is
unaffected.
