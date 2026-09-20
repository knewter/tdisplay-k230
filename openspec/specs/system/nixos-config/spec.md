# system/nixos-config Specification

## Purpose
Defines what the NixOS system for this board contains, what it guarantees when
it boots, and where the boundary sits between what we build and what is
vendored from Canaan.

## Requirements

### Requirement: The system boots to a console prompt

*Grounding: `docs/evidence/qemu-boot.txt`. Booted under
`qemu-system-riscv64 -machine virt` on 2026-09-20, reaching
`<<< Welcome to NixOS kexec-26.11.20260919.20b1ddd (riscv64) - ttyS0 >>>`
and an interactive shell on `ttyS0` at 115200 8N1, with no display, no
keyboard and no network configured. OpenSBI v1.8.1 handed off to S-mode and
systemd reached `Login Prompts`.*

The system SHALL boot to an interactive console prompt on the serial console
without a display, a keyboard, or a network. Everything this project does next
is done through that prompt, so it is the first thing that must hold.

The console SHALL be the serial console at 115200 8N1, matching the board's
CH342 bridge, so that one transcript format serves both QEMU and hardware.

What this proves is machine-independent: that the closure is coherent and
that userspace starts. It SHALL NOT be read as evidence about the board.

*The emulated machine is `virt`, not `k230`, and that is a finding rather
than a shortcut. Mainline Linux has no bootable K230 platform: 6.18.52
carries `pinctrl-k230.c` and `reset-k230.c` but ships no K230 device tree
(`arch/riscv/boot/dts/canaan/` is K210-only) and has no `SOC_CANAAN_K230` —
only `SOC_CANAAN_K210`, which is `depends on !MMU`. A `k230`-machine boot
additionally needs the Xuantie kernel built with `CONFIG_ERRATA_THEAD_PBMT=n`,
that errata being the T-Head MAEE page-table extension QEMU does not
implement. That kernel is the panel bring-up's to package.*

#### Scenario: The system boots under emulation

- **WHEN** the system is booted under QEMU on a riscv64 machine
- **THEN** a console prompt is reached, and the transcript is committed as evidence

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
out of scope.*

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
