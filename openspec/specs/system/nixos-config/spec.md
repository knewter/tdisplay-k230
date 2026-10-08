# system/nixos-config Specification

## Purpose
Defines what the NixOS system for this board contains, what it guarantees when
it boots, and where the boundary sits between what we build and what is
vendored from Canaan.

## Requirements

### Requirement: The system boots to a console prompt

*Grounding: observed on both halves. QEMU: `docs/evidence/qemu-boot.txt`.
Hardware: a root prompt was reached on the board over the CH342 serial console
at 115200 8N1, with no display, no keyboard and no network, and commands were
run at it (`docs/evidence/hardware-userspace.md`). The transcript format is
shared, as the requirement intends.*

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

### Requirement: Chicago local time is the image default

The system SHALL use `America/Chicago` as its local timezone, providing Central local time to applications without restoring home-directory state. This is owned by the NixOS system; it does not change the UTC hardware-clock or synchronization policy.

*Grounding: `docs/evidence/chicago-clock/runtime.json` records the physical board reporting `Timezone=America/Chicago` and a local CDT offset after the requested runtime setting. The repository configuration and installed profile are verified separately in the same evidence directory.*

#### Scenario: Default configuration is built

- **WHEN** the board configuration is evaluated and built
- **THEN** its timezone is America/Chicago and its generated localtime link selects that zone

#### Scenario: Profile is activated

- **WHEN** the configured profile is activated on the board
- **THEN** `timedatectl` reports America/Chicago and ordinary local-time output uses the zone's current offset

### Requirement: The coherent shell boots the selected system with matching boot artifacts

*Grounding: `docs/evidence/boot-verification/coherent-bundle-host/README.md` binds the kernel, initrd, DTB and init to one configuration. `docs/evidence/boot-verification/coherent-ordinary-boot/README.md` records installation and uninterrupted ordinary autoboot with matching system/profile/kernel/init and active shell services. `docs/evidence/mainline-display/physical-2026-10-01/power-swap-recovery-2026-10-02/README.md` independently verifies the same normal selection after physical reset; `docs/evidence/boot-verification/coherent-ordinary-boot/operator-navigation.json` records operator acceptance of Home→All apps, handle→Overview and Terminal open/return after that reboot.*

The system SHALL provide matching kernel, initrd, board device tree and explicit boot init for the selected coherent-shell configuration. After ordinary boot the person SHALL see a usable shell on the panel and the serial console SHALL report that exact selected system, rather than an older boot generation.

#### Scenario: A qualified shell update is rebooted
- **WHEN** a qualified coherent-shell bundle is installed and the device boots normally
- **THEN** the panel shows the usable shell, navigation responds, and serial identities match the selected system and its boot artifacts

#### Scenario: A runtime activation has not installed matching boot files
- **WHEN** an updated shell runs after test activation but persistent boot still selects an older generation
- **THEN** its published status identifies runtime-only deployment and does not claim the new system survives reboot

### Requirement: A failed coherent-shell boot remains recoverable

*Grounding: `docs/evidence/boot-verification/2026-10-01/README.md` records a failed candidate and restored normal system with photographed Home. `docs/evidence/boot-verification/coherent-ordinary-boot/README.md` records checked root-backed boot backups, retained GC roots, serial manual recovery, successful persistent installation and its interruption window. The later physical power-swap recovery verifies all eight protected hashes and visible normal Home. Physical failed-write rollback and power-cut installation testing remain unperformed and are not claimed.*

The system update procedure SHALL retain a usable normal boot backup and serial recovery before selection. A failed candidate SHALL remain unaccepted until the normal system is restored and its visible shell and protected identities are observed.

#### Scenario: The candidate starts services but the panel is black
- **WHEN** a candidate reaches serial login and active services but fails visible shell acceptance
- **THEN** it is recorded as a failed display trial, the normal system is restored, and the failed candidate is not selected as the persistent default

### Requirement: The mainline full shell starts the same units as the vendor-kernel shell
The `k230-mainline-drm-shell` variant SHALL start every systemd unit the
vendor-kernel coherent shell starts, except units listed as recorded non-goals
with their reason, and it SHALL remain an opt-in trial that never replaces the
protected normal system or its boot selection.

#### Scenario: No unexpected failed units
- **WHEN** the mainline full shell has booted through the guarded trial
- **THEN** `systemctl --failed` on the serial console lists no units other than recorded non-goals
*Grounding: observed on hardware 2026-10-06 (`docs/evidence/mainline-shell-parity-2026-10-06/README.md`): 0 failed units, firewall active (before the netfilter fragment it failed).*

#### Scenario: Normal system unaffected
- **WHEN** the trial ends and the board returns to the normal system
- **THEN** the protected normal identities, eight boot hashes and three shell services are unchanged

### Requirement: The installed daily system is the mainline coherent shell
The system profile and `/boot` mutable files SHALL select the mainline coherent
shell built from this repository, with stage 1 and the DT selector files
unchanged, and the board-side trial tooling SHALL treat that installed system as
the protected normal it verifies before and after every trial.

#### Scenario: Installed identities are recorded
- **WHEN** installation completes
- **THEN** the recorded installer journal lists the new system, the four replaced boot files with hashes, the unchanged protected files, and the retained rollback roots
*Grounding: observed on hardware 2026-10-07 (`docs/evidence/mainline-default-boot/first-install-journal.json`): journal lists system `5g3ylmyy…`, before/after hashes of all eight boot files (OpenSBI wrapper and selectors unchanged) and both rollback GC roots.*

#### Scenario: Trials guard the new normal
- **WHEN** a guarded mainline trial runs after installation
- **THEN** its preflight and recovery checks expect the installed mainline identities, not the vendor 6.6 ones
<!-- UNVERIFIED: the baseline (`docs/evidence/mainline-default-boot/postboot.json`) and tooling are updated and unit-tested, but no guarded trial has yet run against the installed mainline normal -->
