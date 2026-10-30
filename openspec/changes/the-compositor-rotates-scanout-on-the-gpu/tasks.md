## 1. Cost of the pieces, without the compositor (board, after the kernel change lands)

- [ ] 1.1 Standalone rotate bench: a root probe rotates a 1232x568 RGB565 contiguous source into a padded 568x1232 destination 300 times with `vg_lite_blit` (90 degree matrix), with and without the C908 cache clean of the source, recording CPU time and wall per rotation against the existing CPU turn (`compositor-repaint/turn-bench.c.txt`). Proof: probe output and a parser under `docs/evidence/vglite-turn/`. Board observation (private buffers; not compositor evidence).
- [ ] 1.2 Decide the gate: continue only if GPU rotation CPU per frame (including the cache clean) is at most half of the CPU turn. Record the numbers in `docs/evidence/vglite-turn/`; otherwise close this change with the negative result.

## 2. Compositor profile (host)

- [ ] 2.1 Allocate the Pixman scratch image from contiguous memory and add the opt-in GPU turn with whole-frame CPU fallback to the output-turn patch. Proof: `nix build .#shell-compositor-vglite-turn --no-link --print-out-paths` and a host test comparing GPU-path and CPU-path output bytes with the mock device (as `tools/test-vglite-renderer.sh` does). Host build and mock only.

## 3. Board trial (hardware)

- [ ] 3.1 Same-boot GPU versus CPU turn on the drawer-scroll and keyboard-cycle workloads of `docs/evidence/interaction-jank/compositor-repaint/measure.sh.txt`: sway CPU per presented frame, repaint wall, presented interval, plus a `grim` capture comparison of identical scenes. Proof: committed `docs/evidence/vglite-turn/` with both modes and the analysers' output. Board observation, injected touch.
- [ ] 3.2 Controls: touch, keyboard, Apps, Back/Home under the GPU turn, and recovery by forced CPU fallback after an injected finish failure. Board observation, injected touch.
- [ ] 3.3 `openspec validate the-compositor-rotates-scanout-on-the-gpu --strict` and `./tools/blob-scan.py --no-vendor`; state in the result whether a proposal for GPU client composition (analysis ranks 2 and 3) is justified.
