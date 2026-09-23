# Actual scene trial: Pixman fallback and its rejection reasons

Two bounded board sessions on 2026-09-23 used the experimental wlroots renderer
inside Sway's existing DRM backend. Neither submitted a GPU frame. These are
negative acceleration findings, not hardware promotion or normal-service GPU
acceptance. The normal shell and seatd recovered after both sessions.

| Run | Source revision | GPU frames | Pixman replays | UTC start |
| --- | --- | ---: | ---: | --- |
| Initial mapped synthetic scene | `3a296b5` | 0 | 230 | 07:37:37 |
| Fixed-schema diagnostic | `1b155b6` | 0 | 224 | 07:53:19 |

Each run's `result.json` records exact immutable compositor/client paths, the
installed system closure, boot ID, scanout format, sole observed Sway PID,
exit status and service restoration. The trial used RGB565 at 568x1232, scale
one. No image flash, device permission change, second DRM owner, or persistent
service override was performed. The root diagnostic and its separately launched
unprivileged synthetic client do not prove the normal shell service's access
boundary. Its prior credential-isolation prerequisite is recorded in
`../vglite-isolation/`.

## Commands and retained evidence

The coordinator reserved `/tmp/k230-board.lock`, imported only missing Nix
closure paths over the private network with matching SHA-256 and successful
`nix-store --import`, then uploaded the committed per-run `check.py` and
`tools/vglite-root-scene-trial.py`. The actual board invocation for the second
run was:

```sh
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /run/gpu-diagnostic-check.py > /run/gpu-diagnostic-check.out 2>&1
```

The copied checker contains the exact bounded harness/client arguments and
native `grim` capture commands. The harness arms recovery before replacing
the normal shell and tears down both diagnostic cgroups before restoration.
The diagnostic `decisions.log` retains only the fixed numeric renderer records;
the unrestricted root-private journal and transfer addresses are not published.

An initial attempt used an unsupported synthetic app ID and the client exited
64 before mapping. `initial/rejected-app-id.json` retains that failure. The
corrected runs use the fixture's supported `k230.card.one` ID. It is a test
surface with independently changing parent and child buffers, not a product
application or a card-shell acceptance run.

## What the diagnostics established

Of 224 replay decisions, 220 rejected `texture_transfer`: the ordinary surface
has transfer value 8 (GAMMA22), primaries present, luminance one, opacity one,
and no YCbCr encoding/range. Four clear-only passes rejected
`target_attributes`. Every logged target has one linear RGB565 plane, offset
zero, and **stride 1136 bytes**. The renderer currently requires 64-byte stride
alignment, so the actual width-times-two target fails even without textures.
No record reaches `result=attempt` or `result=gpu`.

The full-size parent texture also has four clip rectangles due to child
occlusion. Since the color rejection stops later preflight, these logs do not
prove whether clip/coverage would pass after a color fix. Target allocation,
clipping, and partial damage must be investigated independently; this finding
does not justify removing their checks.

The subsequent source/host-tested exact default-color exception is documented
in `../vglite-default-scene-color.md`. It was **not** the package in these
board runs, and does not resolve the observed target stride.

## Visual inspection and limits

The coordinator inspected the native PNGs. The initial scene and diagnostic
later capture show the synthetic striped parent and contrasting child with
frame markers. The diagnostic first capture is entirely black: the checker
waited for IPC mapping, which did not guarantee visible presentation before
capture. It is retained rather than treated as successful content evidence.
Future visual comparison must wait for a presented/recognizable frame.

These captures and logs establish actual scene fallback and its first rejection
conditions. They do not establish exact GPU pixels, cache ownership, GPU frame
timing, touch usability, optical behavior, or product card performance. Those
proposal gates remain open. Pixman remains the normal default.

After the diagnostic, the coordinator ran `restoration-check.py` on the board
using the same board Python path above. `restoration-result.json` records PASS
for normal shell/seatd, injected Apps Next/Previous, keyboard show/hide while
preserving Apps, Terminal focus, and Apps Back. The checker imports the retained
pixel helper from `docs/evidence/launcher-gestures/metadata-budget/check.py`
(deployed as `/run/rollback_check.py`) and uses the existing injected device.
This is an installed-image recovery regression, not physical-finger acceptance
or a measured UI latency trial. The initial helper's CPU-heavy PNG processing
time is not a response-time measurement.

## Follow-up: actual GPU submission with padded pitch

The later [padded scene trial](padded/README.md) reached 196 GPU frames and zero
CPU replays. Its forced-Pixman comparison uses the same allocation. Source
colors differ by a quantization step, and no speedup is accepted. The original
zero-GPU records above remain unchanged.
