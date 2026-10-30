## Purpose

Plays a terminal text effect from the Omarchy `ttfx` family as the boot animation:
executed by stage 1 on the stage 1 splash, with the effect and text chosen per boot;
continued live in early Linux; and handed to the shell without a dark frame.

## ADDED Requirements

### Requirement: The no_std engine produces the same frames as ttfx

The engine stage 1 executes SHALL be ttfx's own animation engine built for
`core` + `alloc` from a patch against the pinned ttfx revision, and for the same
effect, text, seed and canvas it SHALL produce the same frames as the std ttfx,
byte for byte, including as the riscv64imac soft-float object code linked for
stage 1. The std ttfx SHALL remain buildable with its own tests passing from the same patched source.

*Grounding (2026-10-30): host and QEMU user-mode measurements in
`docs/evidence/boot-text-effects/nostd-parity-full.txt` (148 of 148 host streams, 37 of 37
firmware streams identical) and `nostd-feasibility.md`. These are host and QEMU claims, not
U-Boot or board claims.*

#### Scenario: Comparing engines

- **WHEN** an effect is run by the no_std engine and by `ttfx --parity-dump` with the same seed, text and canvas
- **THEN** the two frame streams have the same SHA-256

#### Scenario: A ttfx bump changes frames

- **WHEN** the pinned ttfx revision changes its frames or its dump format
- **THEN** the host tests fail on their golden hashes instead of shipping a different animation

### Requirement: Stage 1 executes an effect chosen per boot

Stage 1 SHALL, only when the text-effects source is selected, run the engine for an
effect, text and seed chosen for that boot and draw its frames onto the scanout it
already owns using a freestanding glyph renderer, then publish a record identifying
source 2, the effect, text, seed, canvas, the last frame drawn and a hash of that
frame's cells. The choice SHALL come from, in order, U-Boot environment overrides that
are never saved, a build-time list indexed by a seed, and a default; the seed SHALL
be derived from the timer, any readable clock and the environment value. With the
source not selected, the boot SHALL be identical to the boot without this feature.
Stage 1 remains vendored-derived firmware built from pinned source; this requirement
is on the source-built U-Boot, not on the system.

#### Scenario: Source not selected <!-- UNVERIFIED: stage 1 playback has not been built or run on the board. -->

- **WHEN** the board boots with the text-effects source not selected
- **THEN** the console shows the normal stage 1 sequence and the static logo is unchanged

#### Scenario: Source selected, defaults <!-- UNVERIFIED: requires the installed stage 1 build and a console transcript. -->

- **WHEN** the board boots with the source selected and no overrides
- **THEN** the console reports the effect, text and seed it chose, the frames drawn and the record's frame and hash, and the glass shows that effect

#### Scenario: Overrides <!-- UNVERIFIED: requires the installed stage 1 build. -->

- **WHEN** `tfx_effect`, `tfx_text` and `tfx_seed` are set at the `K230#` prompt before `boot`
- **THEN** stage 1 plays exactly that effect, text and seed, and the record carries them

### Requirement: The picture is oriented by the keyboard base

Stage 1 SHALL, before it draws, probe the keyboard base on its I2C bus without writing any register content
on it, and SHALL draw the animation in portrait if the base does not answer within a bounded time or any
error occurs, and in the shell's landscape orientation if it does. It SHALL record the orientation, and Linux
SHALL continue in the orientation the shell will display, or from frame 0 in that orientation if it differs from
the record's. The stage 1 side is source-built firmware; the Linux side is the system.

*Grounding (2026-10-30): the base's chips and LILYGO's detection are in `docs/evidence/keyboard-base/probe/README.md`;
the landscape mapping is the repo's touch calibration; the renderer is tested on the host. The probe itself has not
run on the board.*

#### Scenario: Base detached <!-- UNVERIFIED: the base-absent boot has never been done. -->

- **WHEN** the board boots without the keyboard base
- **THEN** the animation is drawn in portrait and the record says portrait

#### Scenario: Base attached <!-- UNVERIFIED: requires the installed stage 1 build with the I2C4 probe. -->

- **WHEN** the board boots clipped into the keyboard base
- **THEN** the animation is drawn in landscape, upright for a person at the keyboard, and the record says landscape

#### Scenario: The probe fails

- **WHEN** the bus cannot be brought up or an error occurs during the probe
- **THEN** the animation is drawn in portrait and the boot continues

#### Scenario: Rendering the landscape picture

- **WHEN** a landscape frame is drawn on the host
- **THEN** logical pixel (x, y) of the 1232x568 picture is at native pixel (y, 1231 - x) and the surface hash equals an independent renderer's

### Requirement: A failing engine falls back to a pre-rendered sequence

If the engine cannot start or fails before drawing its first frame (no arena, an
unknown effect, a Rust panic), stage 1 SHALL play a sequence generated on the host
from the same ttfx for a default effect, or leave the static logo, and SHALL record
which it did. The failure SHALL NOT stop the boot.

#### Scenario: Engine forced to fail <!-- UNVERIFIED: requires the installed stage 1 build and the operator's failure trigger. -->

- **WHEN** the engine is made to fail at start
- **THEN** the replay sequence or the logo is shown, the record's flags say so, and Linux still boots

#### Scenario: The sequence is reproducible

- **WHEN** the host generator is run twice with the same ttfx revision, seed and arguments
- **THEN** both sequence files have the same SHA-256

*Grounding (2026-10-30): `tests/test_textfx_frames.py`, output in
`docs/evidence/boot-text-effects/host-textfx-tests.txt`.*

### Requirement: Linux continues the same run live

Early Linux SHALL render a live run of the same effect, text, canvas and seed named
by a valid stage 1 record into the panel through DRM, SHALL skip to the frame the
record names after confirming its own cell-grid hash for that frame equals the
record's, and SHALL otherwise play from the first frame. The player SHALL NOT make
the shell depend on it.

*Grounding (2026-10-30): the continuation is a software property tested on the host
(`tests/test_textfx_player.py`); board behaviour is recorded by the board-process
tasks, not assumed.*

#### Scenario: Valid record

- **WHEN** the record's prefix, checksum and boot instance validate and the cell hash at the named frame equals the live run's
- **THEN** the player draws from that frame onward and logs the frame and hash

#### Scenario: Record missing or wrong

- **WHEN** the record is absent, invalid, or its hash differs from the live run
- **THEN** the player logs the reason and plays from the first frame

#### Scenario: The player fails

- **WHEN** the player cannot open DRM or exits with an error
- **THEN** the shell still starts and the display is taken by the existing owner as today

### Requirement: The animation hands the display to the shell

The player SHALL signal that it holds the scanout, drop DRM master when told
by the shell's existing release signal, retain the last frame in the
framebuffer, and write the same acknowledgement the splash owner writes.

#### Scenario: Shell takes over after the player <!-- UNVERIFIED: requires a boot or board run with the shell started after the player. -->

- **WHEN** the shell is released while the player holds the scanout
- **THEN** the player acknowledges `master-dropped` and the shell opens DRM

### Requirement: The stage 1 engine runs in a proven arena

The stage 1 engine SHALL allocate only from a fixed DRAM range that a host check proves, against the
device tree the board boots and the recorded boot layout, to overlap no kernel image, initrd, device tree,
firmware, U-Boot relocation, splash reservation or other reserved node, and that is large enough for
every effect in the default per-boot list with a stated margin. The range SHALL be abandoned before
`bootm`.

*Grounding (2026-10-30): `tools/check-boot-textfx-memory.py` against the DTB read from the board
(`docs/evidence/boot-text-effects/arena-memory-map.txt`). A host check, not a U-Boot run.*

#### Scenario: The shipped arena

- **WHEN** the checker is run on the shipped arena, the board's device tree and the boot file sizes
- **THEN** it reports OK and states the largest effect's peak against the margin limit

#### Scenario: An arena that overlaps a load <!-- UNVERIFIED: the rejection is a host test; U-Boot behaviour on overlap is not exercised. -->

- **WHEN** the arena is moved onto the initrd's load range, the splash reservation or the CMA pool
- **THEN** the checker rejects it and names the overlapping interval

### Requirement: The animation is bounded in cost, memory and time

The Linux player SHALL run at the lowest practical CPU priority, drop frames rather
than run late, and stop on its own after the effect completes, leaving the final
frame on screen. The stage 1 engine SHALL allocate only from an arena it is given,
bounded at build time, and SHALL not use U-Boot's heap. A measured CPU cost per
frame SHALL be recorded for both before they are enabled at boot. U-Boot-to-Linux
ownership MAY leave a visible pause while the kernel starts; no uninterrupted-motion
claim is made.

#### Scenario: Measured cost

- **WHEN** the player and the engine bench are started by hand on the running board
- **THEN** the committed records state CPU time per frame and frames dropped

#### Scenario: Physical continuity <!-- UNVERIFIED: no film has been taken; the webcam must not be used without the operator. -->

- **WHEN** a boot is filmed from power-on to the shell
- **THEN** the film shows the stage 1 effect, the documented pause, the live continuation and the shell's first frame
