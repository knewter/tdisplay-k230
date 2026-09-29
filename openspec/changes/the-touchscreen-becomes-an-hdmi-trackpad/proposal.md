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
- `nix/touch-trackpad-service.nix`: a standalone, importable NixOS module
  (`k230.touchTrackpad.enable`) defining the systemd unit — not wired into
  `nix/shell.nix`/`nix/k230.nix` by this change, since both are under
  active edit by the coordinator's HDMI work in a separate worktree; the
  coordinator imports it explicitly once there is a live HDMI session to
  try it against.
- `design.md` records the rejected alternatives (a hand-synthesized
  relative-pointer uinput daemon; the wlroots `zwlr_virtual_pointer_v1`
  Wayland-client route; a compositor-side patch) and why the
  touchpad-re-emission design won on latency, permissions, and getting
  pinch/swipe "for free" from libinput's already-shipped gesture engine.

## Capabilities

### New Capabilities

None — this describes what the existing touch input does in a new
situation (HDMI active), not a new piece of hardware.

### Modified Capabilities

- `display/touch`: records that while an HDMI output is the active one,
  the touchscreen SHALL be re-emitted as a virtual touchpad rather than
  reporting absolute touch coordinates, and what a consumer (libinput,
  Sway) observes as a result.

## Impact

- New Rust crate + Nix derivation (`nix/touch-trackpad/`), cross-built and
  proven with `nix build .#handheld-touch-trackpad`; no kernel or
  device-tree change (`CONFIG_INPUT_UINPUT=y` is already built into this
  kernel per `nix/kernel.nix`'s existing `evemu`/touch-injection rationale,
  and `TOUCHSCREEN_GOODIX_BERLIN_*` is already on).
- A new, currently-unwired NixOS module
  (`nix/touch-trackpad-service.nix`); no change to any file the
  coordinator's `plugging-in-hdmi-moves-the-display` change is actively
  editing.
- Host evidence only in this change: unit tests of the protocol translator
  and mode detector, ioctl-number/struct-size checks against the kernel
  UAPI, and one live host `/dev/uinput` device creation showing udev's own
  `ID_INPUT_TOUCHPAD=1` classification. Whether libinput/Sway actually
  drive pointer motion and gestures correctly from the real GT9895 through
  this relay, on the board, with a real HDMI session up, is **not proven
  by this change** and is left as an explicit open board-verification task
  — this change cannot itself get board time (no `/dev/ttyACM0` access;
  the coordinator owns the board and the HDMI prerequisite this depends
  on is itself still mid-flight).
- Non-goals: replacing or altering the coordinator's direct `map_to_output`
  touch path (this is a parallel mode, not a replacement); implementing
  the no-reboot HDMI hot-plug automation (`plugging-in-hdmi-moves-the-display`
  group 4) — this change's mode detection is written to work under either
  outcome of that still-open question; tuning libinput's acceleration
  curve, tap timeout, or scroll speed beyond its defaults (follow-on once
  someone can feel it on glass); a udev-rule-based non-root permission
  model for the service (documented as follow-on in `design.md`).
