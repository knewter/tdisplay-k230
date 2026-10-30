## Status (2026-10-30)

**In progress.** Host work, the Sidestep riscv64 port and a first board pass are done;
the three-pair egui trial, the scene-matched Sidestep client and the pinned Nix
packaging of the Sidestep port remain. The board was withdrawn for a boot-path
trial on 2026-10-30 before the remaining arms could run. Evidence is under
`docs/evidence/egui-sidestep/`; its `README.md` indexes it.

## 1. Build the egui software probe

- [x] 1.1 Package the opt-in egui software probe (`nix/egui-software-probe`: egui 0.34.1, `egui_software_backend` 0.0.3, `wl_shm` output, the Qt trial's scene and JSONL events). Proof (host cross-build): `nix build .#egui-software-probe --max-jobs 1 --cores 4` under the build lock produced `/nix/store/jr5vpm68dnlhxzkamc588lmq127cjvj2-egui-software-probe-riscv64-unknown-linux-gnu-0.1.0` (binary 5.8 MB, closure 4 paths / 127 MB; `docs/evidence/egui-sidestep/egui-board-results.md`).
- [x] 1.2 Host fixture: scene constants equal the baseline's and no GL or window toolkit is a dependency. Proof (host test): `python3 tests/test_egui_probe_scene.py`. A headless render under a host Weston also produced a frame whose five probe pixels match the controller's gates.
- [x] 1.3 Run the riscv64 binary under QEMU user mode. Proof (QEMU user, no speed claim): a cargo cross-build of the same source under `qemu-riscv64-static` against a headless Weston produced a frame byte-identical to the x86_64 build's (`docs/evidence/egui-sidestep/egui-qemu-user-smoke.txt`, 1232x568 scene).

## 2. Assess and port Sidestep to riscv64

- [x] 2.1 Inventory the architecture-specific source with line counts, fallbacks and ABI notes at Sidestep `626422b`. Proof (source reading): `docs/evidence/egui-sidestep/sidestep-riscv64-assessment.md`.
- [x] 2.2 Decide go/no-go (go) and implement the riscv64 LP64D pieces as a patch overlay (`nix/sidestep-riscv64/`, 526 added lines plus a one-line third-party patch); cross-build `msgbench`, `textbench`, `controlbench`, `eventbench`, `drawing-gallery`, `controls-gallery`. Proof (host cross-build with cargo, **not** a Nix derivation): the commands in `nix/sidestep-riscv64/README.md`.
- [ ] 2.3 Package the port as a pinned Nix derivation (`nix build .#sidestep-riscv64-benches`). Open: Sidestep's `tools/objc2-overlay` downloads and patches crates at build time, which needs a vendoring step.
- [x] 2.4 Run the conformance tests under QEMU user mode. Proof (QEMU user): `sidestep-conformance-riscv64-qemu-user.txt`: 610 tests passed, one real failure (the autorelease return-value handoff, not ported), seven attributable to the environment or identical on the x86_64 control.

## 3. Prepare the comparable trial

- [x] 3.1 `tools/toolkit-eval-trial.py` adds a candidate slot to the Qt trial's controller and analysis, the WAYLAND_DEBUG identity check for a client that does not link libwayland, a pre-arm display wake, a scene-reset patch for the functional checks and whole-system CPU counters per arm. Proof (host test): `python3 tools/toolkit-eval-trial.py --self-test`.
- [ ] 3.2 Make the injected input land reliably. The runner's uinput touchscreen landed rotated or wrong in several arms (see the results file); the absolute-pointer replacement failed its scroll and tap gates in the one arm it ran. Owner of `tools/qtquick_board_runner.py` and this change must agree on a fix, then re-run.

## 4. Sidestep scene client

- [ ] 4.1 An AppKit app with the same scene (scroll view of 20 rows, editor, animated tile, image), built for riscv64 against the port, with software-route identity. Proof: host cross-build plus QEMU user run. Not started.

## 5. Measure on the board

- [ ] 5.1 egui: three matched pairs against the baseline under the board lock, native `grim` captures, injected input, restoration. Partly done: **one valid 30 s pair** and one short pair are recorded (`pairs-cargo-build/`, `short-pair-12s/`); pair 2 and pair 3 are missing or invalid. Proof when finished: `python3 tools/toolkit-eval-trial.py board --name egui ...` evidence committed with boot ID and unchanged boot default.
- [ ] 5.2 Sidestep scene client measured the same way. Blocked on 4.1. Done instead (not a substitute): the Sidestep benches and two windowed demo apps ran on the board (`sidestep-board/`, `captures/`).
- [ ] 5.3 Typing: with the on-screen keyboard rendering, `text_focus` and `text_entry` pass for egui and the baseline. They failed for both because the keyboard did not appear in the captures.
- [ ] 5.4 Publish the verdicts beside the shell and Qt results once 5.1 and 5.2 have their numbers. Proof: `python3 scripts/build_site.py` and the published revision.

## 6. Close

- [ ] 6.1 `openspec validate --all --strict`; archive only when every task above has its named proof. Keep this change open for 2.3, 3.2, 4.1 and 5.x.
