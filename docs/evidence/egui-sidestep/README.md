# egui and Sidestep on the K230

Index of the evidence for `openspec/changes/the-handheld-evaluates-sidestep-and-egui`.

- `egui-board-results.md`: egui on the board, with its limits.
- `sidestep-riscv64-assessment.md`: the Sidestep riscv64 port, conformance and board benches.
- `pairs-cargo-build/`, `short-pair-12s/`, `pointer-attempt/`: run records and event logs
  (`tools/toolkit-eval-trial.py analyse --out DIR` regenerates the tables).
- `sidestep-conformance-riscv64-qemu-user.txt`, `sidestep-conformance-x86_64-control.txt`:
  QEMU user-mode and control logs (host paths replaced by `<scratch>`).
- `sidestep-board/`: raw outputs of the Sidestep benches and windowed apps on the board.
- `captures/`: four native `grim` captures (egui probe, baseline, two Sidestep demo apps).

Commands:

```sh
# egui trial (host; needs the board lock per arm, a booted board and the Qt trial's runner)
python3 tools/toolkit-eval-trial.py board --name egui --candidate STORE_OUT --baseline STORE_OUT --out DIR
python3 tools/toolkit-eval-trial.py analyse --out DIR
# host checks
python3 tests/test_egui_probe_scene.py && python3 tools/toolkit-eval-trial.py --self-test
nix build .#egui-software-probe --max-jobs 1 --cores 4 --out-link RESULT
```
