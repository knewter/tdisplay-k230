## 1. Proposal

- [ ] 1.1 Validate with `openspec validate the-compositor-repaints-within-its-render-budget --strict`.

## 2. Baseline (hardware-only)

- [ ] 2.1 Measure drawer scroll and keyboard cycles on installed `z1basiwi` with the compositor benchmark armed.

## 3. Iterations (each: host check, test-activate, same measurement)

- [ ] 3.1 Sway without `-d`.
- [ ] 3.2 Drawer opaque region from opaque sheet rows (`render::tests::an_opaque_drawer_sheet_reports_its_opaque_rows`).
- [ ] 3.3 wvkbd opaque region.
- [ ] 3.4 Profile the result with `tools/board-profile.py`, then try the next measured lever or record that gains became minimal.

## 4. Close

- [ ] 4.1 Commit the measurements under `docs/evidence/interaction-jank/compositor-repaint/`, comparing each step against the 12 ms render allowance and the 33.334 ms card budget. Record any failed budget as failed.
- [ ] 4.2 Promote the final build to the boot default, then verify an ordinary boot and a drawer run on it.
