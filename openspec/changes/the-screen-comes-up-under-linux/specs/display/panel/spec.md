## Purpose

Defines what appears on this board's AMOLED and how the panel is driven under
Linux.

## ADDED Requirements

### Requirement: The panel is described by device tree, not by a bespoke driver

The RM69A10 SHALL be driven through the kernel's device-tree-configured
generic Canaan panel support. This project SHALL NOT add a panel driver in C
for it.

*Grounding: `drivers/gpu/drm/panel/panel-canaan-universal.c` in the pinned
Xuantie kernel is 395 lines and reads its init command sequence
(`struct panel_cmd_seq *init_seq_v1`), timings (`struct videomode vm`), reset
and power GPIOs, and DSI lane count from the device tree. The reference
`k230-canmv-v3-lcd.dts` uses it via `display-st7701-480x800.dtsi` for a
different panel.*

The init sequence SHALL be transcribed from the vendor's working
implementation rather than derived from the panel datasheet.

*Grounding: LilyGO's `mpp/kernel/connector/src/rm69a10.c` drives this exact
panel on this exact board; `docs/rtsmart-boot-log.txt` records it running —
`rm69a10_init`, `rm69a10_568x1232_init`, `rm69a10_set_phy_freq`. The panel
reset is GPIO22.*

#### Scenario: The panel support is inspected

- **WHEN** someone asks which driver drives this screen
- **THEN** it is the generic Canaan panel support, configured by this board's device tree, with no board-specific C

### Requirement: The panel displays what the system draws

*Grounded on hardware by photographs in `docs/evidence/panel-photos/`.
The panel was driven to three known states from a shell on the board —
`/dev/urandom` (speckled bright field), `/dev/zero` (dark), and `0xFF`
bytes (bright) — and photographed each time. Three states rather than one
deliberately: a single bright frame could be a reflection and a single
dark frame is what a dead panel looks like, so the change is the
evidence. A fourth photograph shows the kernel console rendering on the
panel at 71x77 characters. See `docs/evidence/panel-lit.md`.*

*What is NOT yet grounded: the image flickers. Measured with the panel
showing static stripes and the webcam exposure locked, over 30 seconds:
stripe position jitters -9..+1 px with no monotonic drift, and brightness
shows 19 irregular dips, one to 53% of mean. That is unstable frame
delivery, not a refresh-rate beat. A fix giving the DSI link 25% burst
headroom is built but not yet confirmed on hardware.*

The system SHALL present the panel as a working framebuffer at 568x1232, and
what is written to that framebuffer SHALL appear on the screen.

**A framebuffer device existing is not evidence.** This SHALL be grounded by a
photograph of the physical screen, because a pipeline that reports success and
shows nothing is a failure mode this hardware has already produced once — the
Wi-Fi driver reported `start ap successs!` while transmitting nothing.

#### Scenario: The system boots with the panel configured

- **WHEN** the board boots
- **THEN** a framebuffer at 568x1232 is present, and a photograph shows the console on the screen

#### Scenario: Something is written to the framebuffer

- **WHEN** a pattern is written to the framebuffer
- **THEN** it is visible on the physical panel, photographed, and the photograph is committed
