## Why

The handheld's native Apps launcher is reliable for taps and buttons, but a finger drag currently cancels the card instead of providing a useful page or window transition. A bounded client-side gesture and overview surface can give the shell a webOS-like cards experience while preserving the working Sway session, persistent bar, keyboard, and button fallbacks.

## What Changes

- Add explicit single-touch gesture recognition to the native launcher with a fixed movement threshold, directional classification, cancellation rules, and a bounded page transition.
- Let Apps page cards with horizontal swipes while retaining Previous, Next, Back, and direct taps.
- Add a lightweight window overview mode using Sway window metadata and focus actions, with title/state cards and no live thumbnails in the first phase.
- Preserve persistent bar controls, keyboard behavior, Home recovery, Help, launch-error recovery, and terminal focus semantics.
- Keep the first phase client-only: no Sway/wlroots fork, no GPU renderer, no screencopy thumbnails, pinch physics, or compositor-wide gesture policy.
- Measure CPU frame/update cost and memory at the existing 568x1232 Pixman/RGB565 configuration; mark real-finger and final-glass gesture evidence separately from injected tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: add touch launcher paging and a metadata-only window overview while retaining existing controls and recovery behavior.

## Impact

The change affects `nix/touch-launcher`, its launcher packaging and tests, the shell's launcher/menu integration, and shell evidence. It uses existing Wayland layer-shell, `wl_touch`, Sway IPC, and terminal/window focus paths. It does not require kernel, device-tree, compositor, or GPU changes. Physical-board validation is required for real-finger gesture behavior and panel readability; injected input and host tests can validate state-machine correctness and fallback behavior first.
