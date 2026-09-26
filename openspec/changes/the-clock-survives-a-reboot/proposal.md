## Why

Without a working RTC, every boot starts the system clock at the kernel's
compiled-in epoch until NTP catches up, which is wrong for anything that
timestamps files, logs, or notifications before the network is up — and is
simply wrong forever if there is no network. The on-chip K230 RTC is
already described in the device tree and `status`-enabled by default
(`rtc@0x91000c00`, `compatible = "canaan,k230-rtc"`, no `status` override).
`docs/research/board-capability-inventory.md` finds the entire gap is a
single Kconfig line: `drivers/rtc/rtc-k230.c` already exists in our pinned
kernel source tree, but `RTC_DRV_K230` defaults to `n` and our
`structuredExtraConfig` never sets it — instead setting only the unrelated
`CONFIG_RTC_DRV_SUN6I=y` (an Allwinner RTC this board does not have).

## What Changes

- Enable `RTC_DRV_K230` so `/dev/rtc0` (backed by the already-`okay`
  device-tree node) appears.
- Make NixOS actually use it: rely on `systemd-timesyncd`'s existing
  default behavior of writing NTP-corrected time back to the RTC when one
  is present, and run `hwclock --systohc` at points where that is the
  standard mechanism, so the wall clock a reboot sees reflects the last
  known-good time.
- Do not claim more than is grounded: whether this RTC block has a battery
  or supercapacitor backing it that survives a full power cycle (versus
  only a warm reboot, where the SoC's own rail may stay powered) is not
  established anywhere in this repository or in LILYGO's documentation.
  This change marks "the RTC keeps time across a full power-off" as
  explicitly `UNVERIFIED` rather than inferring it from the DT node being
  enabled, and the board test plan is written to distinguish the two cases
  (warm reboot vs. a real power-off-and-wait).

## Capabilities

### New Capabilities

- `system/rtc`: the `system/` group already holds `nixos-config`, `kernel`
  and `console`; wall-clock persistence is a person-observable capability
  distinct from all three (it is not "the kernel boots," it is not "there
  is a NixOS closure," and it is not "there is a console") and gets its
  own spec file, per the inventory's own suggestion.

### Modified Capabilities

None.

## Impact

The kernel (`nix/kernel.nix` — one Kconfig line, in its own clearly
delimited hunk since `feat/speaker` is concurrently editing this same
file) and NixOS time configuration (`nix/hardware.nix` or `nix/k230.nix`).
No device-tree change — the RTC node is already enabled. Confirming
`/dev/rtc0` exists, that `hwclock -r` reads a plausible time, and that a
warm reboot preserves it are hardware-only gates. Whether a full
power-off preserves it stays `UNVERIFIED` unless a backing supply is
documented on the schematic; this change does not claim otherwise.
