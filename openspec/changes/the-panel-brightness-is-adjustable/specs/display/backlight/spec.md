## ADDED Requirements

### Requirement: The panel exposes a real backlight device

The system SHALL register exactly one `/sys/class/backlight/<dev>` device
for the RM69A10 panel, with `max_brightness` reflecting the
`MIPI_DCS_SET_DISPLAY_BRIGHTNESS` command's 8-bit range and
`brightness` writable by a process with permission on the device node.
Writing `brightness` SHALL send a single-byte `MIPI_DCS_SET_DISPLAY_BRIGHTNESS`
(0x51) command to the panel controller, matching the exact command shape
(`MIPI_DSI_DCS_SHORT_WRITE_PARAM`, cmd + one data byte) already proven
working in `panel-init-sequence`.

*Grounding: `drivers/gpu/drm/panel/panel-canaan-universal.c` in the pinned
Xuantie kernel tree registers no backlight device by default —
`ctx->power_on` (DT property `backlight_gpio`, GPIO25) is an on/off enable
gate driven once at probe, not a brightness control. Confirmed on the
board: `ls /sys/class/backlight` shows exactly one device
(`canaan-dsi-backlight`, `max_brightness=255`), and writes at 10/50/100%
read back as set with no dmesg errors — see
`docs/evidence/backlight/board-findings.md`.*

<!-- UNVERIFIED / NEGATIVE RESULT, board-confirmed: writing brightness does
NOT visibly or measurably change the panel. A clean board test (fresh
boot, no DPMS interference) of 0/128/255 shows near-identical mean
luminance (200.99/201.14/201.33) with the locked-exposure camera. A real
transport bug (a malformed 2-byte DCS write) was found and fixed, but the
fix alone did not close this gap; see board-findings.md for the current
best hypothesis (this DSI host's command path may not deliver generic
commands while continuous video streaming is active) and the two
"Scenario"s below, which restate what the fixed command achieves and does
not achieve rather than asserting success. -->

#### Scenario: A person lists the backlight class

- **WHEN** a person runs `ls /sys/class/backlight` on the board
- **THEN** exactly one device appears, with `max_brightness` and
  `brightness` files

#### Scenario: A person writes a new brightness (not yet met)

- **WHEN** a person writes 10%, 50%, then 100% of `max_brightness` to that
  device's `brightness` file
- **THEN** the write is accepted with no error and reads back as set, but
  **the panel's visible brightness does not yet change** — this scenario
  is board-confirmed to fail today; see board-findings.md

### Requirement: Brightness survives a modeset or DPMS cycle

<!-- UNVERIFIED, and now confounded by a separate board finding: a DPMS
off/on cycle was tried and produced a large luminance change, but
canaan_panel_unprepare() drives backlight_gpio (GPIO25) low while
canaan_panel_dsi_probe() only ever drives it high once, at probe() -- so
that change may be the enable gate getting stuck low, not brightness
being reapplied. This requirement cannot be considered met until the
underlying "a person can see the panel change brightness" requirement
above is met at all; see board-findings.md. -->

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

<!-- UNVERIFIED: the stepper does reach /sys/class/backlight's brightness
attribute (confirmed: the udev rule grants write access, and
tools/device_settings.py's sysfs path is exercised), but per the
requirement above, the write reaching the attribute does not yet mean the
panel visibly changes. -->

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
