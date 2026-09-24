The probe outputs, analyzer and trial commands below are **planned interfaces**,
not existing tools or completed checks. Each owning task adds its interface
before invoking it. Evidence belongs in `docs/evidence/qtquick/` with exact
source/store identities and explicit host, injected-input and physical labels.

## 1. Build the minimal Qt Quick and baseline clients

- [ ] 1.1 Package the opt-in primitive Qt Quick software probe, including editable text and unsupported-effect negative control; reserve the build slot and verify `nix build .#qtquick-software-probe --max-jobs 1 --cores 4 --no-link --print-out-paths`. Retain configure/QV4/cache mode, build time, Qt/Wayland identities and `nix path-info -rsS PROBE_OUT`; a failed build is retained, not a physical result.
- [ ] 1.2 Add the equivalent small SHM baseline client with identical viewport, content and scripted motion; verify `nix build .#qtquick-shm-baseline --max-jobs 1 --cores 4 --no-link --print-out-paths` and host scene/output fixtures with `python3 tests/test_qtquick_probe_scene.py`.

Proof: the two narrow build commands and host fixture check above. No normal-image integration or board claim.

## 2. Prepare comparable measurement and bounded recovery

- [ ] 2.1 Add the candidate/workload manifest and analyzer, freezing design ceilings and unchanged card budgets before any run; verify mismatched IDs, missing presentation samples, changed budgets, failed baseline and per-run aggregation with `python3 tools/qtquick-trial.py --self-test`.
- [ ] 2.2 Add a deadline-controlled board runner for transient clients, scoped cleanup and independent restoration; verify launch failure, controller loss, focus capture and timeout paths with `python3 tests/test_qtquick_trial_recovery.py`. Document exact operator commands and required board lock.
- [ ] 2.3 Prepare the pinned Qt/baseline manifest with exact current system and compositor identities; verify `python3 tools/qtquick-trial.py prepare --qt PROBE_OUT --baseline BASELINE_OUT --output NEW_MANIFEST` rejects missing or mismatched artifacts and records workload/budget version.

Proof: the named self-test, recovery tests and prepare command. Host recovery simulation is not physical restoration proof.

## 3. Measure the Qt Quick app on the board

- [ ] 3.1 Reserve the board and run `python3 tools/qtquick-trial.py board --manifest MANIFEST --stage qt --output NEW_EVIDENCE_DIR`; commit backend/SHM identity, native captures, three matched pairs, startup/CPU/session-memory/presentation/input results and normal-session restoration. Use concrete paths in the evidence record and retain failures.
- [ ] 3.2 In that bounded trial, record real finger tap, scroll, interrupted motion, text-field focus and existing on-screen keyboard behavior plus panel readability; retain focused camera evidence distinct from injected events and verify every named observation in the trial's physical checklist.
- [ ] 3.3 Evaluate the Qt prerequisite with `python3 tools/qtquick-trial.py decide --stage qt --evidence NEW_EVIDENCE_DIR`; retain each pass/fail/incomplete criterion and a separate production-budget result. Do not start the Quickshell board stage unless the prerequisite passes.

Proof: exact recorded board and decision commands plus real-glass checklist/media. No camera or host fixture can substitute for measured compositor presentation, and no timestamp is labeled optical latency without optical proof.

## 4. Evaluate a minimal Quickshell surface conditionally

- [ ] 4.1 After the Qt prerequisite passes, package pinned Quickshell against the same Qt ABI with effective GPU-screencopy/Hyprland/X11/unrelated-service flags disabled; verify `nix build .#quickshell-software-probe --max-jobs 1 --cores 4 --no-link --print-out-paths`, record feature summary and incremental closure size.
- [ ] 4.2 Extend the manifest for that exact output and run `python3 tools/qtquick-trial.py board --manifest MANIFEST --stage quickshell --output NEW_EVIDENCE_DIR` under a fresh board reservation; retain layer-shell/backend proof, matched measurements and physical input-region/focus/keyboard/edge-gesture/show-hide/exit/restoration observations.
- [ ] 4.3 Run `python3 tools/qtquick-trial.py decide --stage quickshell --evidence NEW_EVIDENCE_DIR` and commit the app-versus-shell recommendation with explicit module/effect limits. A simple panel cannot certify full Omarchy or live-card composition.

Proof: narrow package build, concrete board trial and decision invocations. If the prerequisite fails, these tasks remain unperformed/open; do not mark them successful because the gate was evaluated.

## 5. Publish decisions without implying adoption

- [ ] 5.1 Publish reviewed screenshots/video, artifact identities, per-run metrics and separate Qt-app/Quickshell decisions in committed evidence; verify links with `python3 scripts/build_site.py` and inspect the exact published revision.
- [ ] 5.2 Validate the completed evaluation with `openspec validate --all --strict`; archive/sync only once all required execution and recovery proof exists, preserving any proposed adoption as a separate explicitly scoped change. Keep the proposal open if a dependent stage was not performed.

Proof: site build, strict validation, reviewed evidence and exact-revision CI/deployment. This change does not add a default Qt/Quickshell session.
