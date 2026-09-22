## Purpose

Defines what the panel shows from the moment the board is powered until the
system draws its first frame, which stage of the boot owns each part of that,
and how a lit panel is handed from one stage to the next without going dark.

## ADDED Requirements

### Requirement: The panel lights during stage 1 and shows a known image

Stage 1 SHALL initialise the panel and scan out an image from the boot
partition before it loads the kernel, so that a person who powers the board
sees the screen respond before any of the system has run. Stage 1 owns this
requirement; nothing in the system contributes to it.

The image SHALL be loaded by exact filename from the root of the boot
partition, the same way stage 1 finds `Image`. When the file is absent stage
1 SHALL leave the panel untouched and continue booting, so that removing one
file restores the behaviour of a board without a splash.

*Grounding, vendor source read on 2026-09-22. Canaan's U-Boot overlay carries
a bare-metal display path for the CanMV's ST7701 —
`.build/k230_linux_sdk/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/board/canaan/common/logo/`,
enabled by `CONFIG_K230_BARE_DISP_LOGO` (`arch/riscv/cpu/k230/Kconfig:35`,
which `select`s `LAST_STAGE_INIT` so `k230_display_logo()` runs from
`last_stage_init()` before the autoboot countdown). `k230_logo.c:200` loads
`/logo.yuv` with `ext4load`, `st7701.c:807` resets the panel, sets the PHY,
programs DSI and VO timing and points a layer at the picture. LILYGO's
official BSP extends that path to this panel: its overlay's `k230_logo.c`
adds a `CONFIG_K230_BARE_DISP_LOGO_RM69A10` case with a 568x1232 XRGB8888
`/logo.xrgb` at `0x1f000000`, `st7701.c` gains `rm69a10_568x1232_init()`
and `GPIO_RST_PIN 22`, and `display_logo.c` gains a 2-lane PHY routine and
an OSD4 scanout. Their init sequence is not the one this project sends:
its rows 6-8 are the partial-area block `31/30/12`, which lit this panel
under Linux but glitched (`docs/evidence/panel-lit.md`), and which
`nix/dts/display-rm69a10-568x1232.dtsi` replaced with `13`
(ENTER_NORMAL_MODE). Stage 1 sends the DTSI's sequence. Recorded, with the
commit hash and the full diff, in `docs/evidence/lilygo-uboot-logo.md`.
Their U-Boot returns `-1` and skips the logo when the load fails
(`k230_logo.c`, `_k230_display_logo_load_pic`). The vendored `k230_canmv_v3`
configuration this project builds does not enable any of it.*

<!-- UNVERIFIED in full: docs/evidence/boot-splash.md and
 docs/evidence/splash-uboot-motion/README.md record this project's source-built
 U-Boot displaying the asset on glass while stopped at K230#, before Starting
 kernel. The required second-card power-on procedure remains open; these
 recordings are USB-attached, serial-initiated warm resets. -->

#### Scenario: The board is powered on

- **WHEN** power is applied with a splash file on the boot partition
- **THEN** the panel shows the splash image before the serial console prints `Starting kernel`, and a timestamped capture together with a photograph records it

#### Scenario: The splash file is not on the card

- **WHEN** the boot partition has no splash file
- **THEN** stage 1 boots the kernel as it does today, the panel stays dark until the system lights it, and the serial console records that the logo was skipped rather than an error that stopped the boot

### Requirement: The panel is driven at the same mode by stage 1 and by the system

Stage 1 SHALL drive the panel at the pixel clock, lane rate and DSI PHY
calibration band the system's device tree declares, so that the handoff is
not also a mode change. In particular the PHY calibration band at this
board's lane rate is `0x87`, and stage 1 SHALL use it rather than the value
either vendor hardcodes.

*Grounding: measured on this board under Linux, like for like, changing only
the device tree value —* `0x96` *(the value in* `canaan_dsi.c:383` *(pristine; 428 as patched) and in
LILYGO's U-Boot* `k230_logo.c` *connector table) works and rolls, `0x97` blanks
the panel, `0x87` is stable to 0.02 px over 30 s;*
`docs/evidence/dsi-hsfreqrange-hardcoded.md`. *The system's mode is 49.5 MHz,
568x1232, htotal 748, vtotal 1268, 2 lanes, 594 Mbps —*
`nix/dts/display-rm69a10-568x1232.dtsi`. *LILYGO's U-Boot runs 39.6 MHz and
475 Mbps with* `0x96`*, which sits inside the band that value calibrates for
and is why it works for them.*

<!-- UNVERIFIED: docs/evidence/dsi-hsfreqrange-hardcoded.md now derives the
 594 Mbps PLL encodings from the Linux clock routine, and the U-Boot table
 carries those values. Source agreement does not prove physical stability.
 The target registration attempt in docs/evidence/splash-uboot-motion/README.md
 failed, so a calibrated U-Boot motion result remains open. A comparison must
 use matching measurement units and rig geometry, not equate panel rows with
 the historical raw-camera-pixel table. -->

#### Scenario: The splash is measured

- **WHEN** the splash is on screen under stage 1 and the panel is filmed with the rig used for `docs/evidence/dsi-hsfreqrange-hardcoded.md`
- **THEN** the frame-to-frame motion is within the figures that document records for `0x87` under Linux, not the rolling figures for `0x96`

#### Scenario: The system takes over

- **WHEN** the kernel's display driver first enables the pipeline after a stage 1 splash
- **THEN** the boot log's `DSI PHY:` line reports the same lane rate and `hsfreqrange` stage 1 used

### Requirement: The system does not extinguish a panel stage 1 lit

When stage 1 reports that it lit the panel, the system SHALL NOT pulse the
panel's reset line, SHALL NOT replay the panel's initialisation sequence on
its first enable, and SHALL NOT scan out a cleared buffer during boot. The
first thing the system draws on the panel SHALL be a deliberate frame from
whatever owns the screen, not a side effect of a driver probing. When stage 1
did not light the panel, the system SHALL initialise it in full as it does
today.

The kernel owns this requirement, and it SHALL take the fact "the panel is
lit" from stage 1 at boot time rather than from a static property of the
device tree, so that a boot on which stage 1 failed to light the panel is a
boot on which the kernel lights it.

*Grounding, vendor kernel source read.* `panel-canaan-universal.c:318-329`
*pulses reset at probe;* `canaan_panel_prepare()` *(lines 124-150) replays*
`init_seq_v1`*, and* `nix/kernel.nix` *adds three reset pulses in front of it
because the panel would not answer otherwise. The modeset that puts a cleared
buffer on the screen during boot comes from the fbdev emulation:*
`canaan_drv.c` *calls* `drm_fbdev_generic_setup()` *at bind, the helper
allocates a zeroed dumb buffer* (`drm_fbdev_generic.c:89-98`)*, and the first
commit is driven from the output poll worker — the soft-lockup trace in*
`docs/evidence/dsi-phy-hang.md` *is exactly that path,*
`output_poll_execute → canaan_dsi_encoder_enable`*. LILYGO's kernel patch
0051 takes the same two steps (reset GPIO requested* `GPIOD_ASIS`*, fbdev
setup skipped) but keys them on a static device tree property; a board whose
logo failed to load would then never be lit at all.* `ft_board_setup()` *in*
`board/canaan/common/k230_board_common.c:574` *is where the vendor U-Boot
already edits the device tree before boot, and is where a runtime flag can be
written.*

<!-- UNVERIFIED in full: the historical unpreserved first-mode trials in
 docs/evidence/boot-splash-handoff.md showed intermittent geometry/color
 failures. The carried exact-mode first-enable VO/DSI preservation and Sway
 initial scene have newer physical warm-boot evidence in
 docs/evidence/splash-preserve-trial/README.md and
 docs/evidence/splash-initial-scene-ready/README.md. The controlled first-mode
 audit in docs/evidence/splash-first-modeset-preserve/README.md observes no
 captured dark frame around first-owner startup or shell takeover. The matching
 kernel journal records the prepare skip. Those trials also exercise
 missing-logo initialization and later display off/on. They do not complete
 the separate second-card and power-on acceptance procedure. Keep the
 first-modeset fallback decision tied to the physical recording. -->

#### Scenario: The kernel boots behind a splash

- **WHEN** stage 1 lit the panel and the kernel boots to a serial prompt with nothing yet opening the display device
- **THEN** the splash is still on the panel at the prompt, the kernel log records `stage 1 splash: leaving fbdev unset`, no panel prepare/init occurs before a DRM client starts, and the first later DRM prepare logs that it left the panel as stage 1 set it

#### Scenario: Stage 1 did not light the panel

- **WHEN** the splash file is absent, or stage 1 reports it could not light the panel
- **THEN** the kernel resets and initialises the panel exactly as recorded in `docs/evidence/panel-lit.md`, and the framebuffer console is available on it when configured

#### Scenario: The panel is later turned off and on

- **WHEN** the display is disabled and re-enabled after the system has taken the screen over
- **THEN** the panel is reset and initialised in full on the re-enable, because the stage 1 handoff applies to the first enable only

### Requirement: The handoff from the splash to the system's first frame is continuous

From the moment stage 1 lights the panel until the shell draws its first
frame, the panel SHALL NOT show a dark frame, and the first frame the system
draws SHALL be the same image stage 1 was showing. An animation MAY run from
that frame onward. Whatever owns the screen during that interval SHALL
retain its last frame until the shell's first frame replaces it, rather than
clearing the screen and exiting.

Userspace owns this requirement. It is met by the thing that opens the
display device first, and that thing is chosen in design.md against a
measured build cost rather than assumed.

*Grounding for the shape of the problem: userspace starts about 22 s into
the kernel boot on this board (*`docs/evidence/panel-probe.txt`*,
`[   22.947804] systemd[1]`), so an owner that starts in the main system first carries forward a static
stage-1 frame. The measured build-cost decision in
`docs/evidence/boot-splash-owner.md` selects the minimal main-system DRM owner;
this change does not implement animation during that initial interval.*

<!-- UNVERIFIED in full: docs/evidence/splash-initial-scene-ready/README.md
 and its camera audit record warm-boot samples without an observed dark frame
 around the corrected handoff, plus physical keyboard show/hide and display
 off/on. Task 5.4 still requires the complete power-on recording and frame
 timings. Camera samples do not prove uninterrupted electrical scanout. -->

#### Scenario: A complete boot is filmed

- **WHEN** the board is filmed from power-on until the shell's first frame
- **THEN** no captured frame between the splash appearing and the shell's first frame is dark, and the first frame the system draws is indistinguishable from the last frame stage 1 showed

#### Scenario: The shell starts

- **WHEN** the shell opens the display device
- **THEN** the image on the panel is the splash's last frame until the shell's first frame replaces it, and the serial log shows the splash owner releasing the device rather than clearing it

### Requirement: The splash and the panel console are a build-time choice

The system SHALL offer two configurations and default to the first: a boot
that shows the splash and puts no console on the panel, and a boot that
lights the panel from the kernel and shows the framebuffer console on it as
`the-screen-comes-up-under-linux` left it. Selecting the second SHALL be one
option in the NixOS configuration, and SHALL be what a person reaches for
when the panel path itself is being debugged.

*Grounding: the console configuration is what runs today —* `console=tty0`
*via* `lib.mkBefore` *in* `nix/hardware.nix` *and* `FRAMEBUFFER_CONSOLE=y` *in*
`nix/kernel.nix`*, photographed in*
`docs/evidence/panel-photos/05-console-on-panel.jpg`*. It is kept because
every diagnosis in* `docs/evidence/` *since the panel lit has depended on
seeing the kernel's messages, and a splash that hides them would make the
next panel regression harder to see, not easier.*

<!-- UNVERIFIED in full: nix/panel-console.nix defines k230.panelConsole
 with a module default of false, but flake.nix explicitly selects true for the
 daily configuration. docs/evidence/splash-initial-scene-ready/default-config.json
 confirms that effective choice. Splash-enabled image builds and missing-logo
 console evidence exist. docs/evidence/splash-option-acceptance/README.md
 now records paired toplevel evaluations and current console-image inspection.
 The final effective default promotion in task 6.1 remains open. -->

#### Scenario: The default configuration boots

- **WHEN** the system is built with no option set
- **THEN** the boot shows the splash and no kernel text appears on the panel

#### Scenario: The panel console is selected

- **WHEN** the system is built with the panel console option
- **THEN** the boot partition carries no splash file, stage 1 leaves the panel dark, the kernel lights it and the console appears on it as before
