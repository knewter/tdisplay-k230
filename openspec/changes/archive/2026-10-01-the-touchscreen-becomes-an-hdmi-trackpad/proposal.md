## Why

`plugging-in-hdmi-moves-the-display` gives the board a mode where an
external monitor is the active output (1080p, rotated portrait) and the
built-in AMOLED panel goes dark. In that mode the GT9895 touchscreen is
still live silicon with nothing to point at directly: a person's finger no
longer lands on anything it's touching, since the picture is on a monitor
across the desk, not under the glass. Direct absolute touch-to-output
mapping (`map_to_output`, the coordinator's parallel work) is one answer
for someone standing at the panel; it is not useful for someone sitting at
the monitor with the board flat on a desk, which is the actual physical
arrangement HDMI mode is for. The operator wants that same glass usable
the way a laptop trackpad is: relative pointer motion, tap-to-click, and
multi-finger gestures (two-finger scroll, pinch-zoom, swipes) for the
monitor session — and wants it to happen automatically, with no manual
mode switch, whenever HDMI is actually the active output.

## What Changes

- A new host-side prototype, `nix/touch-trackpad/` (Rust, cross-built for
  riscv64-linux exactly as `nix/rust-shell-client/` is): grabs the
  touchscreen (`EVIOCGRAB`) and re-emits its multitouch protocol-B contacts
  through a virtual `uinput` device declared with touchpad properties
  (`INPUT_PROP_POINTER` + `INPUT_PROP_BUTTONPAD`, `BTN_TOOL_FINGER`/
  `_DOUBLETAP`/`_TRIPLETAP`, no `INPUT_PROP_DIRECT`) instead of one that
  itself computes relative motion or gestures. libinput classifies the
  result as a touchpad on its own (host-verified: `ID_INPUT_TOUCHPAD=1`,
  `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/host-uinput-classification.md`)
  and does its own pointer acceleration, tap-to-click, and every
  multi-finger gesture (two-finger scroll, pinch, swipe) itself — this
  program's only job is protocol translation, not gesture recognition.
- Automatic mode switching: the daemon polls `/sys/class/drm/*/status`
  (no dependency on Sway's IPC socket or on Sway having started) and grabs
  the touchscreen only while an `HDMI*` connector reads `connected`;
  otherwise the touchscreen is left ungrabbed for the coordinator's direct
  touch mapping. A `--force-mode=trackpad|direct` flag is kept as a manual
  override for bring-up, but is not the normal path.
- `nix/touch-trackpad-service.nix`: an importable NixOS module
  (`k230.touchTrackpad.enable`) defining the systemd unit. The explicit
  `k230-coherent-shell-hdmi-trial` profile imports and enables it after
  the bounded standalone board safety trial. Other profiles retain their
  existing direct-touch configuration.
- `design.md` records the rejected alternatives (a hand-synthesized
  relative-pointer uinput daemon; the wlroots `zwlr_virtual_pointer_v1`
  Wayland-client route; a compositor-side patch) and why the
  touchpad-re-emission design won on latency, permissions, and getting
  pinch/swipe "for free" from libinput's already-shipped gesture engine.

- The Rust shell subscribes to `wl_pointer` and shares its existing
  touch actions with primary mouse clicks/drags, so the virtual trackpad can
  activate Home/launcher icons and settings controls. Pointer hover and
  secondary buttons do not accidentally activate apps.

- A four-finger inward pinch on the touchscreen-derived virtual touchpad
  opens app overview via Sway's normal device-scoped gesture binding.

## Capabilities

### New Capabilities

None — this describes what the existing touch input does in a new
situation (HDMI active), not a new piece of hardware.

### Modified Capabilities

- `display/touch`: records that while an HDMI output is the active one,
  the touchscreen SHALL be re-emitted as a virtual touchpad rather than
  reporting absolute touch coordinates, and what a consumer (libinput,
  Sway) observes as a result.

- `runtime/shell`: overview entry through four-finger trackpad pinch.

## Impact

- New Rust crate + Nix derivation (`nix/touch-trackpad/`), cross-built and
  proven with `nix build .#handheld-touch-trackpad`; no kernel or
  device-tree change (`CONFIG_INPUT_UINPUT=y` is already built into this
  kernel per `nix/kernel.nix`'s existing `evemu`/touch-injection rationale,
  and `TOUCHSCREEN_GOODIX_BERLIN_*` is already on).
- A new NixOS module
  (`nix/touch-trackpad-service.nix`), plus a named virtual-touchpad input
  stanza in `nix/shell.nix` enabling normal libinput tap and scroll behavior.
  The coordinator owns that configuration change after the HDMI checkpoint landed.
- Evidence now includes the host tests/classification plus a bounded real
  board contact capture and the operator's confirmation of cursor movement.
  The capture exposed incorrect multi-finger UAPI bindings; these are fixed
  and independently checked against Linux headers. Tap-to-click is explicitly
  enabled for the named virtual device in the image's Sway configuration.
  Physical click/scroll/pinch and panel restoration remain
  open board-verification gates; see `board/contact-checkpoint.json` under
  this change's evidence directory. The coordinator reserves the board and
  serial port for those trials.
- Non-goals: replacing or altering the coordinator's direct `map_to_output`
  touch path (this is a parallel mode, not a replacement); implementing
  the no-reboot HDMI hot-plug automation (`plugging-in-hdmi-moves-the-display`
  group 4) — this change's mode detection is written to work under either
  outcome of that still-open question; retuning pointer acceleration or tap timing; a udev-rule-based non-root permission
  model for the service (documented as follow-on in `design.md`).

## HDMI gesture refinement (2026-09-30)

The operator reports awkward shell gestures and requests an actual HDMI UX
pass, especially easy two-finger drawer/card navigation. Extend this existing
change rather than create another unrelated in-flight proposal. Two-finger
vertical swipes starting near the built-in glass's top/bottom edges navigate
the shell independently of cursor location; center scrolling/pinch and
one-finger pointer/taps remain libinput-owned. Two-finger horizontal overview
scroll follows movement continuously and preserves release momentum. Drawer/
shade dismissal must be reversible and must not strand a half-visible sheet.
The coordinator owns relay gesture arbitration, bounded local IPC, compositor
policy, shared Rust reveal/dismiss and named-device natural scroll defaults.
No HDMI kernel/DT change, new graphics engine or whole-device flash is needed.

## Uniform gesture correction (2026-09-30)

The operator confirmed upward two-finger navigation but reported that downward
drawer dismissal failed. They clarified the interaction model: two fingers in
HDMI trackpad mode must perform the shell gestures already available to one
finger in direct touch mode, rather than accumulating independent shortcuts.
Three fingers from the bottom replace the touch mode's two-contact keyboard
chord. Both modes share tracking, reversal, scrolling boundaries and release
physics. Preserve ordinary one-finger pointer input and application scroll/zoom.

## Accepted closeout, 2026-10-01

The operator accepts this delivered functional scope and waives additional
capture-only acceptance gates. `docs/evidence/proposal-closeout/2026-10-01/trackpad.md` records the exact report,
prior evidence and limits. Its task dispositions supersede older statements
that these acceptance gates remain open; they do not claim new test runs.
