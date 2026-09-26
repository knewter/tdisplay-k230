## ADDED Requirements

### Requirement: The panel exposes a real backlight device

<!-- UNVERIFIED: registered against the pinned kernel source and this
board's DT properties; no boot log or photograph yet confirms the device
node appears or that writes change the panel. -->

The system SHALL register exactly one `/sys/class/backlight/<dev>` device
for the RM69A10 panel, with `max_brightness` reflecting the
`MIPI_DCS_SET_DISPLAY_BRIGHTNESS` command's 8-bit range and
`brightness` writable by a process with permission on the device node.
Writing `brightness` SHALL send `MIPI_DCS_SET_DISPLAY_BRIGHTNESS` (0x51) to
the panel controller, gated by `MIPI_DCS_WRITE_CONTROL_DISPLAY` (0x53) to
enable the brightness control block.

*Grounding: `drivers/gpu/drm/panel/panel-canaan-universal.c` in the pinned
Xuantie kernel tree registers no backlight device today — `ctx->power_on`
(DT property `backlight_gpio`, GPIO25) is an on/off enable gate driven once
at probe, not a brightness control; the fixed value `0xFE` in
`panel-init-sequence` (`nix/dts/k230-tdisplay.dts`) is the only brightness
this board has ever shown. `include/video/mipi_display.h` in the same
pinned tree already defines `MIPI_DCS_SET_DISPLAY_BRIGHTNESS = 0x51` and
`MIPI_DCS_WRITE_CONTROL_DISPLAY = 0x53`, and `DRM_PANEL_CANAAN_UNIVERSAL`
already `depends on BACKLIGHT_CLASS_DEVICE`, itself already `=y` in
`arch/riscv/configs/k230_defconfig` — see design.md's Context.*

#### Scenario: A person lists the backlight class

- **WHEN** a person runs `ls /sys/class/backlight` on the board
- **THEN** exactly one device appears, with `max_brightness` and
  `brightness` files

#### Scenario: A person writes a new brightness

- **WHEN** a person writes 10%, 50%, then 100% of `max_brightness` to that
  device's `brightness` file
- **THEN** the panel's visible brightness changes at each write, observable
  by camera

### Requirement: Brightness survives a modeset or DPMS cycle

<!-- UNVERIFIED: requires a physical modeset/DPMS cycle on the board with
brightness observed before and after. -->

A brightness value a person has set SHALL still apply after the panel is
re-enabled by a later modeset or a DPMS-style off/on cycle. The system
SHALL NOT silently revert to the fixed default brightness baked into the
panel's init sequence.

*Grounding: the inventory's flagged prerequisite —
`canaan_panel_prepare()`'s reset pulses were commented out by the vendor
(now fixed in `nix/kernel.nix`'s postPatch history), so `prepare()` fully
re-runs `panel-init-sequence`, including its fixed brightness DCS write, on
every real modeset. `drivers/gpu/drm/drm_panel.c`'s `drm_panel_enable()`/
`drm_panel_disable()` already call `backlight_enable()`/
`backlight_disable()` whenever `struct drm_panel.backlight` is set, and
`canaan_dsi.c`'s encoder enable/disable path already calls
`drm_panel_enable()`/`drm_panel_disable()` on every modeset — see design.md
decision 4.*

#### Scenario: A modeset happens after brightness was changed

- **WHEN** a person has set brightness away from the default and a modeset
  or DPMS cycle then occurs
- **THEN** the panel's brightness after the cycle matches what the person
  set, not the fixed default

### Requirement: A fresh image looks unchanged until brightness is touched

The default brightness SHALL match the value already baked into
`panel-init-sequence` today, so a system with this change but with nobody
having used the Settings brightness control looks identical to a system
without it.

*Grounding: `panel-init-sequence`'s existing fixed DCS write is
`15 05 02 51 fe` — `0xFE` — in `nix/dts/k230-tdisplay.dts`.*

#### Scenario: A fresh boot with no brightness interaction

- **WHEN** the system boots and nobody has opened Settings' brightness
  control
- **THEN** the panel's brightness matches what a system without this
  change would show

### Requirement: The Settings brightness stepper drives the real device

The existing Settings brightness stepper (`ServiceRequest::Brightness`,
already implemented in the Rust shell as a stepper rather than a slider,
per the design review) SHALL change the panel's actual brightness through
`/sys/class/backlight/*/brightness`, through the existing
`tools/device_settings.py` sysfs path, once the unprivileged `shell` user
holds write permission on that device.

*Grounding: `tools/device_settings.py`'s `Settings.backlight()` and
`Settings.change_brightness()` already read/write
`/sys/class/backlight/*/brightness` generically and already report
`writable`/`read-only`/`unavailable` based on `os.access()` — this was
previously always `unavailable` because no backlight device existed at
all. `nix/rust-shell-client/src/service_ui.rs`'s stepper logic
(`value.saturating_sub(10)` / `.saturating_add(10).min(100)`) is already
implemented and tested.*

#### Scenario: A person steps brightness up or down in Settings

- **WHEN** a person taps the Settings brightness stepper's + or − control
- **THEN** the request reaches `/sys/class/backlight/*/brightness` and the
  panel's brightness changes accordingly
