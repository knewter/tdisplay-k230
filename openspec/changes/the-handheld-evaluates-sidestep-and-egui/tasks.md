## Status (2026-10-30)

Proposed. Board offline at the time of writing (power cycle needed); host tasks proceed.

## 1. Build the egui software probe

- [ ] 1.1 Package the opt-in egui software probe (`nix/egui-software-probe`): egui 0.34, `egui_software_backend` 0.0.3, `wl_shm` output, the Qt trial's scene and JSONL events. Proof (host build, cross): `flock /tmp/k230-nix-build.lock nix build .#egui-software-probe --max-jobs 1 --cores 4 --out-link $SCRATCH/egui-probe` and `nix path-info -rsS` for the closure size. A failed build is retained.
- [ ] 1.2 Host fixture: render the scene headlessly on the build host and compare layout and gestures with the baseline fixture. Proof (host test): `python3 tests/test_egui_probe_scene.py`.
- [ ] 1.3 Run the riscv64 binary under QEMU user mode to show it starts and renders into a buffer headlessly. Proof (QEMU user, no speed claim): `qemu-riscv64-static` run recorded in `docs/evidence/egui-sidestep/`.

## 2. Assess and, if bounded, port Sidestep to riscv64

- [ ] 2.1 Inventory the architecture-specific source with line counts, fallbacks and ABI notes at the pinned Sidestep revision. Proof (source reading): `docs/evidence/egui-sidestep/sidestep-riscv64-assessment.md`, citing paths and lines.
- [ ] 2.2 Decide go/no-go in that document. If go, add the LP64D pieces as a patch overlay under `nix/sidestep-riscv64/` and cross-build `msgbench`, `textbench`, `controlbench`, `eventbench` and the conformance crate. Proof (host cross-build): `nix build .#sidestep-riscv64-benches`. If no-go, the recorded estimate closes this group and groups 4 and 5 are marked not performed.
- [ ] 2.3 Run the conformance tests and benches under QEMU user mode. Proof (QEMU user): transcripts under `docs/evidence/egui-sidestep/`.

## 3. Prepare the comparable trial

- [ ] 3.1 Add `tools/toolkit-eval-trial.py` that imports `tools/qtquick_analysis.py` and adds a candidate slot (`egui`, `sidestep`), a frozen manifest and a deadline-controlled transient board runner. Proof (host test): `python3 tools/toolkit-eval-trial.py --self-test`.

## 4. Sidestep scene client (only if 2.2 is go)

- [ ] 4.1 A Sidestep app with the same scene, built for riscv64, with software-route identity. Proof: host cross-build plus QEMU user run.

## 5. Measure on the board

- [ ] 5.1 Egui: three matched pairs against the baseline under the board lock, native `grim` captures, injected input, restoration. Proof (injected board event): `python3 tools/toolkit-eval-trial.py board --candidate egui ...`, evidence committed with the board's boot ID and unchanged boot default.
- [ ] 5.2 Sidestep (if 4.1 done): the same measurement with its benches' own results. Proof as 5.1.
- [ ] 5.3 Publish the verdicts with numbers beside the shell and Qt results. Proof: `python3 scripts/build_site.py` and the published revision.

## 6. Close

- [ ] 6.1 `openspec validate --all --strict`; archive only when every task above has its named proof. A no-go in 2.2 requires a successor proposal for the unperformed Sidestep tasks before closing.
