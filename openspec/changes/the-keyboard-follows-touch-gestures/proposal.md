## Why

A person can type on the handheld but cannot readily discover how to show or dismiss the keyboard. The user also wants dismissal to follow their fingers and settle smoothly, consistent with app navigation.

## What Changes

- Provide an explicit two-finger upward gesture from the bottom edge to reveal the external on-screen keyboard, preserving one-finger app navigation.
- Add a visible themed handle above the shown keyboard; dragging it down tracks contact directly and smoothly settles to hidden or shown on release.
- Keep typing, app touch streams, focus, and keyboard-exclusive space correct through cancellation, second contacts, interrupted transitions and service failure.
- Retain a clear Settings Keyboard action and a short gesture hint as discoverable alternatives.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: Add explicit gesture control and direct manipulation of the on-screen keyboard in the coherent shell.

## Impact

Userspace compositor input/scene policy, keyboard lifecycle integration, themed grip and Settings text, Nix session wiring, host/native QEMU checks and separate real-glass proof. No kernel, device-tree or stage-1 changes. Physical panel/touch proof is required for completion. Non-goals: replacing wvkbd, changing its key layout, interpreting drags on ordinary keys as dismissal, adding haptics, or replacing the Wi-Fi password editor's explicit close/cancel controls.
