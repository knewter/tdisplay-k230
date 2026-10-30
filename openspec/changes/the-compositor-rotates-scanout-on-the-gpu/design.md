## Context

Layers: wlroots renderer patch (userspace compositor), kernel device (supplied by `the-mainline-kernel-drives-the-vglite-gpu`), Nix package. Today `render/pixman/pass.c` (patched by `nix/patches/wlroots-k230-output-turn.patch`) composites the scene into a landscape RGB565 scratch image and, at submit, turns it into the portrait scanout buffer on the CPU, logging `K230_PIXMAN_OUTPUT_TURN ... rotation_cpu_ns=` (3.4 ms median in the committed drawer run). Profile evidence: [`docs/evidence/vglite-uses/README.md`](../../../docs/evidence/vglite-uses/README.md).

Facts carried from the committed GPU work: BGR565 targets and a padded 64-byte-aligned linear destination work (`docs/evidence/vglite-scene-board/padded`); one retained serialized context avoids the 107 ms per-pass setup (`context-lifetime`); a private-buffer 568x1232 job costs about 0.1 ms process CPU and 2 ms wall (`gpu-validation/cpu-timing-pass.txt`); the driver imports a dma-buf by its last scatter-gather address, so buffers must be physically contiguous.

## Decisions

### Rotate only, on compositor-owned buffers

Both buffers are owned by the compositor: the scratch image is allocated by the patched Pixman renderer, and the destination is the wlroots-supplied scanout buffer. Allocating the scratch from contiguous memory (a DRM dumb buffer or CMA allocation) means no client pixel is ever copied for the GPU, the property whose absence made the September trial lose. Rejected: a full VG-Lite renderer again (snapshot and upload copies), GPU composition of `wl_shm` surfaces (needs those copies), a second DRM client.

### Whole-frame GPU or whole-frame CPU

For each frame the compositor either rotates entirely on the GPU or entirely on the CPU (existing path); there is no per-region mixing. Any unproved condition (format, stride, an error from `vg_lite_finish`) selects the CPU path for that frame and, after a failed finish, for the rest of the session, as in the September fallback policy.

### Cache and completion

The scratch is CPU-written, so it is cleaned before submit; the destination is read by scanout after `vg_lite_finish` returns. The direction and cost of the C908 cache operations are the open question of `the-shell-trials-vglite-composition` task 2.4 and are measured here, not assumed. The CPU waits for completion before commit (no fence claim).

### Opt-in

A distinct Sway package and `K230_VGLITE_TURN=1` select the path. The default shell is unchanged unless the measurement gate passes and a separate default-change proposal is accepted.

## Risks / Trade-offs

- The cache clean of 1.4 MB may eat the saving: the proposal's first task is to measure exactly that on the board before wiring the compositor.
- A 2 ms GPU wait is wall time in the repaint; the gain is CPU freed for the client and the sway repaint wall, so both are recorded.
- Driver and broker work are prerequisites owned by other changes; this change cannot be accepted before they are.
