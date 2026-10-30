**Un-queued by the user (2026-10-30):** "i do want the boot shows a game of
life bit too" lifts the 2026-09-28 queue (see `Status (2026-10-30)` in
`proposal.md`). Tasks are now being worked in order; hardware-only gates stay
open until their named physical proof exists.

## 1. Prerequisite and engine

- [ ] 1.1 Consume the separate static splash-to-Linux repair result as a prerequisite and record its before/after physical evidence; verify the prior wrapped/color-swapped first-modeset case is absent before enabling animation, without modifying that repair in this change.
- [x] 1.2 Implement the portable C Game of Life rules, deterministic seed, glider insertion, and versioned state/checksum ABI; verify reproducible frame hashes with `cc -std=c11 -Wall -Wextra -Werror -I src tests/test_game_of_life.c src/game_of_life.c -o /tmp/test-game-of-life && /tmp/test-game-of-life` and retain the test output under `docs/evidence/game-of-life/host-engine.txt`.
  Done 2026-10-30 (host build/test only; no board, U-Boot or QEMU): `src/game_of_life.{h,c}` (142x308 torus, 4 px cells = 568x1232 scanout, B3/S23, xorshift32 default seed, glider insertion, differential and full renderers, 5 584-byte little-endian record with FNV-1a checksum and boot-instance token) and `tests/test_game_of_life.c` (362 checks, 0 failures). Golden grid/frame hashes at generations 0/1/10/100/500 were cross-checked against an independent numpy implementation. Output: `docs/evidence/game-of-life/host-engine.txt`.
- [x] 1.3 Define the reserved-RAM ownership and address from the compiled DTB and actual boot layout, including invalidation and fallback behavior; implement `tools/check-boot-life-memory.py` to decompile the DTB with `dtc`, read the reserved-memory node, collect U-Boot load/relocation addresses and kernel/initrd ranges, and reject overlapping intervals; verify its report in `docs/evidence/game-of-life/memory-map.txt`.
  Done 2026-10-30 (host check over real artifacts; no board write): record window `0x102ac000..0x102ae000` (record 5 584 bytes of an 8 KiB window) inside the existing 4 MiB no-map splash reservation `0x10000000..0x10400000`, after the 568x1232x4 scanout (ends `0x102ab600`): no new reserved-memory node and no new RAM claim. `tools/check-boot-life-memory.py` decompiles the DTB the board actually boots (read from `/boot` over SSH, sha256 `f6d31149...a618`), reads the `reserved-memory` node, collects `blinux` load addresses with the real boot-file sizes plus the live U-Boot relocation/LMB/relocated-initrd/DTB ranges from the earlier physical `bdinfo`/`bootm` capture (`docs/evidence/stage1-memory-map.md`), and rejects overlap; it reports OK, and `tests/test_check_boot_life_memory.py` shows it rejecting seven bad cases. Invalidation and fallback are in `docs/evidence/game-of-life/memory-map.txt`. Limit: the U-Boot ranges are the earlier measurements, not re-measured, and the kernel BSS beyond the Image file size is not measured.

## 2. Stage handoff

- [ ] 2.1 Add stage-1 frame rendering and last-frame/state publication without changing the repaired static handoff contract; verify the source-built vendor-derived U-Boot output with `nix build --no-link --print-out-paths .#uboot-k230 --option max-jobs 1 --option cores 1` and retain a state dump under `docs/evidence/game-of-life/uboot-state-host.txt`; physical U-Boot rendering remains a separate board check.
- [ ] 2.2 Add early-Linux state validation and continuation after display ownership is ready; verify invalid/version-mismatched state falls back to the deterministic pattern and that logs identify the ownership pause.
- [ ] 2.4 Run the stage-1 animation from U-Boot's cyclic hook so it advances while U-Boot keeps loading the kernel, with the blocking loop as the fallback when cyclic is absent; verify the stage-1 host test (`tests/test_boot_life_stage1.c`, incremental session case), the two nix builds (`nix build --no-link --print-out-paths .#uboot-k230-boot-life .#uboot-k230 --option max-jobs 1 --option cores 1`, default output unchanged), and then on the board a serial capture of a boot with `boot_life=1` showing the `cyclic stopped at generation N after M callbacks, mean/max us` line and the boot-time delta against the same boot without it. Findings so far, source reading only: `docs/evidence/game-of-life/uboot-cyclic.md`. The board measurement is UNVERIFIED and needs the reviewed install procedure.
- [ ] 2.3 Record a physical boot video and serial transcript showing stage-1 frames, Linux takeover, the documented pause, and first valid Linux frame; verify no uninterrupted-motion claim is made.

## 3. Touch and optional continuation

- [ ] 3.1 Add Linux touch glider insertion with no-touch fallback; verify injected touch drops a glider and the animation remains recoverable when the input device is absent, then separately record a real finger tap adding a glider with camera and console evidence.
- [ ] 3.2 Investigate feasibility of porting Goodix input into U-Boot using the existing Linux driver as a reference; verify with a source/ABI feasibility note and, only if pursued, separate board serial/camera evidence for probe, coordinates, and glider insertion. This optional task does not gate archive on a successful port.
- [ ] 3.3 Add optional Wayland continuation without removing persistent shell controls; verify Apps, Keyboard, Windows/Home, System, and recovery remain reachable in a shell capture.

## 4. Review

- [ ] 4.1 Run the host engine command from 1.2, inspect the built image and memory-map artifact from 1.3, and run `openspec validate --type change the-boot-shows-a-computational-game-of-life --strict`; verify all three outputs are attached to the evidence directory and that no physical U-Boot or touch task is marked complete without board evidence.
