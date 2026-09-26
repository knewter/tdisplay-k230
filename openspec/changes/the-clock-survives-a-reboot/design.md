## Context

See proposal.md. Grounding, read directly from the pinned tree's own
unpacked source
(`/nix/store/bjgv1xn5b66gbz2kxv2aqzr1szp7dk7c-linux-xuantie-k230-src` at
the time of writing):

- `arch/riscv/boot/dts/canaan/k230.dtsi`'s `rtc@0x91000c00` node
  (`compatible = "canaan,k230-rtc"`) carries no `status` property at all,
  which per the devicetree spec means enabled by default — already
  confirmed in `docs/research/board-capability-inventory.md`.
- `drivers/rtc/rtc-k230.c` exists in this tree and matches that
  compatible string.
- `drivers/rtc/Kconfig`'s `RTC_DRV_K230` is `tristate ... default n
  depends on ARCH_CANAAN` — the one and only reason `/dev/rtc0` does not
  exist today.
- `nix/kernel.nix`'s `structuredExtraConfig` sets only
  `CONFIG_RTC_DRV_SUN6I=y` today (an Allwinner part not on this board) and
  no `RTC_DRV_K230` line at all — checked directly against the current
  file.
- NixOS's own `services.timesyncd` module
  (`nixos/modules/system/boot/timesyncd.nix`, read from the pinned
  nixpkgs source tree) is enabled by default
  (`default = !config.boot.isContainer`) and needs no configuration from
  this project; the actual write-back to `/dev/rtc0` after a successful
  NTP sync is `systemd-timesyncd`'s own built-in binary behavior
  (periodic and at clean shutdown), not something a NixOS module option
  configures — the Nix module only starts the daemon. This project's part
  is only making `/dev/rtc0` exist for that daemon to find.

## Goals / Non-Goals

**Goals:** `/dev/rtc0` exists; `hwclock -r` reads a plausible time;
`timedatectl` reports `RTC time` alongside `Local time`/`Universal time`;
a warm reboot's clock reflects the last known-good time rather than the
kernel's compiled-in epoch.

**Non-Goals:** claiming the RTC block survives a full power-off — that
depends on whether this specific board's RTC domain has a battery or
supercapacitor backing it, which is not documented anywhere in this
repository or in LILYGO's published hardware pinmap/BOM. This change
explicitly marks that scenario `UNVERIFIED` rather than inferring
"DT node enabled" as "survives power-off." Also non-goals: NTP server
configuration (`networking.timeServers` already covers this, untouched),
timezone/localtime handling.

## Decisions

1. **One Kconfig line, no device tree change.** The DT node is already
   `okay` by omission; adding an explicit `status = "okay";` would be a
   no-op restatement, not a fix. `RTC_DRV_K230 = yes;` (built-in, not a
   module — the RTC is needed from very early boot for a sane clock before
   any module-loading userspace runs, and this board's kernel builds most
   of its own SoC drivers in for the same reason). Kept in its own clearly
   delimited hunk in `nix/kernel.nix`'s `structuredExtraConfig`, since
   `feat/speaker` is concurrently editing this same file for audio
   Kconfig.
2. **Rely on `services.timesyncd`'s existing default enablement, and add
   one explicit `hwclock --systohc` unit rather than trusting only
   `systemd-timesyncd`'s internal periodic write-back.** `time-sync.target`
   is the standard systemd synchronization point reached once the first
   NTP sync completes; a small oneshot service ordered after it
   (`k230-rtc-sync.service`) runs `hwclock --systohc` once per boot. This
   makes the "NixOS uses it" contract this proposal asks for auditable
   (a named unit, inspectable with `systemctl status`) rather than resting
   entirely on `systemd-timesyncd`'s internal ~hourly write-back cadence,
   which could leave a short reboot-to-reboot gap where the RTC never got
   updated at all. Rejected: relying solely on `systemd-timesyncd`'s
   built-in behavior — correct on its own terms, but with no local,
   inspectable evidence in this repo that it actually ran on this board's
   `/dev/rtc0`, versus a named unit whose `systemctl status` and journal
   entries are exactly that evidence.
3. **`UNVERIFIED` is the honest answer for full power-off**, not a claim
   either way. The inventory found no schematic or BOM reference to a
   backing battery/supercap for this RTC domain, and this repository has
   no prior board observation of a full power-off's effect on the clock.
   The combined board test plan's RTC section is written to physically
   distinguish "warm reboot" (this change's actual claim) from "full
   power-off and wait" (left `UNVERIFIED` unless that test is separately
   run and its result recorded).

## Risks / Trade-offs

- [The RTC domain has no backing supply and loses time the instant main
  power drops, even briefly] → this is precisely why the two board-test
  scenarios (warm reboot vs. power-off-and-wait) are kept distinct rather
  than one combined "survives a reboot" claim; only the warm-reboot half
  is asserted as a requirement here.
- [`hwclock --systohc` running before the first NTP sync completes would
  write a wrong time into the RTC] → ordering `k230-rtc-sync.service` after
  `time-sync.target` (not merely after `systemd-timesyncd.service` starts)
  is specifically to avoid this; `time-sync.target` is only reached once a
  sync has actually completed.

## Migration Plan

Enable `RTC_DRV_K230`, add the sync unit; cross-build the kernel and full
system closure. Install the built kernel to `/boot` and reboot (a kernel
config change). Physical acceptance: confirm `/dev/rtc0`, `hwclock -r`,
`timedatectl`, reboot, and `hwclock -r` again to confirm persistence
across the warm reboot. Rollback is reverting this commit; nothing else
about system time handling changes.
