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

*A separate real-finger report -- a flickering band across the bottom
~50-100 px of the panel, only during bottom-edge app-switch gestures and
the app switcher, never in a static IPC-driven capture -- was traced with
a board scene/render/present diagnostic
(`docs/evidence/card-shell/bottom-band-flicker/board-diagnostic.md`) to
frames whose render ran long (15% of 7,598 sampled frames exceeded one
52.19Hz refresh period, concentrated during the same gestures) while the
compositor's own scene and DRM presentation-timestamp feedback both
stayed clean. Reading the vendor kernel's DRM driver
(`docs/evidence/card-shell/bottom-band-flicker/kernel-vblank-latch.md`)
found `canaan_crtc_atomic_flush()` committing the VO's shadow-register
"load" bit synchronously, at arbitrary atomic-commit time, never
synchronized to the panel's actual scan position or to the driver's own
vblank interrupt -- unlike the DRM completion event, which already is.
Deferring that one register write into the vblank interrupt handler
(`nix/patches/canaan-drm-defer-reg-load-to-vblank.patch`) is implemented
and builds (`nix build .#kernel`); it has not yet been run on the board.
This is a driver-side timing gap independent of the TE/free-running-scan
gap above -- fixing it does not by itself establish whether that
remaining gap is also a live contributor.*

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

#### Scenario: A real-finger gesture animates the panel continuously

- **WHEN** a person performs a real bottom-edge app-switch or app-switcher
  gesture with continuous finger motion, as opposed to a single static
  IPC-driven state change
- **THEN** the bottom ~100 px of the panel does not flicker or tear, even
  on frames whose software render ran close to or over one refresh period
