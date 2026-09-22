# display/panel Specification

## Purpose
Defines what appears on this board's AMOLED and how the panel is driven under
Linux.

## Requirements

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

*What is NOT yet grounded: the image still moves slightly. The 25% DSI
burst headroom fix referred to here was confirmed on hardware and it
**blanks the panel outright**; it was reverted in `a96ca99`. See
`docs/evidence/dsi-burst-headroom.md`.*

*On the corrected image, measured over 30 s with the webcam exposure
locked and the oblique view rectified by a four-fiducial homography, so
the numbers are in real panel rows: brightness is now flat (95%..101% of
mean, against 19 dips with the worst at 53% before), and the residual is
a **uniform whole-frame vertical shift** of about 2.8 rows RMS out of
1232. Near and far halves of the panel move identically -- std 2.76
against 2.76, correlation 0.959 -- so there is no accumulation down the
frame and no tearing. Mechanism is not established; the untested
hypothesis is that `35 00` SET_TEAR_ON is issued but nothing consumes
TE. See `docs/evidence/flicker-after-headroom-revert.md`.*

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
