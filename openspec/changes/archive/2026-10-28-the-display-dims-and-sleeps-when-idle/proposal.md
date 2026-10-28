## Why

Left alone, the handheld's panel stays at full brightness until someone presses
the power key. On a battery device that is the largest avoidable drain, and a
panel left lit shows the same image for hours. Only the keyboard base's key
backlight has an idle timer (30 s). A person cannot rely on the screen resting
by itself, and a person who touches a dark panel has no defined result: the
touch could reach an app they cannot see.

## What Changes

- After 30 s without input the panel dims to 25% of its current brightness
  (never raising it); after 60 s the display turns off with the same
  `output * power off` the power key uses, so the key's toggle stays correct.
  Any input restores the exact prior brightness and power.
- The Timer and any video player keep the display lit while they are the
  focused card (Sway idle inhibitors).
- A touch on a dark panel wakes it and is consumed with its whole contact
  sequence; the app underneath never receives it. Base-keyboard keys wake
  through Sway and reach the focused app (accepted). The power key keeps its
  existing grabbed, consumed wake and now also restores idle dimming.
- The timeout is a fixed 30 s / 60 s in the image for now. A Settings choice
  (Off / 1 min / 5 min) is recorded as a follow-up task, not built here.

Non-goals: suspend or CPU idle states; a user-visible timeout setting; muting
audio or pausing the Home wallpaper video while dark; screen lock; changing how
the shell's brightness slider writes the backlight.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/power`: idle dim and display-off, idle inhibitors, and the
  consumed touch wake.

## Impact

New `nix/idle-dimmer/` (Python helper, host-tested), a `shell-idle` systemd
service running `swayidle`, two `inhibit_idle` rules in the Sway config, a
small power_keyd hook, and a touch gate in the card-shell compositor adapter
(`nix/card-shell/adapter.c`, `wake-gate.h`). It needs the physical board for the
timing, inhibitor, and touch-consumption proofs; the state logic and the gate
rules are host tests. The compositor change also needs a card-shell build, which
this change has not run. Host tests do not show that a dark panel still delivers
touch events to Sway: that is UNVERIFIED until the board shows it.
