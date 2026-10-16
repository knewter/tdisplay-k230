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
  Progress 2026-10-16 (host only, branch `side-edge-back`): `adapter.c` now
  claims a side band as a weak `EDGE_BACK` origin and fires a release-decided
  inward swipe through `side_back_fire()` (overlay: `card_shell_launch_surface
  ("hide")`; keyboard: `keyboard_signal("hide")`; no seat key event).
  `python3 tests/test_card_shell_route.py` (4/4) pins the dismiss order, the
  recognizer and the no-key-synthesis check, and `nix build .#card-shell`
  compiles the adapter. **Still open:** the long-press sheet lives on the Rust
  Home surface, which reports nothing to the compositor, so `sheet_open()` is a
  stub returning false and the sheet step of the order is not reachable on a
  device. It needs a Home-surface signal plus a Rust route; keep this task
  open until that exists. <!-- UNVERIFIED: sheet dismissal by side Back -->
- [x] 1.2 (parent 4.4) Define touch ownership for bottom Home/drawer, top
  shade, side Back, keyboard, deck and app content; test app scroll/text
  selection and keyboard conflict before enabling edges. Verify with the same
  fixture as 1.1 plus cases for app-scroll-conflict, bottom-qualified,
  top-qualified, side-qualified, and keyboard-inset.
  Done 2026-10-16, host fixture only: `card_shell_touch_owner()` in
  `nix/card-shell/route.c` is the one touch-down decision (keyboard hit, then
  bottom Home, top shade, qualified side Back, deck, app) and `input_down`
  asks it before beginning a side-Back origin; the existing bottom and top
  branches keep their code paths and the fixture pins that the arbiter agrees
  with them. `python3 tests/test_card_shell_route.py` passed 4/4 including
  `test_side_edge_back_and_touch_ownership` at 568x1232 and 1280x800 (cases:
  side-qualified, app-scroll-conflict, bottom-qualified, top-qualified,
  keyboard-inset, off-output). This is a policy check, not a touch on glass.
- [ ] 1.3 (new) On a reserved board, confirm the side-edge Back gesture feels
  right from a real finger across Settings/shade/drawer sub-pages, with no
  accidental app-content Back and no interference with the existing
  bottom-edge escape. Operator command:
  `python3 tools/capture-feature.py side-edge-back --provenance real-touch
  --duration 30 --description 'Side-edge contextual Back on glass'
  --output-dir docs/evidence/coherent-shell/side-edge-back`. Keep open until
  committed.
  Progress 2026-10-16, **injected mouse on HDMI**, not real touch
  (`docs/evidence/coherent-shell/side-edge-back/board-2026-10-16-injected.md`):
  - Left and right inward swipes closed an open Shade (`target=2`).
  - Plain Home, a 30 px swipe, an outward swipe, the top corner and a
    fullscreen app were all left alone.
  - With the keyboard shown, the pointer path never reaches the edge block;
    the top-edge Shade pull fails the same way, so this predates side Back.
    The keyboard target is therefore unproven on the board.
  Progress 2026-10-16 (later), **injected mouse on the panel**, after the
  keyboard-popup fix `b3c44dd0` (same evidence file, "Keyboard target after
  the popup fix"):
  - With the keyboard shown, a top-edge pull opened the Shade.
  - Side Back closed the Shade (`target=2`), then dismissed the keyboard
    (`target=3`).
  - Side Back closed Settings (`target=2`).
  Still open: real-finger feel and the drawer case.

## 2. Motion trace tooling (host + board)

- [x] 2.1 (parent 4.5) Build `tools/shell-motion-trace.py` (touch->scene
  damage->commit->frame-done->output-presented trace IDs, reduced-motion
  parity, process CPU/memory sampling, declared board p95/p99 budgets) and
  `tests/test_shell_motion.py`. Verify with
  `python3 tools/shell-motion-trace.py --self-test` and
  `python3 tests/test_shell_motion.py --case trace-order --case reduced-motion`
  (host trace schema, not panel presentation).
  Done 2026-10-16, host only: both commands passed
  (`tools/shell-motion-trace.py --self-test` printed `self-test PASS`;
  `tests/test_shell_motion.py --case trace-order --case reduced-motion` printed
  `PASS` for each). Budgets are declared in the tool: input-to-present p95 at
  two and p99 at three nominal 52.19 Hz output intervals, the same bounds for
  frame interval, zero blank frames, and 64 MiB RSS growth; CPU is sampled and
  reported with no budget. The card-shell console already emits only input,
  submit (commit) and present rows, so `--log` reports `scene_damage` and
  `frame_done` as unobserved; emitting them with trace IDs is compositor work
  that task 2.2 depends on. <!-- UNVERIFIED: no budget has been measured on the board -->
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
