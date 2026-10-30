## 1. Ground the choice of ttfx

- [x] 1.1 Record what `ttfx` is, its licence, layout, dependencies, whether its engine can emit frames apart from the terminal writer, and which glyphs and colours its 37 effects use over the K230 banner. Proof: `python3 -I tools/textfx_frames.py survey --ttfx <host build of ttfx 14ed274> --banner nix/exhibition/K230.txt --seed 3` (host) reproduces the table in `docs/evidence/boot-text-effects/ttfx-research.md`. Host evidence only.
- [ ] 1.2 Confirm the packaged riscv64 `ttfx` (`nix/ttfx.nix`, `.#ttfx`) emits byte-identical `--parity-dump` frames to the host build of the same revision. Proof: `docs/evidence/boot-text-effects/board-dump-hashes.txt` with the host and board SHA-256 per effect/seed; the board run is a process run on the live system, not a boot observation.

## 2. Host tool and portable renderer

- [ ] 2.1 `tools/textfx_frames.py`: run the pinned `ttfx` with `--parity-dump`, parse the frames into character cells, write a versioned cell-sequence file (`TFXS`), and print a per-frame and whole-sequence hash. Proof: `python3 -I tests/test_textfx_frames.py` (host); the same seed gives the same hashes twice, and a different seed does not.
- [ ] 2.2 `src/textfx.{h,c}`: freestanding C (memcpy/memset only) that applies a `TFXS` frame to a cell grid and blits glyphs into an XRGB8888 or RGB565 target, with a generated 8x16 font table and a visible fallback glyph. Proof: `cc -std=c11 -Wall -Wextra -Werror -I src tests/test_textfx.c src/textfx.c -o <scratch>/test-textfx && <scratch>/test-textfx` (host), whose pixel hashes equal an independent Python renderer's for the same frames.
- [ ] 2.3 Choose the default effect and canvas from measurements of the candidates at the panel's real grid (frame count, changed cells per frame, sequence bytes, glyph coverage). Proof: the table in `docs/evidence/boot-text-effects/effect-candidates.md` produced by `tools/textfx_frames.py survey`; the choice is then written into `design.md` and this task is ticked.

## 3. Early-Linux live player

- [ ] 3.1 `k230-textfx` player (C, `nix/textfx/`), a Nix derivation, and a NixOS option that is off by default: reads `ttfx --parity-dump` from a pipe, skips to a frame given on the command line after checking its cell-grid hash, paces at the sequence frame rate, renders cell deltas, supports `--output-file` (no DRM) and the splash owner's ready-file/`SIGUSR1` protocol. Proof: `nix build .#k230-textfx` (target build, laptop claim) and `tests/test_textfx_player.py` against the host build.
- [ ] 3.2 Start the player by hand on the running board with `--output-file`, under the board lock, and compare its framebuffer hashes with the host reference. Proof: `docs/evidence/boot-text-effects/board-offscreen.txt` (board process run, no glass).
- [ ] 3.3 Start the player by hand against DRM on the running board (stopping and restoring the shell under the board lock, or an equivalent that leaves the user's session intact) and record the KMS calls, exit status and measured CPU per frame. Proof: `docs/evidence/boot-text-effects/board-drm.txt` (board process run). A claim about what the glass shows needs camera or glass evidence and is not made here.

## 4. Stage 1 playback (waits for the operator)

- [ ] 4.1 Add a text-effects frame source (source id 2) to the generic stage 1 loop once `src/boot_frame.h` is on `master`, with the sequence embedded or loaded from a boot file as design decision D2 settles, and build it. Proof: `nix build .#uboot-k230-boot-textfx` (laptop claim). Writing it to a board is task 4.2.
- [ ] 4.2 Install the stage 1 build and the sequence file by the plan in `design.md`, verify readback and a console transcript of one `K230#` run, and keep the rollback. Not started: **HARD STOP**, requires the operator's go-ahead and board reservation.

## 5. Placement in Linux and handoff (waits for the operator)

- [ ] 5.1 Decide and measure the earliest practical start (rootfs unit versus initrd unit) from a boot trace, and write the exact change to kernel-adjacent files in `design.md`. Not started: initrd or bootargs changes are a **HARD STOP**.
- [ ] 5.2 Enable the player at boot, hand the display to the shell, and record the journal timing. Proof: serial/journal transcript under `docs/evidence/boot-text-effects/` (boot observation).

## 6. Physical proof (stays open)

- [ ] 6.1 Film a power-on or warm boot showing the stage 1 sequence, the pause, the live continuation and the shell's first frame, with the film aligned to kernel time. Verify with a committed film and frame timings. **Physical**; the webcam is not used for this change without the operator's say-so.

## 7. Review

- [ ] 7.1 `openspec validate the-boot-plays-terminal-text-effects --strict` and `python3 scripts/render_work_board.py` after commit (host).
