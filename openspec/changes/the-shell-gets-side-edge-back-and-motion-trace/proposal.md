## Why

A 2026-09-28 audit of `the-handheld-presents-a-coherent-shell` (30 open tasks)
found that most of its host-scope tasks are already implemented -- the actual
build went through `nix/rust-shell-client`/`nix/card-shell` rather than
growing `nix/touch-launcher --serve` as the change's own cited test commands
assumed, and has substantial host/QEMU evidence under
`docs/evidence/coherent-shell/`. Three tasks, though, are genuinely
unimplemented and do not depend on the board:

- **Task 2.2 / 4.4**: the qualified side-edge contextual Back gesture for
  shell sheet/Settings/shade/drawer/keyboard. Only a narrower, different fix
  landed -- the bottom-edge overlay-escape and dismiss-direction fix from
  `the-shell-behaves-as-one-coherent-system` slice E
  (`docs/evidence/coherent-shell/overlay-bottom-escape-qemu/`). That change's
  own `proposal.md` says so explicitly: "The general side-edge contextual
  Back mechanism for shell sheet/Settings/shade/drawer/keyboard ->
  `the-handheld-presents-a-coherent-shell` tasks 2.2 and 4.4, still open;
  slice E's bottom-edge escape and dismiss-direction fix are bounded,
  narrower fixes that do not complete those tasks." Task 4.4's broader touch
  ownership arbitration (bottom Home/drawer, top shade, side Back, keyboard,
  deck, app content) depends on the same missing side-edge mechanism.
- **Task 4.5**: a touch->scene damage->commit->frame-done->output-presented
  trace tool with declared p95/p99 budgets. `tools/shell-motion-trace.py` and
  `tests/test_shell_motion.py` do not exist on disk; the parent's own tasks.md
  preamble already calls them "interfaces to create, not current proof."

This is a **scope-split successor**, per `AGENTS.md`'s "close deliberately"
rule: it carries these three tasks and their requirement scope unchanged, so
the parent can close its other 27 tasks (22 done, 5 physical-board) without
waiting on this open-ended design/implementation work.

**Status: authorized 2026-09-28.** The user authorized this split on
2026-09-28 ("yes a-d and f"). Tasks 2.2, 4.4, and 4.5 are now ticked
`[x] ... MOVED, NOT PERFORMED HERE` in the parent's `tasks.md`, and the
parent's `runtime/handheld-shell-design` spec delta has been narrowed to
drop the corresponding requirement scope, in the same commit that makes
this change active. This change's own tasks below are unchanged by that
authorization -- none of them are done yet, only unblocked to proceed.

## What Changes

- **Side-edge contextual Back**: an inward swipe from a qualified side edge
  dismisses the topmost shell context (long-press sheet, Settings, shade,
  drawer, then keyboard) without synthesizing a Back keypress into arbitrary
  Wayland app content. This is distinct from, and does not replace, the
  already-landed bottom-edge overlay escape.
- **Touch ownership arbitration**: a single compositor-side arbiter decides,
  at touch-down, which of bottom Home/drawer, top shade, the new side Back,
  keyboard, deck, and app content owns a contact, tested against app
  scroll/text-selection and keyboard conflicts before any edge is enabled.
- **Motion trace tooling**: `tools/shell-motion-trace.py` (host self-test and
  `--board` modes) and `tests/test_shell_motion.py`, producing touch-to-commit,
  frame-done, and output-presented trace IDs, reduced-motion parity, and
  process CPU/memory sampling against declared p95/p99 budgets.

## Non-goals

- Re-litigating the already-implemented Home/deck/drawer/shade/Settings/
  notification routing in the parent (tasks 1.1-1.6, 2.1, 2.3-2.5, 3.1-3.4,
  4.1-4.3, 4.6, 4.8), which stays there, done, with its own evidence.
- The bottom-edge overlay escape and dismiss-direction fix, already landed by
  `the-shell-behaves-as-one-coherent-system` slice E.
- The gesture-discovery accessibility aid (large labeled route controls),
  which is the parent's own task 1.5 (left open there, not moved here).
- Any board/real-finger acceptance. This is host/QEMU-only scope; physical
  feel of the resulting side-edge Back and the trace tool's board mode are
  new, separately-gated tasks here (2.2-board, 4.5-board) rather than folded
  into the parent's group-5 tasks, since the parent's group 5 predates this
  mechanism.

## Board need

Host work only for the design/implementation tasks below. Two new physical
acceptance tasks (side-edge Back feel, and running the trace tool's `--board`
mode) need a reserved board and are left open pending that reservation.

## Capabilities

### Modified Capabilities

- `runtime/handheld-shell-design`: narrows two requirements the parent already
  added (`Shade and contextual Back preserve the task`, `Gesture ownership and
  feedback are explicit`) with the concrete side-edge mechanism and ownership
  arbitration they described but that were not yet implemented, and adds a new
  requirement for declared, measured motion budgets. Because the parent's own
  delta for this capability is not yet archived, this successor's delta targets
  the same not-yet-existing capability additively, the same pattern
  `the-shell-offers-quick-toggles-and-vision-options` already uses for
  `runtime/notification-center`/`runtime/device-settings`.

## Impact

Userspace only: `nix/rust-shell-client/src/service_ui.rs` (edge arbitration,
side Back), `nix/card-shell/adapter.c`/`route.c` (compositor-side edge
recognizers, alongside the existing bottom-edge/overlay-escape recognizers),
and new `tools/shell-motion-trace.py` / `tests/test_shell_motion.py`. No
kernel, device-tree, stage-1, or radio change.
