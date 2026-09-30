# Portrait HDMI rendering checkpoint

This change is experimental and open. No performance winner or default image
has been selected. The physical acceptance tasks remain unchecked.

The HDMI trial uses Sway output transform 90 at physical 1920×1080 and logical
1080×1920. Pixman performs software rotation. This changes neither the panel
driver nor touch calibration. The committed DRM dump advertises rotation only
on a YUV video overlay, not the RGB desktop plane.

The opt-in `card-shell-hdmi-trial` package contains two alternatives:

- `WLR_PIXMAN_QUARTER_TURN=1` freshly copies eligible textures in tiles before
  ordinary composition; scaled bilinear input retains the stock sampler.
- `WLR_PIXMAN_OUTPUT_TURN=1` composes a logical frame into per-pass scratch and
  rotates it once directly into the physical target. Normal/unsupported formats,
  visible software cursors and damage highlighting retain the original path.

Scratch allocation is capped at 64 MiB. Neither path changes normal defaults.
Per-draw and final-copy traces are bounded; frame CPU measurement must include
the entire copy. Touch diagnostics record routing coordinates and event origins
without device names, application text or network settings.

## Recovered source proof

After the execution environment discarded `/tmp` checkouts, the original ten
HDMI implementation files were recovered from their intact worktree. In the
persistent checkout, these commands passed:

```sh
python3 tests/test_pixman_quarter_turn.py
python3 tests/test_card_shell_telemetry.py
python3 tools/hdmi-shell-performance.py --self-test
```

The pixel test passed 1,152 exact comparisons against stock Pixman, including
crop/scale, opacity, rounded clips, damage and source updates. See
[recovered output](recovered-pixel-check.txt). The telemetry test and nine strict
parser fixtures also passed. The capture and scene entry points are still pending
integration; parser tests deliberately reject those unavailable modes.

The reconstructed final-frame patch passed source/application checks. It has
not yet been rebuilt or exercised as a scene after recovery. Its predecessor
compiled natively before environment loss, but that is not proof for this
reconstructed source. A prior headless run was blocked by sandbox Unix-socket
`bind()` returning `Operation not permitted`; it was not passing scene evidence.

## Correctness and physical limits

A prior host diagnostic compared normal composition followed by final rotation
against stock per-texture affine rotation. All 576 nearest-filter cases matched;
336 of 576 bilinear cases differed, by up to three ARGB8888 channel steps or one
RGB565 channel step in the tested patterns. The diagnostic source/build artifact
was lost with `/tmp` and must be reconstructed before this finding becomes a
reproducible acceptance result. It is recorded as a limitation, not as a passing
pixel gate or permission to relax the requirement.

The first per-texture board trial remained slow. The earlier committed board
baseline also shows expensive rotated software composition. Neither establishes
the proposal's controlled 24-drag budgets for the final-frame candidate.

The operator reported that app-edge gestures worked after recognizing the
touchscreen's 90-degree orientation. This does not complete the named physical
capture, keyboard/shade checks or latency gate; no recognition threshold or
calibration change is justified by that observation alone.

Next gates are reconstructed scene/pixel proof, exact cross-build identity,
reserved one-/two-card physical trials, and normal-panel recovery. Mainline
kernel porting proceeds separately. No archive is justified at this checkpoint.
