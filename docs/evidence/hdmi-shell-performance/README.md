# Portrait HDMI rendering checkpoint

This change is experimental and open. No performance winner or default image
has been selected. The physical acceptance tasks remain unchecked.

The HDMI trial uses Sway output transform 90 at physical 1920×1080 and logical
1080×1920. Pixman performs software rotation. The renderer candidate does not change the panel driver. The HDMI mapping
now compensates absolute touch calibration independently, as described below. The committed DRM dump advertises rotation only
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
[recovered output](recovered-pixel-check.txt). The telemetry test and eleven strict parser/dispatch fixtures also passed.
The capture and scene entry points now delegate to their bounded helpers.
The board helper has separate mocked capture/cleanup fixtures; these are host
proof, not observations from the board.

The reconstructed final-frame patch now compiles as part of the native pinned
wlroots build. A socket-free public-render-pass probe confirms rotation
direction and byte-exact nearest-filter output for both quarter turns and
ARGB8888/RGB565. It also reproduces bilinear differences; see
[the probe and measured limits](../../../tests/pixman-output-turn/README.md).
This is small-surface renderer proof, not a running Sway scene or board proof. A prior headless run was blocked by sandbox Unix-socket
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
capture, keyboard/shade checks or latency gate; no recognition threshold
change is justified by that earlier observation alone. The later
operator correction below proves a separate orientation mismatch.

Next gates are reconstructed scene/pixel proof, exact cross-build identity,
reserved one-/two-card physical trials, and normal-panel recovery. Mainline
kernel porting proceeds separately. No archive is justified at this checkpoint.

## Reproducible capture entry points

The capture helper runs **on the board**, where the live Sway IPC socket and
compositor journal are available. Reserve the board before invoking it. Stage
`tools/hdmi-shell-performance.py` and `tools/hdmi-shell-capture-board.py` together.
Supply the exact source revision used to build the installed compositor; the
helper also records hashes of the actual executable and mapped Pixman library.
A supplied revision alone does not authenticate binary/source correspondence.

For injected profiling with exactly one or two already-open Foot windows:

```sh
python3 tools/hdmi-shell-performance.py --capture --variant candidate \
  --input injected --source-revision DEPLOYED_COMPOSITOR_REVISION \
  --seconds 120 --drags 24 --output NEW_CAPTURE_DIRECTORY
```

For physical contact, use `--input physical --operator-confirmed-contacts`.
After READY, swipe up from the ordinary app into overview, then make 24 center
horizontal drags. Record the operator observation separately. Baseline requires
both rotation opt-ins off; candidate requires an opt-in in the actual process
environment. Run one- and two-card workloads in separate new directories. The
helper never launches/closes apps or changes output settings; it stops the
benchmark, returns from overview and checks output/window counts after capture.
Failed cleanup and incomplete traces are not accepted measurements. Their
allowlisted `capture.log` is retained for routing diagnosis, while
`metadata.json` has no accepted runs.

The host scene entry point currently exercises the **per-texture** candidate,
stock 90-degree sampling, and 180-degree fallback with a changing native client:

```sh
python3 tools/hdmi-shell-performance.py --check-scene --variant candidate \
  --sway UNWRAPPED_RISCV_SWAY --client NATIVE_ANIMATED_CLIENT \
  --output NEW_SCENE_DIRECTORY
```

It requires QEMU user emulation, Grim and permission to bind Wayland sockets.
It is not proof for the final-frame candidate. The current runner cannot bind
those sockets or reach the Nix daemon, and has no serial device, so runtime,
cross-build and physical tasks remain open.

## HDMI touch axes correction

On 2026-09-29, the operator clarified that touch was still rotated: a physical
left-to-right swipe triggered the drawer's bottom-to-top gesture. This supersedes
the earlier inference that recognizing the screen orientation had resolved touch
mapping. No successful physical acceptance is claimed here.

Pinned wlroots `types/wlr_cursor.c` applies the mapped output's transform to
both touch-down and touch-motion coordinates. Sway
`sway/commands/output/transform.c` inverts clockwise CLI degrees into Wayland
anti-clockwise enums. At CLI transform 90, the resulting enum270 maps raw
`(x,y)` to `(y,1-x)`: left-to-right motion becomes upward motion.

The board's glass retains its native portrait axes while controlling the
external monitor. `nix/hdmi-touch-calibration.nix` supplies the compensating
affine matrix for each supported HDMI transform. For the current 90-degree
profile it is `0 -1 1 1 0 0`; wlroots subsequently maps the calibrated point
back to `(x,y)`. `nix/shell.nix` applies it only when HDMI is active, after mapping touch to it, and
explicitly restores identity calibration in the panel configuration on reload.
This uses Sway/libinput configuration and does not change the touch driver or
gesture thresholds.

A socket-free native test evaluates the Nix matrices and feeds synthetic
calibrated contacts through the compiled pinned wlroots cursor/touch APIs:

```sh
python3 tests/test_hdmi_touch_mapping.py \
  --wlroots-source PATH_TO_BUILT_PINNED_WLROOTS \
  --output docs/evidence/hdmi-shell-performance/touch-mapping-native.json
```

All four rotations passed nine points each for both down and motion, including
corners, horizontal and vertical swipes, and output-layout coordinates. The
uncalibrated control failed the expected coordinate assertion for every rotated
output. [Results](touch-mapping-native.json) record the actual library/source
hashes and limits. The affine libinput step is simulated; installation, device
calibration support and real glass remain unverified.

For a reversible live trial on the current transform-90 board session:

```sh
SWAYSOCK=/run/shell/sway-ipc.sock swaymsg 'input type:touch calibration_matrix 0 -1 1 1 0 0'
```

The operator must confirm that upward glass swipes open overview and horizontal
glass swipes remain horizontal. The prepared Nix source has not been built or
installed by this constrained runner. The normal panel remains a separate
identity-calibration case requiring its named regression check.

## Access-restored board and cross-build checkpoint

Tool permissions were subsequently restored. Both the trial package and
ordinary system cross-build succeeded; [build identities](cross-build.json)
record the exact source revision, command and store outputs. The runtime
calibration was applied over the reserved physical serial console and
`get_inputs` reports the expected six values; see
[live board configuration](touch-calibration-board.json). This is configured
state observed on the board, not real-finger acceptance. Coherent-profile
deployment and the operator's direction check remain separate gates.


### Activation regression and correction

The first coherent-profile activation returned touch calibration to identity.
The generated follow-output script passed the matrix as separate `swaymsg`
arguments; its negative coefficient was parsed as an option (`invalid option
-- '1'`). The interactive command had quoted the complete IPC message and
therefore worked. Both generated input commands now quote the whole message.
The operator reported the pre-activation direction fix working, then reported
rotation and performance regressing after the profile switch. The faster
per-texture trial was restored and the quoted calibration reapplied.

`k230-coherent-shell-hdmi-trial` explicitly retains the opt-in per-texture
renderer in a reproducible system profile (`WLR_PIXMAN_QUARTER_TURN=1`,
`WLR_PIXMAN_OUTPUT_TURN=0`), rather than depending on a runtime service override.
The ordinary coherent profile remains the performance comparison baseline.
Neither this profile nor the operator's qualitative speed report meets the
unchecked frame budgets, full scene correctness, or normal-panel regression
requirements. Physical trial results and deployment identity are recorded
separately when observed.
