## Purpose

Defines what executes before our kernel on this board, which parts are
vendored, and how control reaches the system we built.

## ADDED Requirements

### Requirement: Stage 1 is a pinned vendored artifact

The boot chain before our kernel SHALL be a vendored binary, pinned by content
hash, with its origin recorded — which SDK, which board configuration, and how
it was produced. It SHALL NOT be built from source by this project.

*Grounding: `docs/rtsmart-boot-log.txt` records the chain on this board:
`U-Boot SPL 2022.10`, the DDR PMU training messages, `U-Boot 2022.10`, and
`OpenSBI v0.9`. Canaan wraps these in a custom header with compression
(`image: uboot load to 20000000 compress =1`).*

#### Scenario: The vendored firmware is inspected

- **WHEN** someone asks where the bootloader on the card came from
- **THEN** the flake names its source, its board configuration, and its hash

### Requirement: Stage 1 hands control to our kernel

<!-- UNVERIFIED: no image of ours has been loaded by this chain yet.
Grounded by docs/evidence/hardware-boot.txt. -->

The vendored chain SHALL load the kernel, device tree and initrd this project
builds, from the SD card, without modification to stage 1 itself. Where stage 1
requires a particular filename, location or image format, that requirement
SHALL be recorded as a property of the vendored artifact rather than discovered
again each time.

#### Scenario: A built system is placed on a card and the board is powered on

- **WHEN** the board boots with our image on its SD card
- **THEN** the vendored chain loads our kernel, and the console shows it starting

### Requirement: The hardware boot path differs from the emulated one, and that difference is recorded

*Grounding: `docs/evidence/boot-path-differences.md` records the comparison,
started during `a-riscv-nixos-closure-cross-builds`. Two differences are
already observed rather than anticipated: QEMU's `k230` machine models no
block device, and it generates no FDT at all (`dumpdtb` answers "This machine
doesn't have an FDT").*

Under QEMU the kernel is loaded directly; on hardware it is loaded by vendored
U-Boot. The project SHALL record what differs between the two paths, so that a
failure on hardware after a success under emulation is diagnosed against a
written expectation rather than from memory.

#### Scenario: An image boots under QEMU but not on the board

- **WHEN** the two paths disagree
- **THEN** the recorded differences are the first place to look, and they are specific enough to be checked one at a time
