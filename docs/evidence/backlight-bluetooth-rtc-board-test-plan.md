# Board test plan: adjustable brightness, Bluetooth, persistent RTC

Branch `feat/brightness-bt-rtc`, based on `master` at `df2dd84e`. Three
kernel/DT/Nix changes land together in this branch (one commit each):
`the-panel-brightness-is-adjustable`, `the-handheld-talks-bluetooth`,
`the-clock-survives-a-reboot`. All three are **kernel and device-tree
changes** — they need a `/boot` install and a reboot, not just
`nixos-rebuild switch` / activation. I have not touched the board; every
command below is either a host build or something the coordinator runs on
the board or over the serial console (`/dev/ttyACM0`). Board/serial-port
reservation rules apply throughout (`AGENTS.md`): one operator at a time.

## 0. Build (host)

```sh
nix build .#kernel --max-jobs 1 --cores 6 --no-link --print-out-paths
nix build .#deviceTree --max-jobs 1 --cores 6 --no-link --print-out-paths
nix build .#sdImage-coherent --max-jobs 1 --cores 6 --no-link --print-out-paths
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths
```

Record the four store paths in the handoff. `sdImage-coherent` is the
image to flash; `toplevel` is the same closure `nixos-rebuild` would
converge to, useful for diffing what changed against the currently
installed system.

## 1. Install and reboot

Per `docs/uboot-ums.md`/`docs/evidence/usb-host-validation.md` (already
hardware-proven): flash `sdImage-coherent` via `ums 0 mmc 1` +
`tools/flash-latest.sh --ums`, or the card-reader fallback
`tools/flash-latest.sh /dev/disk/by-id/<reader-target>`. Reboot. Confirm
the new kernel is actually running before judging anything below:

```sh
./tools/console.py /dev/ttyACM0 --wait=3 "uname -a"
```

Cross-check the reported build against this branch's commit.

## 2. Backlight (`the-panel-brightness-is-adjustable`)

```sh
./tools/console.py /dev/ttyACM0 --wait=3 "ls /sys/class/backlight"
```

**Expected:** exactly one device directory (e.g. `canaan-dsi-backlight`).

**Failure signatures:**
- Empty output / `ls: cannot access`: the backlight device did not
  register — check `dmesg | grep -i backlight` for a probe error, and
  confirm `canaan,dsi-command-backlight` actually landed in the running
  DTB (`fdtdump` the installed `/boot/*.dtb` if in doubt).
- More than one device: an unexpected second backlight bound; do not
  assume which one the Settings stepper is driving — `tools/device_settings.py`
  refuses to guess when there is more than one (`Settings.backlight()`
  raises `"no unique panel backlight"`).

Write brightness at three points and camera-observe the panel each time
(camera on the bench, not touch — this is a visual check, not something to
judge by feel):

```sh
./tools/console.py /dev/ttyACM0 --wait=1 "cat /sys/class/backlight/*/max_brightness"
./tools/console.py /dev/ttyACM0 --wait=1 "echo 26 > /sys/class/backlight/*/brightness"   # ~10% of 255
./tools/console.py /dev/ttyACM0 --wait=1 "echo 128 > /sys/class/backlight/*/brightness"  # ~50%
./tools/console.py /dev/ttyACM0 --wait=1 "echo 255 > /sys/class/backlight/*/brightness"  # 100%
```

**Expected:** the panel visibly dims and brightens across the three
writes, camera-observable.

**Failure signatures:**
- Writes succeed (`echo` returns 0) but the panel does not visibly change:
  the DCS command is reaching the controller's write path but not its
  brightness block — check `dmesg` for `"failed to enable brightness
  control"` / `"failed to set display brightness"` (the `-110`/`ETIMEDOUT`
  signature already seen elsewhere in this driver's bring-up history means
  the DSI link itself is not answering, not a brightness-specific bug).
- `echo: write error: Invalid argument` / `Permission denied` writing as
  root over console: a permission or range problem independent of the
  udev rule (console root should always be able to write); investigate
  before blaming the shell-user path.

Cycle a modeset or DPMS-style off/on and confirm the brightness set above
(100%) is still in effect afterward, not the fixed `0xFE` default:

```sh
./tools/console.py /dev/ttyACM0 --wait=2 "modetest -M canaan -s <connector-id>:1232x568 || true"
./tools/console.py /dev/ttyACM0 --wait=1 "cat /sys/class/backlight/*/actual_brightness"
```

(`modetest` from `libdrm`, already in `environment.systemPackages` per
`nix/hardware.nix`; substitute the actual connector ID `modetest -M canaan`
reports.)

**Expected:** `actual_brightness` unchanged from before the modeset, and
the panel's visible brightness matches.

**Failure signature:** brightness reverts to the fixed default after the
cycle — the `ctx->panel.backlight` wiring (design.md decision 4) did not
take effect, or `drm_panel_enable()`/`disable()` are not actually being
called on this modeset path; check `dmesg` for the panel driver's own
`dev_info` lines around the cycle.

Also confirm the Settings stepper itself drives the device, once on
real glass:

```sh
./tools/console.py /dev/ttyACM0 --wait=2 "su - shell -c 'k230-settings brightness 50'"
./tools/console.py /dev/ttyACM0 --wait=1 "cat /sys/class/backlight/*/actual_brightness"
```

**Expected:** `{"state":"applied",...}` from `k230-settings`, and
`actual_brightness` at roughly 50% of `max_brightness`.

**Failure signature:** `{"state":"failed","error":"brightness-denied",...}`
— the udev rule did not grant the `shell` group write access; check
`ls -l /sys/class/backlight/*/brightness` for its group and mode.

## 3. Bluetooth (`the-handheld-talks-bluetooth`)

Plug the USB Bluetooth dongle into the board's USB host port (see
`docs/uboot-usb-host-verdict.txt` for confirmed host power/enumeration on
this exact port).

```sh
./tools/console.py /dev/ttyACM0 --wait=2 "lsusb"
./tools/console.py /dev/ttyACM0 --wait=3 "bluetoothctl show"
./tools/console.py /dev/ttyACM0 --wait=12 "bluetoothctl scan on"
./tools/console.py /dev/ttyACM0 --wait=3 "btmgmt info"
```

**Expected:**
- `lsusb` lists the dongle (`0a12:0001` for the bundled CSR8510 clone, or
  the attached device's actual vendor/product ID).
- `bluetoothctl show` reports a controller (`Controller <MAC> ... Powered:
  yes`).
- `bluetoothctl scan on` prints `[NEW] Device ...` lines for nearby
  discoverable devices within the 10 s window.
- `btmgmt info` reports the controller `current settings: powered
  ... running`.

**Failure signatures:**
- `lsusb` does not list the dongle at all: a USB host power problem, not
  a Bluetooth-stack problem — cross-check against
  `docs/evidence/uboot-usb-host-verdict.txt`'s known-good host state, and
  suspect the physical port/hub before the kernel config.
- `lsusb` lists the dongle but `bluetoothctl show` reports no controller,
  or `btmgmt info` never reaches a powered/running state: this is the
  LILYGO-quirk failure mode named in design.md — the bundled dongle may
  need the same `HCI_QUIRK_RESET_ON_CLOSE`-adjacent quirks LILYGO's BSP
  patches (`0056`, `0057-bluetooth-btusb-*.patch`) work around; check
  `dmesg | grep -i bluetooth` for `btusb` probe errors before porting
  those patches as a follow-up change.
- `bluetoothctl show` reports a controller but `scan on` finds nothing in
  a space with other Bluetooth devices present: check `rfkill list` for a
  software or hardware block.

## 4. RTC (`the-clock-survives-a-reboot`)

```sh
./tools/console.py /dev/ttyACM0 --wait=2 "ls /dev/rtc0"
./tools/console.py /dev/ttyACM0 --wait=2 "hwclock -r"
./tools/console.py /dev/ttyACM0 --wait=2 "timedatectl"
```

**Expected:** `/dev/rtc0` exists; `hwclock -r` reports a plausible current
time (not an error, not the kernel's compiled-in epoch); `timedatectl`
shows `RTC time` populated and close to `Universal time`/`Local time`.

**Failure signatures:**
- `hwclock -r` reports `hwclock: Cannot access the Hardware Clock via any
  known method` / `/dev/rtc0` missing: `RTC_DRV_K230` did not build in, or
  the DT node did not bind — check `dmesg | grep -i rtc` and confirm
  `CONFIG_RTC_DRV_K230=y` in the running kernel's `/proc/config.gz` (if
  enabled) or the build's `.config`.
- `timedatectl`'s `RTC time` is present but implausible (far future/past):
  `k230-rtc-sync.service` wrote before a real NTP sync completed — check
  `systemctl status k230-rtc-sync` and its ordering against
  `time-sync.target`.

Reboot (warm reboot only — do not remove power for this step) and check
again:

```sh
./tools/console.py /dev/ttyACM0 --wait=2 "reboot"
# wait for the board to come back, then:
./tools/console.py /dev/ttyACM0 --wait=3 "hwclock -r"
```

**Expected:** the time reported after reboot is consistent with (a few
seconds later than) the time reported before reboot — not reset to the
kernel's compiled-in epoch.

**Failure signature:** the post-reboot `hwclock -r` jumps back to a
epoch-adjacent implausible time — the RTC exists but is not actually
retaining the value across even a warm reboot (a stronger negative result
than the `UNVERIFIED` full-power-off case below); check
`systemctl status k230-rtc-sync` from the *previous* boot's journal
(`journalctl -b -1 -u k230-rtc-sync`) to see whether it ran and succeeded
before the reboot.

**Left `UNVERIFIED` by this test plan:** whether the clock survives a full
power-off (main power removed, not merely a warm reboot). That needs a
separate power-off-and-wait test with the result recorded against task
4.2 of `the-clock-survives-a-reboot`; do not infer it from the warm-reboot
result above.
