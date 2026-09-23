# VG-Lite scene rejection diagnostics

2026-09-23 UTC, `apply/vglite-composition`, base
`221fa17a462a5396b1e0a39cb9d9b1c69a6e33e2`. Source/host follow-up to a
coordinator-reported board session with renderer selection but only Pixman
replays. This checkpoint itself performs no board action.

## Deterministic source finding

Pinned wlroots 0.20.2 `types/scene/surface.c:290–318` assigns ordinary Wayland
surfaces `WLR_COLOR_TRANSFER_FUNCTION_GAMMA22` plus sRGB primaries, even without
client color-management requests. `types/scene/wlr_scene.c:1529–1556` passes
both into the renderer. The current experimental renderer rejects every nonzero
transfer function and every nonnull primaries pointer, so every such textured
scene is ineligible regardless of target format. This source finding explains
one guaranteed rejection; it does not establish the full runtime reason chain.

The initial scene background at `types/scene/wlr_scene.c:2574–2578` is black with
alpha **one**, with its clip restricted to uncovered damaged areas. It passes
the alpha check. A completely occluded background can have an empty clip.
Texture clipping and incomplete redraw remain separate guards. No guard is
loosened in this checkpoint, including the default color metadata guard.

## Fixed diagnostic schema

At debug logging level, each replay emits `VG-Lite decision v=1` with:
`result`, `reason`, zero-based `op` (`-1` for a pass/target condition), `ops`,
`target`, `dmabuf`, numeric `format`, `modifier`, `planes`, `stride`, `offset`,
and `vg_status` (SDK status when the first rejection is an SDK call, zero
otherwise).

A rejected operation also emits `VG-Lite operation v=1`, reporting rect alpha,
blend and clip rectangle count, or texture alpha/opacity, blend, filter,
transform, transfer, presence of primaries, luminance, encoding/range, source
and destination boxes, and clip rectangle count. The first rejecting condition
wins, except a disabled GPU or absent exact trial flag takes precedence.
No device fd, process address, client identity or pixel content is logged.

`result=attempt reason=eligible` is emitted only after operation/coverage,
dma-buf and CPU target-layout checks, immediately before cache handoff and
`vg_lite_init`. It proves reaching the submission path, **not** a successful
GPU operation. `result=gpu` follows successful completion/cleanup;
`result=failed` records a discarded/quarantined GPU pass. `result=pixman`
records the decision to replay, before Pixman submission; it does not itself
claim that fallback submission succeeded. Existing completion and full-pass
messages remain available for comparison with previous captures.

## Host proof

```sh
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
VGLITE_SOURCE=/tmp/k230-sdk-vglite-src/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
nix build .#shell-compositor-vglite --no-link --print-out-paths
```

The sanitizer-backed production-renderer suite passes. Added behavior tests
reproduce rejection of the actual scene-default GAMMA22/sRGB tuple, assert the
fixed target/operation fields and zero GPU attempts, and distinguish an opaque
full clear from alpha-clear and invalid-stride rejection. Injected init/map/
clear errors assert both stage and original numeric SDK status; subsequent
cleanup success cannot erase the first error. Existing Pixman pixel comparisons
and completion-quarantine tests still pass.

Physical gate: the reserved operator repeats the existing bounded root scene
harness with this rebuilt diagnostic Sway, captures its debug journal including
`decision` and `operation` records, and verifies normal-shell restoration.
Interpret `attempt`, completed GPU frame and actual visible correctness as
separate evidence. An eligibility change for scene-default color metadata
requires its own narrowly justified behavior/pixel test and board comparison;
this checkpoint does not approve arbitrary color-transform bypass.

Cross-build passed with wrapper
`/nix/store/zdqgq0c3ajqsyjazg6c94bcvb20w6kvj-sway-1.12`
and actual unwrapped diagnostic executable
`/nix/store/a78y0w6zaiyy86dhixgvdfalcj8b5bsc-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
The operator command, after importing that closure, is:

```sh
python3 tools/vglite-root-scene-trial.py --seconds 20 \
  --compositor /nix/store/a78y0w6zaiyy86dhixgvdfalcj8b5bsc-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  -- <trusted-self-terminating-probe> <probe-arguments>
```
