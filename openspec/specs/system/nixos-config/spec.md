# system/nixos-config Specification

## Purpose
Defines what the NixOS system for this board contains, what it guarantees when
it boots, and where the boundary sits between what we build and what is
vendored from Canaan.

## Requirements

### Requirement: The system boots to a console prompt

*Grounded on both halves. QEMU: `docs/evidence/qemu-boot.txt`. Hardware: a
root prompt was reached on the board over the CH342 serial console at 115200
8N1, with no display, no keyboard and no network, and commands were run at it
(`docs/evidence/hardware-userspace.md`). The transcript format is shared, as
the requirement intends.*

The system SHALL boot to an interactive console prompt on the serial console
without a display, a keyboard, or a network.

The console SHALL be the serial console at 115200 8N1, matching the board's
CH342 bridge, so that one transcript format serves both QEMU and hardware.

**This SHALL hold on the physical board, not only under emulation.** A boot
under QEMU's `k230` machine is not evidence for this requirement, because that
machine models neither the vendored boot chain nor the SD card the board loads
from.

#### Scenario: The system boots under emulation

- **WHEN** the system is booted under QEMU's `k230` machine
- **THEN** a console prompt is reached, and the transcript is committed as evidence

#### Scenario: The system boots on the board

- **WHEN** the board is powered on with a flashed card and a data cable attached
- **THEN** a console prompt is reached on `/dev/ttyACM0`, and that transcript is committed as evidence

#### Scenario: Someone reads an emulated boot as a claim about the board

- **WHEN** an emulated boot succeeds
- **THEN** the evidence records which machine was emulated and what it does not model, so the claim cannot be over-read

### Requirement: Stage 1 is vendored, and the system does not build it

BootROM, the U-Boot SPL and its DDR PMU training firmware, U-Boot, and OpenSBI
SHALL be treated as a vendored binary input. The build SHALL NOT attempt to
compile them from source.

*Grounding: `docs/rtsmart-boot-log.txt` records the chain on this board —
`U-Boot SPL 2022.10`, the PMU training messages, `U-Boot 2022.10`, then
`OpenSBI v0.9`. Canaan packages these with a custom header and compression
(`image: uboot load to 20000000 compress =1`), which is why reproducing them is
out of scope. That `v0.9` belongs to the shipped RT-Smart image and is not the
SBI our kernel boots through: the Linux path uses the SDK's
`opensbi-1.4-overlay` — OpenSBI 1.4 plus Canaan's T-Head overlay — recorded in
`firmware/stage1/PROVENANCE.txt` and `docs/evidence/boot-path-differences.md`.*

This boundary SHALL be explicit in the build rather than implied by what
happens not to be built, so that a later change cannot acquire a dependency on
building stage 1 without saying so.

#### Scenario: The build is inspected for what it compiles

- **WHEN** someone asks whether the project builds its own bootloader
- **THEN** the build names stage 1 as a vendored input, and no derivation compiles U-Boot or OpenSBI

### Requirement: The system is minimal and says what it is for

*Grounding: measured against the built closure rather than asserted —
`/nix/store/lzg30bab6kqkgsa54jaql1ixfxgizxv3-nixos-system-nixos-...` is
1.2 GiB over 474 store paths and contains zero NetworkManager, ModemManager,
xserver or mesa paths. Recorded in `docs/evidence/cross-build.txt`. The QEMU
variant is deliberately heavier — `netboot-minimal` imports
`installation-device` — but that is the test harness and never reaches the
board.*

The system SHALL contain what is needed to reach a prompt and inspect the
machine, and SHALL NOT carry a desktop, a display manager, or a graphical
stack. Absent a binary cache every added package is compiled, so the closure's
contents are a cost paid on every clean build.

#### Scenario: A package is proposed for the system

- **WHEN** something is added to the system closure
- **THEN** the reason it is needed to reach or use a prompt is recorded, or it is left out
