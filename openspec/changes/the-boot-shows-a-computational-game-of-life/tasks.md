## 1. Prerequisite and engine

- [ ] 1.1 Consume the separate static splash-to-Linux repair result as a prerequisite and record its before/after physical evidence; verify the prior wrapped/color-swapped first-modeset case is absent before enabling animation, without modifying that repair in this change.
- [ ] 1.2 Implement the portable C Game of Life rules, deterministic seed, glider insertion, and versioned state/checksum ABI; verify reproducible frame hashes with `cc -std=c11 -Wall -Wextra -Werror -I src tests/test_game_of_life.c src/game_of_life.c -o /tmp/test-game-of-life && /tmp/test-game-of-life` and retain the test output under `docs/evidence/game-of-life/host-engine.txt`.
- [ ] 1.3 Define the reserved-RAM ownership and address from the compiled DTB and actual boot layout, including invalidation and fallback behavior; implement `tools/check-boot-life-memory.py` to decompile the DTB with `dtc`, read the reserved-memory node, collect U-Boot load/relocation addresses and kernel/initrd ranges, and reject overlapping intervals; verify its report in `docs/evidence/game-of-life/memory-map.txt`.

## 2. Stage handoff

- [ ] 2.1 Add stage-1 frame rendering and last-frame/state publication without changing the repaired static handoff contract; verify the source-built vendor-derived U-Boot output with `nix build --no-link --print-out-paths .#uboot-k230 --option max-jobs 1 --option cores 1` and retain a state dump under `docs/evidence/game-of-life/uboot-state-host.txt`; physical U-Boot rendering remains a separate board check.
- [ ] 2.2 Add early-Linux state validation and continuation after display ownership is ready; verify invalid/version-mismatched state falls back to the deterministic pattern and that logs identify the ownership pause.
- [ ] 2.3 Record a physical boot video and serial transcript showing stage-1 frames, Linux takeover, the documented pause, and first valid Linux frame; verify no uninterrupted-motion claim is made.

## 3. Touch and optional continuation

- [ ] 3.1 Add Linux touch glider insertion with no-touch fallback; verify injected touch drops a glider and the animation remains recoverable when the input device is absent.
- [ ] 3.2 Investigate feasibility of porting Goodix input into U-Boot using the existing Linux driver as a reference; verify with a source/ABI feasibility note and, only if pursued, separate board serial/camera evidence for probe, coordinates, and glider insertion. This optional task does not gate archive on a successful port.
- [ ] 3.3 Add optional Wayland continuation without removing persistent shell controls; verify Apps, Keyboard, Windows/Home, System, and recovery remain reachable in a shell capture.

## 4. Review

- [ ] 4.1 Run the host engine command from 1.2, inspect the built image and memory-map artifact from 1.3, and run `openspec validate --type change the-boot-shows-a-computational-game-of-life --strict`; verify all three outputs are attached to the evidence directory and that no physical U-Boot or touch task is marked complete without board evidence.
