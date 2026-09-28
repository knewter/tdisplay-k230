## Why

A tap on the physical bottom/power button currently resets the handheld immediately. That loses the current session and makes the button unusable as a normal display sleep/wake control. The user wants a short press to turn the display off or on and a deliberate hold to show a power menu whose destructive actions require confirmation.

## What Changes

- Make the board's PMU power-key press and release observable by Linux, with hardware reset behavior diagnosed separately from software policy.
- Toggle only the display on a short press. A press while the display is off wakes it without activating the app beneath the finger.
- Open a shell power sheet after a deliberate hold; Cancel closes it, and Power off and Restart require a second explicit confirmation. A hold by itself never shuts down or reboots.
- Preserve the existing Settings power controls and brightness across display off/on.
- Prove actual button timing, panel recovery and confirmation behavior on the physical board before claiming the feature.

Non-goals: suspend-to-RAM, battery operation, a hardware RESET switch if the user's button is actually wired directly to reset, and autonomous long-press power cutoff for an unresponsive kernel. The physical button identity is a named first evidence gate.

## Capabilities

### New Capabilities

- `system/power`: Linux PMU key events and safe power-key policy on this board.

### Modified Capabilities

- `runtime/shell`: a global, touch-friendly power sheet opened by the physical key, with explicit confirmations.

## Impact

The kernel and device tree need the PMU INT0 input path; the image must carry the required configuration and safe default policy. The Sway/shell session needs a key event route, display off/on action and power sheet. The reserved board, serial console and native display capture are required for acceptance; host tests and QEMU can verify state transitions but cannot prove the key or panel.
