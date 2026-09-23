## 1. Experimental renderer boundary

- [ ] 1.1 Add a source-built single-context renderer library and explicit experimental shell option; verify narrow renderer and fallback builds without changing the default toplevel closure.
- [ ] 1.2 Create/export/import a renderer-owned RGB565 dumb-buffer dma-buf with `VG_LITE_BGR565`; verify focused host tests cover ownership, cleanup, and no live-buffer import path.
- [ ] 1.3 Implement explicit GPU completion, CPU cache handling, and discovered DRM handoff completion; verify a focused test records each producer/consumer transition.

## 2. Controlled board trial

- [ ] 2.1 Render opaque RGB565 and premultiplied-alpha validation scenes into the private buffer, then display only through the existing owner; verify board samples, a panel recording, and no unrelated DRM modeset. Hardware proof only.
- [ ] 2.2 Run touch, keyboard, Apps, Back/Home, Terminal, Monitor, and system-control regressions under the trial and forced fallback; verify transcripts distinguish injected and physical input. Hardware proof only.
- [ ] 2.3 Compare repeated frame wall, process CPU, and whole-system CPU/interrupt evidence against the same Pixman scene; verify the report states variance and does not convert process CPU into a device-wide performance claim. Hardware proof only.

## 3. Decision

- [ ] 3.1 Document cache/fence, color, interaction, ownership, and comparison outcomes; verify `openspec validate the-shell-trials-vglite-composition --strict` and `./tools/blob-scan.py --no-vendor` pass.
- [ ] 3.2 Make a promotion or removal decision only after all board gates pass; verify the default remains Pixman unless the recorded evidence supports a separate default-change proposal.
