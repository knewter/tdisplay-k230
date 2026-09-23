# Padded scanout: real GPU submission, color mismatch retained

Board trials on 2026-09-23 at 16:26:23 UTC (GPU) and 16:27:56 UTC (forced
Pixman). Renderer source `ead54046b786a073f6ac880dde0f4838a6d78dee`, landed as
`db751008`; cross-build `/nix/store/iy08ig1xw3xhhh1ph31g5jy59lj04f19-sway-1.12`.
The exact unwrapped executable and trusted synthetic client are in each
`result.json`. Both modes use the same compositor, native RGB565 panel, scale
one, and **1152-byte padded pitch**. Normal installed Sway remains unchanged.

## Actual outcomes

| Mode | Completed GPU frames | Pixman replays | Visible prerequisite | Recovery |
| --- | --- | --- | --- | --- |
| GPU diagnostic | 196 | 0 | Passed | Normal shell restored |
| Forced Pixman | 0 | 576 | Passed | Normal shell restored |

The same Sway/wlroots DRM backend owns the output; the renderer uses its supplied
buffer, with no independent DRM open/modeset/commit path. Only one Sway PID was
observed in each run, and kernel scanout state reports DRM RGB565. Decision logs
record single-plane linear dma-bufs, offset zero and stride 1152. The GPU trial
records actual successful full-frame submissions. Forced replay is selected by
the existing cache opt-in flag set to zero, retaining `WLR_RENDERER=vglite` and
the same padded allocator. It records `opt_in_disabled` and no GPU submissions.

This satisfies the bounded scene-selection/submission observation in task 3.1.
It does **not** satisfy ordinary-user service access, source/target color
correctness, cache ownership, normal controls under GPU, or performance gates.
This root-owned diagnostic is separate from the proposed normal-service broker.

## Capture and color review

The executed checker is `../padded-check.py`; it runs the bounded root scene
harness with a 30-second animated parent/desynchronized-child fixture. Before
retaining PNGs it requires a native PPM capture with recognizable blue parent
content at multiple locations. Mapping a window over IPC alone is insufficient.
The coordinator reviewed both later PNGs: parent bands, child bands/counter,
placement and panel coverage are visible in both modes.

The animations have different frame counters, so directly comparing complete
screenshots would confuse motion with rendering error. Instead,
`analyze-palette.py` compares the parent and child color sets in fixed regions
away from the counters, checking the same colors across both captures per mode.
Its output is retained in `palette-comparison.json`; **MISMATCH is expected and
is not waived**. For the brighter bands:

| Region | GPU RGB | Pixman RGB |
| --- | --- | --- |
| Parent | 33, 113, 173 | 33, 113, 181 |
| Child | 222, 142, 33 | 231, 146, 33 |

The darker bands match. The differing channels are one RGB565 code step apart.
This evidence identifies a conversion/quantization discrepancy; it does not yet
establish its cause or an acceptable correction. Exact source upload/conversion
and cache/correctness acceptance remain open. No tolerance was increased.

The raw frame totals also do not establish a speedup. The free-running fixture
completed fewer frames under GPU. Capture/startup costs and nonidentical frame
sequences make this a diagnostic comparison, not the required wall/process
CPU/system/interrupt benchmark. All performance gates remain open.

## Reproduction, recovery and limits

The checker invokes the same private root-owned harness and unprivileged
Wayland client used in the earlier scene trial, with its independent recovery
timer. `--force-pixman` selects the paired replay mode without changing scanout
allocation. Seven host lifecycle/configuration checks passed, including the
new same-allocation comparison mode and retained client isolation.

Both controller runs exited zero, found normal shell and seatd active, and
recorded the restoration marker. The normal image and boot ID are unchanged in
their manifests. `restoration.json` records a separate injected normal-control
regression after the pair. No flash, battery, real-finger or optical proof is
claimed. Source/format/clip, synchronization, user-service access and measured
interaction costs must still be resolved before considering any default change.
