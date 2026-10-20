## 1. Explicit diagnostic profile (host proof)

- [x] 1.1 Add a named landscape capture profile and strict report with separate schema; reject portrait/landscape cross-use, incomplete joins and mixed runtime/workload. Run `python3 tools/hdmi-shell-capture-board.py --self-test`, `python3 tools/hdmi-shell-performance.py --self-test` and `python3 tools/landscape-hdmi-baseline.py --self-test`; commit the passing host evidence.

## 2. Installed runtime baseline (hardware diagnostic, not glass proof)

- [ ] 2.1 Under the exclusive board lock capture at least 24 injected drags each with one and two ordinary Foot windows, retaining current 1280×800 normal scale1 geometry and exact installed runtime identity. On board run `python3 hdmi-shell-capture-board.py --profile landscape-1280x800 --variant candidate --input injected --seconds 180 --drags 24 --source-revision 221bbcf34a276a939356e5a6af9bfb124af9896a --output <new-run-directory>` once per workload, then `python3 tools/landscape-hdmi-baseline.py --one <one-run-directory> --two <two-run-directory> --output <report.json>` on host. Commit raw allowlisted logs, context, report and commands. No performance acceptance budget is implied.
- [ ] 2.2 Restore normal Home with benchmark stopped and only owned temporary apps removed; preserve original output state and user apps. Save a bounded numeric/status cleanup transcript under `docs/evidence/landscape-hdmi-baseline/` using the same reserved-board wrapper's final checks. This proves cleanup only, not physical HDMI touch or optical visibility.

## 3. Publication

- [x] 3.1 Honor the explicit tooling-only metadata in the public work board; keep missing-delta checks for absent, false, nested, quoted or repeated markers. Run `python3 tests/test_work_board.py` and `python3 scripts/render_work_board.py --working-tree --output /tmp/k230-landscape-work-preview.json`.
- [ ] 3.2 Run `openspec validate the-landscape-hdmi-shell-has-a-reproducible-motion-baseline --strict`, commit the proved tooling/evidence and push master; verify the exact revision at `https://knewter.github.io/tdisplay-k230/work/` after its CI succeeds. Archive only after tasks1–2 have their committed proof. Leave the portrait proposal and all nine unchecked tasks open.
