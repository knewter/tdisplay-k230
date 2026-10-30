## Why

Scrolling the app drawer and raising the keyboard still cost the compositor a third of its CPU in a step no person sees: turning the finished landscape frame into the portrait panel's scanout buffer. On the board, sway spends about 3.4 to 4.0 ms of CPU per rotated frame on it (29% of sway's sampled time on drawer scroll, 21% on keyboard cycles), on a single core that the shell client shares. An earlier RVV attempt halved the work in isolation and gained nothing, because the writes to the scanout buffer set the cost ([`docs/evidence/interaction-jank/compositor-repaint/README.md`](../../../docs/evidence/interaction-jank/compositor-repaint/README.md)).

The ranked analysis in [`docs/evidence/vglite-uses/README.md`](../../../docs/evidence/vglite-uses/README.md) found this to be the one GPU use that needs no CPU copy of client pixels, which is what sank the September full-renderer trial. This change tests it on the real shell.

## What Changes

- Move the compositor's final quarter-turn into the scanout buffer from the CPU to VG-Lite, behind an opt-in profile. Source is the compositor's own RGB565 scratch image, destination is the padded scanout buffer wlroots already supplies. Pixman's rotation stays as the default and as the per-frame fallback.
- Measure it against the CPU turn on the same boot with the existing drawer-scroll and keyboard workloads: sway CPU and repaint wall per presented frame.
- Decide from that number whether the contiguous shared client buffers needed for GPU composition (analysis ranks 2 and 3) are worth a proposal.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: an opt-in compositor profile may perform the output rotation on the GPU.

## Impact

Touches the wlroots Pixman output-turn patch (`nix/patches/wlroots-k230-output-turn.patch`) and an opt-in Sway package; no client changes. Depends on `the-mainline-kernel-drives-the-vglite-gpu` (the device) and on the access broker of `the-shell-trials-vglite-composition` (compositor-only device access). Needs the physical board for every acceptance measurement.

Non-goals: GPU composition of client surfaces, client rendering on the GPU, YUV or video, text, changing the default renderer, any claim about energy.
