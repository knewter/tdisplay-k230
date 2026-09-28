This change was split from `the-handheld-presents-a-coherent-shell` (tasks
2.2, 4.4, and 4.5). The user authorized this split on 2026-09-28 ("yes a-d
and f"); the parent's own tasks 2.2/4.4/4.5 are now ticked `[x] ... MOVED,
NOT PERFORMED HERE` and cross-reference this file. Task IDs here are
renumbered for this change's own groups; each task names its parent task ID
for traceability. Two new board tasks (1.3, 2.2) are added since the
parent's existing group-5 physical tasks predate this mechanism and do not
cover it. None of the tasks below are done yet; authorization only removes
the blocker on starting them.

## 1. Side-edge contextual Back and touch ownership (host)

- [ ] 1.1 (parent 2.2) Implement qualified side-edge contextual Back for shell
  sheet/Settings/shade/drawer/keyboard, without injecting a universal Back
  key into apps, alongside the existing bottom-edge overlay-escape recognizer
  in `nix/card-shell/adapter.c`. Verify with a new host/native fixture
  (`tests/test_card_shell_route.py` extension or equivalent) exercising:
  side-edge dismiss order (sheet, then Settings/shade/drawer, then keyboard),
  no synthesized Back keypress reaching app content, and no interference with
  the existing bottom-edge escape.
- [ ] 1.2 (parent 4.4) Define touch ownership for bottom Home/drawer, top
  shade, side Back, keyboard, deck and app content; test app scroll/text
  selection and keyboard conflict before enabling edges. Verify with the same
  fixture as 1.1 plus cases for app-scroll-conflict, bottom-qualified,
  top-qualified, side-qualified, and keyboard-inset.
- [ ] 1.3 (new) On a reserved board, confirm the side-edge Back gesture feels
  right from a real finger across Settings/shade/drawer sub-pages, with no
  accidental app-content Back and no interference with the existing
  bottom-edge escape. Operator command:
  `python3 tools/capture-feature.py side-edge-back --provenance real-touch
  --duration 30 --description 'Side-edge contextual Back on glass'
  --output-dir docs/evidence/coherent-shell/side-edge-back`. Keep open until
  committed.

## 2. Motion trace tooling (host + board)

- [ ] 2.1 (parent 4.5) Build `tools/shell-motion-trace.py` (touch->scene
  damage->commit->frame-done->output-presented trace IDs, reduced-motion
  parity, process CPU/memory sampling, declared board p95/p99 budgets) and
  `tests/test_shell_motion.py`. Verify with
  `python3 tools/shell-motion-trace.py --self-test` and
  `python3 tests/test_shell_motion.py --case trace-order --case reduced-motion`
  (host trace schema, not panel presentation).
- [ ] 2.2 (new) Under a board reservation, run
  `python3 tools/shell-motion-trace.py --board --output
  docs/evidence/coherent-shell/motion.json`, correlating input->scene
  commit->output presentation with camera-visible movement; report p50/p95/p99,
  blank/missed frames, CPU/RSS, renderer and actual cadence. Record failed
  budgets honestly. Keep open until committed.

## 3. Validation

- [x] 3.1 Validate this change: `openspec validate
  the-shell-gets-side-edge-back-and-motion-trace --strict`. Passed
  2026-09-28 on `close/shell-umbrella`.
- [ ] 3.2 Do not archive until tasks 1.3 and 2.2 are committed, or the
  coordinator explicitly authorizes archiving the host-only portion with the
  board tasks split into a further successor.
