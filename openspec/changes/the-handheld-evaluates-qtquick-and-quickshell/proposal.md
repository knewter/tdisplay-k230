## Why

We cannot yet tell whether Qt Quick apps or a Quickshell UI would feel responsive on this handheld. Source research identifies a CPU-rendered route, but a working desktop example does not establish the device's memory, touch, frame cost or recovery behavior.

## What Changes

- Package an opt-in minimal Qt Quick Wayland app using the software scene graph, with text, images, scrolling, tapping, an editable field and interruptible motion.
- Record the actual RISC-V build, Qt/QML interpreter or JIT configuration, runtime closure, backend and Wayland buffer path.
- Compare startup, memory, idle CPU, active CPU and presentation/input timing with an equivalent small SHM client on the same Sway session and image.
- Trial a minimal Quickshell layer-shell panel only after the Qt Quick prerequisite passes; verify focus, input regions, interaction with shell gestures, and cleanup separately.
- Publish separate decisions for ordinary Qt Quick apps and Quickshell shell surfaces, with exact evidence and gaps. Unsupported shader effects are explicit negative controls.

**Non-goals:** Replacing Sway or the live-card compositor, porting the full Omarchy shell, enabling software GL, adding a VG-Lite/Qt graphics bridge, integrating Qt Multimedia or Qt Virtual Keyboard, or changing the default image/session before an adoption decision. This is an evaluation, not a promise of smooth Qt applications generally.

## Capabilities

### New Capabilities

- `runtime/qtquick-validation`: reproducible, opt-in toolkit trials with verified rendering identity, comparable cost measurements, input/recovery observations and bounded adoption decisions.

### Modified Capabilities

None. The normal shell contract is retained.

## Impact

Nix probe packages, tiny userspace fixtures, a bounded trial/analysis tool, and committed evidence under `docs/evidence/qtquick/`. The source assessment is `docs/research/quickshell-qtquick-feasibility.md`. Host fixture checks and cross-builds can proceed without the board, using the shared build slot. Rendering, latency, real touch, keyboard interaction and restoration require an exclusive board reservation. No stage-1, kernel, device-tree, radio or flash change is presumed.
