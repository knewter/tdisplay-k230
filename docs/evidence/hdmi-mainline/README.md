# Mainline HDMI continuation, 2026-10-09 UTC

Evidence class: **physical board, serial console**, **native Grim capture**,
and the **operator's monitor observation**. A screenshot is not a photograph
of the monitor. This change remains open; no automatic switch or repeatable
fixed-bundle boot is claimed by this checkpoint.

## Original trial and identity

The interrupted Claude session built source `edd74d1626d03770e08e328320b18118ece24508`
and ran `tools/coherent-shell-board-boot.py` against its HDMI bundle. The
continuation found the board still running that volatile trial, with normal
panel boot files unchanged. The controller's private raw capture and
`serial-result.json` remain under `~/tmp/k230-hdmi-board/candidate/`.
The continuation's private raw UART captures are under
`~/tmp/k230-hdmi-continue-private/`.

Host command:

```sh
python3 tools/coherent-shell-boot-inspect.py ~/tmp/k230-hdmi-bundle
```

It passed. [Inspection](original-bundle-inspection.json) records the immutable
bundle, kernel, system, DTB and boot-file hashes. The running system was
`/nix/store/6armjz2q35gdyv5l8vas4k9mk48nzzhq-nixos-system-nixos-26.11.20260919.20b1ddd`,
kernel `7.3.0-rc5`. [Initial serial state](initial-state.txt), captured at
`2026-10-09T05:12:01Z`, preserves these identities and DRM state.
The operator reported the monitor connected, powered on and black.

## Shared-reset failure and live recovery

The original log initializes LT9611 at 2.53 seconds and decodes
1920 horizontal pixels at 4.77 seconds. Goodix begins probing at 4.83
seconds and registers its input at 4.98 seconds. Subsequent bridge reads
report zero video, no EDID and disconnected HPD. The operator sees black.
See [DRM and touch state](drm-and-touch-state.txt).

The touch driver in the read pinned source
`drivers/input/touchscreen/goodix_berlin_core.c:goodix_berlin_probe()` obtains
the reset with `GPIOD_OUT_HIGH`, which asserts the active-low GPIO24 before
`goodix_berlin_power_on()` releases it. This also resets LT9611, whose own
driver intentionally does not own the shared line.

The kernel's regmap debugfs reads returned zeros, including chip revision,
system-init and Port-B registers. Reads used `dd` with nine-byte register
records and the register number as its block offset, for example:

```sh
dd if=/sys/kernel/debug/regmap/0-003b/registers bs=9 skip=32770 count=1 status=none
```

See [reset register state](reset-registers.txt). `modprobe i2c-dev` made the
confirmed I2C3 adapter, Linux adapter **0** on this boot, available to userspace.
With the connector temporarily forced on to suppress detect polling, these
two **separate** I2C transfers restored access:

```sh
i2ctransfer -f -y 0 w2@0x3b 0xff 0x80
i2ctransfer -f -y 0 w2@0x3b 0xee 0x01
i2ctransfer -f -y 0 w1@0x3b 0x00 r3
```

The ID read returned `0x17 0x02 0xe2`; see [raw ID](restored-i2c-id.txt).
A preceding attempted combined transfer and a preceding attempt before
loading `i2c-dev` did not restore access; they are not successful evidence.
Debugfs reads of page 0x83 and then 0x80 resynchronized the kernel's cached
page selector after the raw access. Sway then received:

```sh
swaymsg 'output HDMI-A-1 power off'
swaymsg 'output HDMI-A-1 modeline 148.500 1920 2008 2052 2200 1080 1084 1089 1125 +hsync +vsync'
swaymsg 'output HDMI-A-1 power on'
echo detect > /sys/class/drm/card0-HDMI-A-1/status
```

Commands ran as `shell` with `SWAYSOCK=/run/shell/sway-ipc.sock`, except the
root-only connector write. [Recovery serial state](live-video-recovery.txt)
records a decoded 1920-pixel input, `hsfreqrange 0x96`, HPD `0x0d`, automatic
`connected` status, a **256-byte EDID** and 1080p modes. The bridge reports
`vactive=1081` rather than 1080; this discrepancy remains recorded rather
than corrected by inference. No PHY tuning was needed in this recovery.

The operator then reported **"screen works"**. This is physical monitor
confirmation of the live workaround, not of a fresh boot of the source fix.

At approximately `2026-10-09T05:23Z`, the board ran:

```sh
runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 \
  grim /run/shell/mainline-hdmi.png
```

[Native capture](live-mainline-hdmi.png) is 1080×1920 logical pixels, from
physical 1920×1080 with Sway transform 90. The PNG was copied over the serial
console using base64. It contains the live Home screen, not a host render.

## Mouse follow-up

The operator reported no mouse cursor and no response to touch.
[Input discovery](missing-relay.txt) shows direct-touch events disabled,
no touchpad input, no relay unit and no relay executable in the system PATH.
The original HDMI bundle extends the ordinary mainline profile; it omitted
the relay enabled by the earlier vendor HDMI trial profile.

The already-realized relay was imported into the board's store, but starting
it was blocked by the absence of `uinput` in this kernel; see
[module diagnostic](missing-uinput.txt). This import alone is not mouse proof.

## Source fix and remaining gates

The reset-ordering LT9611 source cross-compiled as an object against the
original kernel's exact development tree. The same tree built an external
`uinput` module for the live mouse trial. The boot-inspector's 15 tamper and
configuration fixtures pass, including the new HDMI profile identity.
[Host checks](host-checks.json) record commands, store paths and source/module
hashes; [object recipe](live-lt9611-check.nix) and
[module recipe](live-uinput.nix) preserve the commands' inputs. These narrow
checks are not substitutes for the full-kernel build required by task 7.1.

The continuation makes LT9611 wait for the I2C touch device to finish binding,
using the board-local `lontium,shared-reset-owner` phandle and a managed device
link. This prevents initialization before the shared reset and orders removal
and system suspend. The panel tree does not instantiate LT9611.

The separate `k230-mainline-drm-shell-hdmi` configuration enables the existing
relay and loads `uinput`; the HDMI boot bundle now selects that configuration.
The mainline DRM kernel enables `INPUT_UINPUT=m`. These source changes need
their own complete build and a new volatile board boot before claiming the
failure is fixed reproducibly. Task 7.3 stays unchecked until that boot,
native capture and physical pointer interaction are recorded. Normal panel
recovery also remains a separate observation.

The inherited card-shell QEMU kernel build was stopped to prioritize HDMI
and retain one heavy build at a time in this session. Its task 5.1 remains
unproved; no QEMU pass or archive is claimed here.
