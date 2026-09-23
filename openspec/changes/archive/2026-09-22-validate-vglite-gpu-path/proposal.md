## Why

The shell still composes through Pixman because the proven GPU result covers
only opaque RGBX private buffers. A compositor integration would be unsafe to
assume until RGB565, alpha/color behavior, and a DRM dma-buf import have been
measured without taking over the live display.

## What Changes

- Add an optional source-built VG-Lite validation package with private-buffer
  RGB565 and alpha/color probes, a no-master DRM dumb-buffer export/import
  probe, and comparable GPU/Pixman timing output.
- Record the board-only procedure and evidence contract, including explicit
  completion points and the limits of a passing result.
- Keep the package outside the image closure and leave Sway, DRM master,
  scanout, services, and boot configuration unchanged.

## Capabilities

### New Capabilities
- `runtime/gpu-validation`: A bounded, privileged GPU validation path that
  proves individual prerequisites before any compositor integration.

### Modified Capabilities

None.

## Impact

Adds `nix/vglite-probe*`, an optional flake package, GPU-specific research and
evidence documentation, and this change's planning artifacts. It requires the
physical board only for the runtime checks; narrow cross-build and static
validation run on the build host.
