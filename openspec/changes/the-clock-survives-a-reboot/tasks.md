## 1. Kernel: enable the K230 RTC driver

- [x] 1.1 Add `RTC_DRV_K230 = yes;` to `nix/kernel.nix`'s
      `structuredExtraConfig`, in its own clearly delimited, separately
      commented block (no shared lines with `feat/speaker`'s audio
      Kconfig edits). Proven:
      `nix build .#kernel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      exited 0, producing
      `/nix/store/78cdif47ayqwv67m7crjpawfzy2mx3af-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`
      (build proof only) — one kernel derivation shared with the
      backlight and Bluetooth Kconfig/driver changes.
- [x] 1.2 Board finding (found during physical acceptance, task 4.1):
      `k230_rtc_read_time()` also masked the day-of-month field with
      `0xf` instead of `0x1f`. Added `nix/patches/k230-rtc-mday-mask.patch`,
      wired into `nix/kernel.nix`'s `patches` list. Proven:
      `nix build .#kernel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      exited 0, producing
      `/nix/store/16qspvmvblal5q059y8p6zbsn1ynjcdy-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`
      (build proof), and confirmed on the board (hardware proof, task 4.1).

## 2. NixOS: use the RTC

- [x] 2.1 Add `systemd.services.k230-rtc-sync`: a oneshot unit ordered
      after `time-sync.target`, running `hwclock --systohc`, in
      `nix/hardware.nix` (the real-hardware-only base; `nix/k230.nix` is
      the shared hardware+QEMU base). Proven:
      `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      exited 0, producing
      `/nix/store/152qrxpkagai2fahgyhkxq7sp8sk98n4-nixos-system-nixos-26.11.20260919.20b1ddd`,
      which schedules `unit-k230-rtc-sync.service` (build proof only).

## 3. Board test plan

- [x] 3.1 Add `ls /dev/rtc0`, `hwclock -r`, `timedatectl`, a reboot, then
      `hwclock -r` again to the combined board test plan
      (`docs/evidence/backlight-bluetooth-rtc-board-test-plan.md`), with
      expected output and the failure signature for "RTC exists but does
      not persist" (a reboot-to-reboot jump back to the kernel's
      compiled-in epoch) versus "no RTC at all" (`/dev/rtc0` missing,
      `hwclock -r` reporting no such device).

## 4. Physical acceptance

- [x] 4.1 Install the built kernel to `/boot` and reboot. Under the
      reserved board lock, confirm `ls /dev/rtc0`, run `hwclock -r` and
      `timedatectl`, reboot, and run `hwclock -r` again to confirm the
      clock survived the warm reboot. Done, plus a second board finding
      folded in: `k230_rtc_read_time()`'s day-of-month read mask was
      `0xf` (should be `0x1f`), dropping bit 4 — see
      `nix/patches/k230-rtc-mday-mask.patch` and
      `docs/evidence/rtc/mday-mask-fix.md`. Verified on the board: days
      15, 16 (the bit-4 boundary), 26 and 31 all read back correctly,
      and `hctosys` sets the correct time after a real cold reboot from
      a freshly bootswapped `/boot` (not the kernel's compiled-in
      epoch). `/proc/cmdline`'s `init=` on that boot confirms the new
      toplevel was actually running.
- [ ] 4.2 Leave `UNVERIFIED`: whether the RTC survives a full power-off
      (main power removed, not just a reboot) rather than only a warm
      reboot. Requires a documented backing supply or a separate
      power-off-and-wait board test not performed by this change; do not
      tick this task without that specific evidence.
