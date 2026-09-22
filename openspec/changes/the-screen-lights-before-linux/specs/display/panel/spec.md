## MODIFIED Requirements

### Requirement: The panel displays what the system draws

*Grounding: observed on hardware -- photographs in `docs/evidence/panel-photos/`.
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

*The roll was subsequently stopped by the DSI PHY calibration band:
`canaan,hsfreqrange = <0x87>` in the device tree,
`docs/evidence/dsi-hsfreqrange-hardcoded.md`.*

The system SHALL present the panel as a display device at 568x1232 through
DRM, and what the system draws on it SHALL appear on the screen. The
framebuffer console on the panel — `/dev/fb0` and `console=tty0` — SHALL
remain available as a configuration, and SHALL be the configuration used
when the panel path is being debugged; it is no longer what a boot shows by
default, because `display/boot-splash` puts a splash there and the console's
takeover is what would clear it.

*Why this changed: the fbdev emulation is the thing that performs the first
modeset during boot, from the output poll worker onto a zeroed buffer
(`drm_fbdev_generic.c:89-98`, and the trace in
`docs/evidence/dsi-phy-hang.md`). A splash that survives the kernel cannot
coexist with it, so it becomes the debugging configuration rather than the
default. Nothing about the DRM device, the mode, or the plane formats
changes; `modetest -s 48:568x1232@AR24` set a mode on this panel before the
fbdev fix was ever applied (`docs/evidence/kernel-patches.md`).*

**A framebuffer device existing is not evidence.** This SHALL be grounded by a
photograph of the physical screen, because a pipeline that reports success and
shows nothing is a failure mode this hardware has already produced once — the
Wi-Fi driver reported `start ap successs!` while transmitting nothing.

#### Scenario: The system boots with the panel configured

- **WHEN** the board boots
- **THEN** a DRM device with a 568x1232 mode is present, and a photograph shows the panel displaying what the boot's owner drew — the splash by default, the console when that configuration is selected

#### Scenario: The panel console is configured

- **WHEN** the system is built with the panel console selected
- **THEN** a framebuffer at 568x1232 is present, and a photograph shows the console on the screen

#### Scenario: Something is written to the framebuffer

- **WHEN** a pattern is written to the framebuffer
- **THEN** it is visible on the physical panel, photographed, and the photograph is committed
