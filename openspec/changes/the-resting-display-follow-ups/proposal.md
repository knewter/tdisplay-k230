## Why

The display now dims, turns off, and on the charger shows a clock instead
of going dark (`the-display-dims-and-sleeps-when-idle`,
`the-charging-display-shows-an-exhibition-clock`, both board-proved on
2026-10-27/28). Several gaps were deliberately left out of those slices, and
a person still runs into them:

- The 30 s / 60 s idle timeout is fixed. Someone reading a long page, or
  someone who wants the panel to last longer on battery, cannot change it.
- Unplugging HDMI lights the panel without telling the idle timer. The panel
  can stay dim, or turn off sooner than the person expects.
- Nobody has decided whether the charger should hold the display on, or
  whether the Home wallpaper video should keep decoding while the panel is
  dark.
- The clock screen cannot show that notifications are waiting. It uses the
  dimmed brightness, with no control of its own. Its two-hour cap and effect
  interval are fixed. An HDMI mouse alone cannot close it. It cannot be
  started on demand.
- No camera recording of the clock screen exists. The operator reassigned the
  webcam on 2026-10-28.

This change exists so those two changes can archive. It holds every
follow-up they listed, with the wording kept, and nothing else.

## What Changes

- A Settings choice for the idle timeout (Off / 1 min / 5 min), read by
  `shell-idle` at start.
- An HDMI unplug wakes the display through the idle dimmer, so brightness
  and the idle timer are restored together.
- A recorded decision on whether charging defers idle off, and whether the
  wallpaper video pauses while the display is off.
- On the clock screen: a notification-count dot; its own brightness; settings
  for the two-hour cap and the effect interval; closing it on pointer-only
  activity; a shade tile or Home action that starts it.
- A camera record of the clock screen, once a camera is available again.

Non-goals: suspend or CPU idle states; screen lock; new clock-screen effects
or layouts; changing how dim, off and wake already behave; anything on
battery that would keep the panel lit longer by default.

Board: most items need the physical board for proof. The Settings row, the
dimmer's HDMI wake call and the clock-screen settings can be built and
host-tested first. The camera item needs the webcam back and is not a gate
for the rest.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/power`: the HDMI-unplug wake goes through the idle dimmer; pointer
  activity closes the clock screen; the clock screen can be started on demand.
- `runtime/device-settings`: an idle-timeout choice.

## Impact

- `nix/idle-dimmer/idle_dimmer.py` and `nix/shell.nix` (`shell-idle`
  arguments).
- `nix/touch-trackpad/src/shell_ipc.rs` (HDMI-unplug wake).
- `nix/term-apps/k230_exhibition.py` and the Rust settings and shade surfaces
  (`nix/rust-shell-client/src/`).
- Source of the follow-ups: tasks 4.1–4.3 of
  `the-display-dims-and-sleeps-when-idle`, and 5.1–5.5 of
  `the-charging-display-shows-an-exhibition-clock` (5.5 was 4.7).
