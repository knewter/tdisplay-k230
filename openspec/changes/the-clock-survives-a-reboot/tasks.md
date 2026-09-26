## 1. Kernel: enable the K230 RTC driver

- [x] 1.1 Add `RTC_DRV_K230 = yes;` to `nix/kernel.nix`'s
      `structuredExtraConfig`, in its own clearly delimited, separately
      commented block (no shared lines with `feat/speaker`'s audio
      Kconfig edits). Prove with
      `nix build .#kernel --max-jobs 1 --cores 6` (build proof only).

## 2. NixOS: use the RTC

- [x] 2.1 Add `systemd.services.k230-rtc-sync`: a oneshot unit ordered
      after `time-sync.target`, running `hwclock --systohc`, in
      `nix/k230.nix`. Prove with
      `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      (build proof only).

## 3. Board test plan

- [x] 3.1 Add `ls /dev/rtc0`, `hwclock -r`, `timedatectl`, a reboot, then
      `hwclock -r` again to the combined board test plan
      (`docs/evidence/backlight-bluetooth-rtc-board-test-plan.md`), with
      expected output and the failure signature for "RTC exists but does
      not persist" (a reboot-to-reboot jump back to the kernel's
      compiled-in epoch) versus "no RTC at all" (`/dev/rtc0` missing,
      `hwclock -r` reporting no such device).

## 4. Physical acceptance

- [ ] 4.1 Install the built kernel to `/boot` and reboot. Under the
      reserved board lock, confirm `ls /dev/rtc0`, run `hwclock -r` and
      `timedatectl`, reboot, and run `hwclock -r` again to confirm the
      clock survived the warm reboot. Commit console output under
      `docs/evidence/rtc/` (hardware proof only).
- [ ] 4.2 Leave `UNVERIFIED`: whether the RTC survives a full power-off
      (main power removed, not just a reboot) rather than only a warm
      reboot. Requires a documented backing supply or a separate
      power-off-and-wait board test not performed by this change; do not
      tick this task without that specific evidence.
