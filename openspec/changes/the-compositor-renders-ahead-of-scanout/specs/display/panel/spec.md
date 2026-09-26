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

*A separate real-finger report -- a band about 50 px tall along the panel's
bottom edge flickering only during bottom-edge app-switch gestures and in
the card overview -- was traced with a board scene/render/present
diagnostic (`docs/evidence/card-shell/bottom-band-flicker/board-diagnostic.md`)
to a defect below composition: scene and DRM present timing stayed clean
while consecutive camera frames showed the band cycling between correct,
stale-dark and black. Deferring the VO's register commit to vblank did not
change it and was withdrawn (`kernel-patch-boot-panic.md`). Setting Sway's
`max_render_time 8` on DSI-1 removed it on real glass
(`max-render-time-fix.md`) and on the patch-free kernel under injected
gestures (`kernel-patch-boot-panic.md`). The mechanism is inferred, not
measured.*

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
- **THEN** the bottom ~100 px of the panel does not flicker or tear
