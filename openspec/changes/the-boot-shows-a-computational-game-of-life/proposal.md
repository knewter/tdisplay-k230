## Why

The current splash handoff preserves a static image into Linux, but the first
Sway modeset still produces incorrect physical geometry and colors. Once that
blocking defect is fixed, a computational Game of Life gives the boot display a
small, meaningful workload and a visible transition into the shell without
promising uninterrupted animation during kernel startup.

## What Changes

- Add a deterministic, portable C Game of Life engine shared by U-Boot and early Linux.
- Store a versioned state and last rendered frame in reserved RAM so the next owner can continue from known state when the handoff is valid.
- Render a deterministic default pattern and seed; permit transient same-boot state only, never home-directory backup or cross-boot user state.
- Let Linux touch input drop a glider into the simulation once the touch driver and renderer are active.
- Investigate an optional U-Boot touch path by porting Goodix input into U-Boot, using the existing Linux driver as a reference; mark it hardware-unverified and do not require it for the first implementation.
- Allow an optional Wayland continuation after the shell starts, with the shell retaining ownership of normal controls.
- Require the current static splash geometry/color handoff defect to be fixed before this change is accepted.
- Document the expected apparent pause between U-Boot exit and Linux rendering; strict uninterrupted motion during kernel boot is out of scope.

## Capabilities

### New Capabilities

- `runtime/boot-game-of-life`: A deterministic shared boot animation with bounded state handoff and touch interaction.

### Modified Capabilities

- None.

## Impact

The change affects the vendored stage-1 display path, Linux early userspace or
kernel handoff, reserved RAM ownership, and optionally the Wayland shell. It
must not depend on the unproven second RISC-V core. The host can test the pure C
engine and deterministic images; the physical board is required for panel
handoff, touch, RAM reservation, and boot timing evidence. No current task is
complete until those future hardware checks are recorded.
