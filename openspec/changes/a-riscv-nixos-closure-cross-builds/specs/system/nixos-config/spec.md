## Purpose

Defines what the NixOS system for this board contains, what it guarantees when
it boots, and where the boundary sits between what we build and what is
vendored from Canaan.

## ADDED Requirements

### Requirement: The system boots to a console prompt

<!-- UNVERIFIED: no image has been booted yet. Grounded once
docs/evidence/qemu-boot.txt records the transcript. -->

The system SHALL boot to an interactive console prompt on the serial console
without a display, a keyboard, or a network. Everything this project does next
is done through that prompt, so it is the first thing that must hold.

The console SHALL be the serial console at 115200 8N1, matching the board's
CH342 bridge, so that one transcript format serves both QEMU and hardware.

#### Scenario: The system boots under emulation

- **WHEN** the system is booted under QEMU's `k230` machine
- **THEN** a console prompt is reached, and the transcript is committed as evidence

### Requirement: Stage 1 is vendored, and the system does not build it

BootROM, the U-Boot SPL and its DDR PMU training firmware, U-Boot, and OpenSBI
SHALL be treated as a vendored binary input. The build SHALL NOT attempt to
compile them from source.

*Grounding: `docs/rtsmart-boot-log.txt` records the chain on this board —
`U-Boot SPL 2022.10`, the PMU training messages, `U-Boot 2022.10`, then
`OpenSBI v0.9`. Canaan packages these with a custom header and compression
(`image: uboot load to 20000000 compress =1`), which is why reproducing them is
out of scope.*

This boundary SHALL be explicit in the build rather than implied by what
happens not to be built, so that a later change cannot acquire a dependency on
building stage 1 without saying so.

#### Scenario: The build is inspected for what it compiles

- **WHEN** someone asks whether the project builds its own bootloader
- **THEN** the build names stage 1 as a vendored input, and no derivation compiles U-Boot or OpenSBI

### Requirement: The system is minimal and says what it is for

<!-- UNVERIFIED: no closure exists yet. -->

The system SHALL contain what is needed to reach a prompt and inspect the
machine, and SHALL NOT carry a desktop, a display manager, or a graphical
stack. Absent a binary cache every added package is compiled, so the closure's
contents are a cost paid on every clean build.

#### Scenario: A package is proposed for the system

- **WHEN** something is added to the system closure
- **THEN** the reason it is needed to reach or use a prompt is recorded, or it is left out
