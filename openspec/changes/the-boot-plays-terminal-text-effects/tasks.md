## 1. Ground the choice of ttfx

- [x] 1.1 Record what `ttfx` is, its licence, layout, dependencies, whether its engine can emit frames apart from the terminal writer, and which glyphs and colours its 37 effects use over the K230 banner. Proof: `python3 -I tools/textfx_frames.py survey --ttfx <host build of ttfx 14ed274> --banner nix/exhibition/K230.txt --seed 3` (host) reproduces the table in `docs/evidence/boot-text-effects/ttfx-research.md`. Host evidence only.
  Done 2026-10-30 (host): table and findings in `docs/evidence/boot-text-effects/ttfx-research.md`; 37 of 37 effects deterministic across repeat runs and parseable as SGR 0/38;2 only. The host `ttfx` was a cargo build of the `14ed274` checkout; `nix build .#ttfx-host` (added in this change) is queued behind the shared build lock and the hashes will be repeated against it.
- [ ] 1.2 Confirm the packaged riscv64 `ttfx` (`nix/ttfx.nix`, `.#ttfx`) emits byte-identical `--parity-dump` frames to the host build of the same revision. Proof: `docs/evidence/boot-text-effects/board-dump-hashes.txt` with the host and board SHA-256 per effect/seed; the board run is a process run on the live system, not a boot observation.

## 2. Host tool and portable renderer

- [x] 2.1 `tools/textfx_frames.py`: run the pinned `ttfx` with `--parity-dump`, parse the frames into character cells, write a versioned cell-sequence file (`TFXS`), and print a per-frame and whole-sequence hash. Proof: `python3 -I tests/test_textfx_frames.py` (host); the same seed gives the same hashes twice, and a different seed does not.
  Done 2026-10-30 (host): `tools/textfx_frames.py` and `tests/test_textfx_frames.py`, 9 tests pass, output in `docs/evidence/boot-text-effects/host-textfx-tests.txt`. Golden hashes pin ttfx `14ed274` (wipe, seed 3, 35x38: 138 frames, dump sha256 `0cac956c...`, sequence 16 506 bytes).
- [x] 2.2 `src/textfx.{h,c}`: freestanding C (no libc calls) that applies a `TFXS` frame to a cell grid and blits glyphs into an XRGB8888 or RGB565 target, with a generated 8x16 font table and a visible fallback glyph, and a live-ANSI frame parser for the player. Proof: `TTFX=<host ttfx> UNIFONT_BDF=<unifont.bdf> python3 -I tests/test_textfx.py` (host): the C sequence reader, the C live-ANSI parser and the C blitter (XRGB8888 and RGB565, incremental and full redraw) agree with `tools/textfx_frames.py` and with an independent Python renderer that reads the BDF directly.
  Done 2026-10-30 (host): `src/textfx.{h,c}`, generated `src/textfx_font.c` (608 Unifont 17.0.04 glyphs, reproducible from `tools/gen-textfx-font.py`), `tests/textfx_harness.c`, `tests/test_textfx.py`: 4 tests pass over all 138 wipe frames, pixel hashes equal at frames 0, 1, 40 and 137. The licence notice travels in the generated file; no board, U-Boot or QEMU run.
- [ ] 2.3 Choose the default effect and canvas from measurements of the candidates at the panel's real grid (frame count, changed cells per frame, sequence bytes, glyph coverage). Proof: the table in `docs/evidence/boot-text-effects/effect-candidates.md` produced by `tools/textfx_frames.py survey`; the choice is then written into `design.md` and this task is ticked.

## 2b. A no_std ttfx engine for stage 1

- [x] 2.4 Feasibility: what separating the engine from the terminal writer takes, std dependencies, floating point, the U-Boot target's FPU, memory per effect, linking a staticlib. Proof: `docs/evidence/boot-text-effects/nostd-feasibility.md` (host evidence; reads `readelf -A` of the built U-Boot and the pinned tarball).
  Done 2026-10-30: bounded, about 600 hand-written lines in a 73-file patch, FPU off so soft-float `riscv64imac`, engine 125 to 520 KB depending on the effects, heap 1 to 13 MiB per effect.
- [x] 2.5 The `no_std` patch and parity: `nix/ttfx-nostd/ttfx-nostd.patch` against `14ed274`, the std CLI unchanged. Proof: `cargo test --release` on the patched tree (37 unit and 11 integration tests pass), `--parity-dump` identical to unpatched for 37 effects in both engines (74 of 74), and `TTFX=<std ttfx> TTFX_NOSTD_SRC=<patched source> FW=1 FULL=1 RISCV_CC=<riscv64 gcc> python3 -I tests/test_ttfx_nostd.py` (output: `docs/evidence/boot-text-effects/nostd-parity-full.txt`).
  Done 2026-10-30 (host build/test; the riscv64imac staticlib ran under `qemu-riscv64-static`, user mode, which proves the machine code and says nothing about speed or U-Boot): 148 of 148 host streams and 37 of 37 firmware streams byte-identical to std ttfx.
- [ ] 2.6 `nix build .#k230-ttfx-boot` (patched source, official `rust-std` for `riscv64imac-unknown-none-elf`, `Cargo.lock` vendored) and record the staticlib size. Proof: that command's output path and `nm`/`readelf` of the archive. Laptop claim; queued behind the shared build lock.
- [ ] 2.7 Record codec and per-boot selector in portable C: `src/textfx_record.{h,c}` (payload of source id 2, D5) and a selector over the effect and text lists (D11), with a host test. Proof: `python3 -I tests/test_textfx_record.py` (host).
- [ ] 2.8 The engine bench on the board: `nix/ttfx-boot/bench/bench.c` linked with the staticlib into a static soft-float executable, run for every effect in the subset over the K230 banner under the board lock. Proof: `docs/evidence/boot-text-effects/board-engine-bench.txt` with frames, bytes, FNV hash (equal to the host's) and milliseconds per effect. Board process run on the live system, not a boot observation.

## 3. Early-Linux live player

- [ ] 3.1 `k230-textfx` player (C, `nix/textfx/`), a Nix derivation, and a NixOS option that is off by default: reads `ttfx --parity-dump` from a pipe, skips to a frame given on the command line after checking its cell-grid hash, paces at the sequence frame rate, renders cell deltas, supports `--output-file` (no DRM) and the splash owner's ready-file/`SIGUSR1` protocol. Proof: `nix build .#k230-textfx` (target build, laptop claim) and `tests/test_textfx_player.py` against the host build.
- [ ] 3.2 Start the player by hand on the running board with `--output-file`, under the board lock, and compare its framebuffer hashes with the host reference. Proof: `docs/evidence/boot-text-effects/board-offscreen.txt` (board process run, no glass).
- [ ] 3.3 Start the player by hand against DRM on the running board (stopping and restoring the shell under the board lock, or an equivalent that leaves the user's session intact) and record the KMS calls, exit status and measured CPU per frame. Proof: `docs/evidence/boot-text-effects/board-drm.txt` (board process run). A claim about what the glass shows needs camera or glass evidence and is not made here.

## 4. Stage 1 playback (waits for Life's interface and the operator)

- [ ] 4.1 Add the text-effects frame source (source id 2) to the generic stage 1 loop once `src/boot_frame.h` is on `master`: the engine library linked in, the effect/text/seed selection of D11, the replay fallback of D1b, and the record of D5. Proof: `nix build .#uboot-k230-boot-textfx` (laptop claim). Writing it to a board is task 4.2.
- [ ] 4.2 Install the stage 1 build by the plan in `design.md`, verify readback and a console transcript of one `K230#` run (with and without `tfx_*` overrides, and with the engine forced to fail so the fallback runs), and keep the rollback. Not started: **HARD STOP**, requires the operator's go-ahead and board reservation.
- [ ] 4.3 Decide how stage 1 animates while U-Boot loads (D12) from the cyclic-framework research on the Life branch and the engine bench of 2.8. Proof: a design note and the frame period achieved in the 4.2 transcript.

## 5. Placement in Linux and handoff (waits for the operator)

- [ ] 5.1 Decide and measure the earliest practical start (rootfs unit versus initrd unit) from a boot trace, and write the exact change to kernel-adjacent files in `design.md`. Not started: initrd or bootargs changes are a **HARD STOP**.
- [ ] 5.2 Enable the player at boot, hand the display to the shell, and record the journal timing. Proof: serial/journal transcript under `docs/evidence/boot-text-effects/` (boot observation).

## 6. Physical proof (stays open)

- [ ] 6.1 Film a power-on or warm boot showing the stage 1 sequence, the pause, the live continuation and the shell's first frame, with the film aligned to kernel time. Verify with a committed film and frame timings. **Physical**; the webcam is not used for this change without the operator's say-so.

## 7. Review

- [ ] 7.1 `openspec validate the-boot-plays-terminal-text-effects --strict` and `python3 scripts/render_work_board.py` after commit (host).
