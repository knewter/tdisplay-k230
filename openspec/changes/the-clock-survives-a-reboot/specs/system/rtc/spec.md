## ADDED Requirements

### Requirement: The on-chip RTC is usable from Linux

<!-- UNVERIFIED: no boot log yet confirms /dev/rtc0 appears or that
hwclock reads a plausible time on this board. -->

The system SHALL expose the K230 SoC's on-chip RTC as `/dev/rtc0`, and
`hwclock -r` and `timedatectl` SHALL report a plausible time from it.

*Grounding: `arch/riscv/boot/dts/canaan/k230.dtsi` in the pinned Xuantie
kernel tree already carries `rtc@0x91000c00` (`compatible =
"canaan,k230-rtc"`) with no `status` override, meaning enabled by default
per the devicetree spec; `drivers/rtc/rtc-k230.c` already exists in the
same tree, gated only by `RTC_DRV_K230`, which our
`structuredExtraConfig` never set — setting instead only the unrelated
`CONFIG_RTC_DRV_SUN6I=y`.*

#### Scenario: A person checks the RTC device

- **WHEN** a person runs `ls /dev/rtc0` on the board
- **THEN** the device exists

#### Scenario: A person reads the RTC time

- **WHEN** a person runs `hwclock -r` or `timedatectl`
- **THEN** a plausible current time is reported, not an error or the
  kernel's compiled-in epoch

### Requirement: The wall clock survives a warm reboot

The system's time, once synchronized (by NTP or by an explicit
`hwclock --systohc`), SHALL survive a warm reboot: the system clock
immediately after boot SHALL reflect the last known-good time rather than
resetting to the kernel's compiled-in epoch.

*Grounding: `services.timesyncd` is enabled by default in NixOS
(`nixos/modules/system/boot/timesyncd.nix`, `default =
!config.boot.isContainer`) and writes a synced time back to a present RTC;
this change additionally runs `hwclock --systohc` in a
`k230-rtc-sync.service` unit ordered after `time-sync.target`, so the
write-back is both automatic and independently auditable.*

#### Scenario: The board reboots after the clock was synchronized

- **WHEN** the system's time has been synchronized and the board is then
  rebooted (power stays applied to the SoC's RTC domain throughout)
- **THEN** the clock immediately after boot matches the time before reboot,
  not the kernel's compiled-in epoch

### Requirement: Survival across a full power-off is unverified

<!-- UNVERIFIED: no documented backing supply for this RTC domain and no
board observation of a full power-off's effect on the clock. -->

Whether the RTC keeps time across a full power-off (main power removed,
not merely a warm reboot) SHALL NOT be claimed as working until a backing
supply (battery or supercapacitor) for this RTC domain is documented from
the schematic or BOM, or a physical power-off-and-wait test is performed
and recorded.

*Grounding: neither this repository's DT/schematic notes nor LILYGO's
published hardware pinmap document a backing supply for the K230 RTC
block; the inventory and this proposal deliberately do not infer one from
the DT node being `okay`.*

#### Scenario: Someone asks whether the clock survives a full power-off

- **WHEN** someone asks whether unplugging the board (not just rebooting
  it) preserves the RTC's time
- **THEN** the answer is that this is unverified, pending either a
  documented backing supply or a recorded power-off-and-wait board test
