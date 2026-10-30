## Purpose

Plays a terminal text effect from the Omarchy `ttfx` family as the boot
animation: pre-rendered at the stage 1 splash, continued live in early Linux,
and handed to the shell without a dark frame.

## ADDED Requirements

### Requirement: Text-effect frames are generated deterministically on the host

The build SHALL produce the stage 1 animation by running the pinned `ttfx`
with a fixed seed, effect and arguments over a committed text, and SHALL store
the result as a versioned cell sequence. Running the generator twice with the
same inputs SHALL produce identical per-frame and whole-sequence hashes, and a
different seed SHALL not.

*Grounding (2026-10-30): host measurement of `ttfx` 0.5.1 `--seed N --parity-dump`
over `nix/exhibition/K230.txt` repeated with identical SHA-256; see
`docs/evidence/boot-text-effects/ttfx-research.md`.*

#### Scenario: Rebuilding the sequence

- **WHEN** the generator is run twice with the same ttfx revision, seed and arguments
- **THEN** both sequence files have the same SHA-256

#### Scenario: A changed ttfx output format

- **WHEN** a ttfx revision changes its dump format or frames
- **THEN** the host test fails on its golden hashes instead of shipping a different animation

### Requirement: Stage 1 plays the pre-rendered sequence

Stage 1 SHALL, only when the text-effects source is selected, draw the
sequence's frames onto the scanout it already owns using a freestanding glyph
renderer, then publish a record identifying source 2, the last frame drawn and
a hash of that frame's cells. With the source not selected, the boot SHALL be
identical to the boot without this feature. Stage 1 remains vendored-derived
firmware built from pinned source; this requirement is on the source-built
U-Boot, not on the system.

#### Scenario: Source not selected <!-- UNVERIFIED: stage 1 playback has not been built or run on the board. -->

- **WHEN** the board boots with the text-effects source not selected
- **THEN** the console shows the normal stage 1 sequence and the static logo is unchanged

#### Scenario: Source selected <!-- UNVERIFIED: requires the installed stage 1 build and a console transcript. -->

- **WHEN** the board boots with the text-effects source selected
- **THEN** the console reports the frames drawn and the record's frame and hash, and the glass shows the effect

### Requirement: Linux continues the same run live

Early Linux SHALL render a live `ttfx` run of the same effect, text, canvas and
seed into the panel through DRM, SHALL skip to the frame named by a valid stage
1 record after confirming its own cell-grid hash for that frame, and SHALL
otherwise play from the first frame. The player SHALL NOT make the shell
depend on it.

*Grounding (2026-10-30): the live ttfx dump on the host is identical across
runs; the continuation is a software property. Board behaviour is recorded by
the board-process tasks, not assumed.*

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

### Requirement: The animation is bounded in cost and time

The player SHALL run at the lowest practical CPU priority, drop frames rather
than run late, and stop on its own after the effect completes, leaving the
final frame on screen. A measured CPU cost per frame SHALL be recorded before
the player is enabled at boot. U-Boot-to-Linux ownership MAY leave a visible
pause while the kernel starts; no uninterrupted-motion claim is made.

#### Scenario: Measured cost

- **WHEN** the player is started by hand on the running board
- **THEN** the committed record states CPU time per frame and frames dropped

#### Scenario: Physical continuity <!-- UNVERIFIED: no film has been taken; the webcam must not be used without the operator. -->

- **WHEN** a boot is filmed from power-on to the shell
- **THEN** the film shows the stage 1 effect, the documented pause, the live continuation and the shell's first frame
