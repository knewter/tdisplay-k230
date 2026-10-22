## 1. Proposal

- [x] 1.1 Validate with `openspec validate the-compositor-repaints-within-its-render-budget --strict`.

## 2. Baseline (hardware-only)

- [x] 2.1 Measure drawer scroll and keyboard cycles on installed `z1basiwi` with the compositor benchmark armed (`docs/evidence/interaction-jank/compositor-repaint/run-base`).

## 3. Iterations (each: host check, test-activate, same measurement)

- [x] 3.1 Sway without `-d` (run-h-nodebug).
- [x] 3.2 Drawer opaque region from opaque sheet rows (run-i-opaque): no gain on the translucent theme; dropped.
- [x] 3.3 wvkbd opaque region (run-j-wvkbd): rejected by the operator, since it looks wrong while sliding; dropped.
- [x] 3.4 Profile with `tools/board-profile.py`, then try the next measured lever: RVV quarter-turn (run-k, prof-k-drawer, no gain, dropped); sway `SCHED_RR` through `LimitRTPRIO=1` (run-k-rr, run-l, run-m); prof-m-kbd records that the remaining levers are small or rejected.

## 4. Close

- [x] 4.1 Commit the measurements under `docs/evidence/interaction-jank/compositor-repaint/`, comparing each step against the 12 ms render allowance and the 33.334 ms card budget. Record any failed budget as failed.
- [ ] 4.2 Promote the final build to the boot default, then verify an ordinary boot and a drawer run on it.
