## Why

The panel lights at one fixed brightness baked into `panel-init-sequence`
(`15 05 02 51 fe` — `SET_DISPLAY_BRIGHTNESS 0xFE`, in
`nix/dts/k230-tdisplay.dts`). There is no `/sys/class/backlight` device, so
nothing on the system — not `tools/device_settings.py`, not the Settings
brightness stepper already built into the Rust shell — can change it. A
person holding the handheld in a dark room or full sun has exactly one
brightness, forever.

`docs/research/board-capability-inventory.md` names this the single
cheapest, lowest-risk gap on the board (rank 2: "Adjustable screen
brightness ... Low — DSI command writes only") and cites LILYGO's own fix,
already shipped in their BSP:
`Xinyuan-LilyGO/T-Display-K230:k230_bsp` patch
`0049-drm-panel-canaan-universal-add-rm69a10-dsi-backlight.patch`, which adds
`canaan,dsi-command-backlight`, `default-brightness` and `max-brightness`
device-tree properties plus a Linux `backlight_device` driven by
`MIPI_DCS_SET_DISPLAY_BRIGHTNESS` (0x51). The inventory also flags the
prerequisite this change must close: `canaan_panel_prepare()` in our pinned
`panel-canaan-universal.c` has every reset pulse commented out
(`docs/dts-evidence.md`), so a brightness value applied once would not
survive a later modeset or DPMS cycle without one.

## What Changes

- Port a DSI-command backlight into `panel-canaan-universal.c`: register a
  real `/sys/class/backlight/<dev>` device whose `brightness` attribute
  writes `MIPI_DCS_SET_DISPLAY_BRIGHTNESS` (0x51), gated by
  `MIPI_DCS_WRITE_CONTROL_DISPLAY` (0x53) to enable the brightness control
  block. `max_brightness` reflects the DCS command's 8-bit range; the
  default brightness matches today's fixed value (0xFE) so a fresh boot
  looks identical to today until someone touches the control.
- Reapply the last-set brightness whenever the panel re-runs its init
  sequence (a real modeset) or is re-enabled (DPMS-style on/off), so a
  brightness a person picked does not silently revert to the fixed default.
- Wire this into the device tree via new properties on the existing `lcd`
  panel node (`canaan,dsi-command-backlight`, `default-brightness`,
  `max-brightness`) rather than a new node, so a board without the property
  keeps today's fixed-brightness behavior unchanged.
- Wire the existing shell control to the new device: the Settings
  brightness stepper (`ServiceRequest::Brightness`, a stepper per the
  design review, not a slider — out of scope to redesign here) already
  calls `k230-settings brightness <percent>`, and `tools/device_settings.py`
  already reads/writes `/sys/class/backlight/*/brightness` generically. The
  only missing piece is write permission for the unprivileged `shell` user;
  add a udev rule granting the `shell` group write access to the backlight
  device's `brightness` attribute.
- Add a Rust unit test for the stepper's boundary behavior (0% and 100%),
  which previously had no real backend to be wrong against.

## Capabilities

### New Capabilities

- `display/backlight`: the taxonomy in `.skills/k230-spec-change/SKILL.md`
  already names this capability; no spec file exists for it yet. This
  change adds the first one.

### Modified Capabilities

None. `display/panel`'s existing requirements (panel is device-tree-driven,
panel displays what the system draws) are unchanged; this change only adds
brightness control alongside them and fixes a defect
(`canaan_panel_prepare()`'s missing reset) already flagged against that
capability's evidence, not a requirement rewrite.

## Impact

The kernel (`panel-canaan-universal.c`, via `nix/kernel.nix` postPatch —
kept in its own clearly delimited hunk since `feat/speaker` is concurrently
editing this same file for audio Kconfig), the device tree
(`nix/dts/display-rm69a10-568x1232.dtsi`, not touched by `feat/speaker`),
NixOS (`nix/k230.nix`, a new udev rule), and the Rust shell (already wired;
one boundary test added). No new userspace package. Camera-observable
brightness change at 10/50/100% and persistence across a DPMS/modeset cycle
are hardware-only gates; a cross-build and the panel's existing QEMU-proof
boundary (QEMU's `k230` machine models no display) do not touch the panel
at all, so this whole change's functional proof is hardware-only.
