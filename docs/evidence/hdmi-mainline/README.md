# Mainline HDMI continuation, 2026-10-09 UTC

Evidence class: **physical board, serial console**, **native Grim capture**,
and the **operator's monitor observation**. A screenshot is not a photograph
of the monitor. The corrected bundle has a matching fresh volatile boot and automatic relay
startup. Physical picture/tap acceptance of that boot and automatic switching
remain open; this change is not archived.

## Original trial and identity

The interrupted Claude session built source `edd74d1626d03770e08e328320b18118ece24508`
and ran `tools/coherent-shell-board-boot.py` against its HDMI bundle. The
continuation found the board still running that volatile trial, with normal
panel boot files unchanged. The controller's private raw capture and
`serial-result.json` remain under `~/tmp/k230-hdmi-board/candidate/`.
The [sanitized trial report](original-trial-boot.json) preserves the controller
and loaded artifact hashes, running identities and unchanged-profile result.
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

The host then compiled the upstream `drivers/input/misc/uinput.c` against
the running Image's exact kernel development output. The module was copied
to `/run/k230-uinput-trial.ko` with `tools/push-file.py` under the board lock;
the transfer verified MD5 `10385a49550e6735a5f84271d08018ba` on the board.
`insmod /run/k230-uinput-trial.ko` succeeded. A transient
`k230-hdmi-trackpad-trial` service started the already-realized relay:

```sh
systemd-run --unit=k230-hdmi-trackpad-trial --property=Restart=on-failure \
  --property=DevicePolicy=closed --property='DeviceAllow=/dev/uinput rw' \
  --property='DeviceAllow=char-input rw' --property=ProtectSystem=strict \
  --property=ProtectHome=true --property=NoNewPrivileges=true \
  /nix/store/v0n70zk76z0p3xky67613769l8pc2lrl-k230-touch-trackpad-riscv64-unknown-linux-gnu-0.1.0/bin/k230-touch-trackpad \
  --shell-socket=/run/shell/sway-ipc.sock
```

[Startup state](live-pointer-start.txt) shows the relay grabbing the actual
Goodix input and Sway recognizing an enabled virtual touchpad. This older
relay warns that `--shell-socket` is unknown and ignores it: it supplies
basic pointer/tap behavior, not the newer shell gesture integration. The
corrected bundle builds the current relay. Physical cursor movement and tap
acceptance must be recorded separately from this startup result.

At `2026-10-09T05:36:40Z`, the newly built current-source relay
`/nix/store/gy6r7r8pf8694pras6njlvgbpmjgg3n8-k230-touch-trackpad-riscv64-unknown-linux-gnu-0.1.0`
replaced the older relay in transient service
`k230-hdmi-trackpad-current-trial`. [Current startup](current-pointer-start.txt)
records its active state, successful grab and enabled virtual touchpad, with
no unknown-argument warning. The monitor remains automatically connected
with a 256-byte EDID. This update does not reboot or change the profile.

At `2026-10-09T05:42:05Z`, a compositor command placed the cursor at logical
`(540, 900)`, then Grim captured it with `-c`:

```sh
swaymsg 'seat seat0 cursor set 540 900'
grim -c /run/shell/hdmi-pointer.png
```

[Native cursor capture](live-pointer-native.png) shows the cursor. This is
**injected compositor movement**, not finger input or a physical monitor
photograph. It proves cursor rendering and does not complete the touch gate.

## Source fix and remaining gates

The reset-ordering LT9611 source cross-compiled as an object against the
original kernel's exact development tree. The same tree built an external
`uinput` module for the live mouse trial. The boot-inspector's 15 tamper and
configuration fixtures pass, including the new HDMI profile identity.
[Host checks](host-checks.json) record commands, store paths and source/module
hashes; [object recipe](live-lt9611-check.nix) and
[module recipe](live-uinput.nix) preserve the commands' inputs. These narrow
checks are not substitutes for the full-kernel build required by task 7.1.

The corrected HDMI DTB builds and decompiles. [DTB checks](fixed-dtb-check.json)
record its hash and graph/reset checks; [reproduction command](check-dtb.py)
checks reciprocal endpoints, one DSI output, no panel and touch ownership
of GPIO24/23. The corrected bundle also passes inspection. The default panel DTB builds
and decompiles with its panel present and no LT9611. The extracted common
controller body equals the original `94196f97` panel source except for the
touch label; this is a host regression check, not a new panel boot.

The continuation makes LT9611 wait for the I2C touch device to finish binding,
using the board-local `lontium,shared-reset-owner` phandle and a managed device
link. This prevents initialization before the shared reset and orders removal
and system suspend. The panel tree does not instantiate LT9611.

The separate `k230-mainline-drm-shell-hdmi` configuration enables the existing
relay and loads `uinput`; the HDMI boot bundle now selects that configuration.
The mainline DRM kernel enables `INPUT_UINPUT=m`. The complete corrected
kernel and bundle build now pass, including the
narrow `nix build .#kernelMainlineDrm` proof, bundle inspection and all 15
inspector fixtures; see [full host checks](fixed-host-checks.json) and
[matching bundle inspection](fixed-bundle-inspection.json). The matching fresh
boot and native captures are recorded below. Task 7.3
is now complete with the matching trial and operator acceptance recorded below.
The ordinary panel recovery below is serial proof; no physical panel taps
are inferred.

The inherited card-shell QEMU kernel build was stopped to prioritize HDMI
and retain one heavy build at a time in this session. Its task 5.1 remains
unproved; no QEMU pass or archive is claimed here.

## Matching corrected-bundle board trial

The host exported an 18-path, 175,871,264-byte NAR closure delta over the
private transfer link. [Staging report](fixed-stage.json) records immutable
bundle identity, transfer hashes and the resulting stage. Staging passed its
closure, artifact and protected-profile checks. Raw UART and transport details
remain private.

Before the corrected HDMI trial, the controller issued an ordinary `reboot`
and sent no U-Boot intervention. [Panel recovery](ordinary-panel-recovery.json)
records the original protected system, connected `DSI-1`, registered Goodix,
three active shell services and byte-identical boot files. The
[controller recipe](ordinary-panel-reboot.py) records its exact input checks.
This is serial recovery proof, not physical panel touch acceptance.

Corrected trial command, run under the controller's exclusive board lock:

```sh
python3 tools/coherent-shell-board-boot.py \
  --candidate ~/tmp/k230-hdmi-continue-private/hdmi-fixed-bundle \
  --state ~/tmp/k230-hdmi-continue-private/fixed-stage/state.json \
  --output ~/tmp/k230-hdmi-continue-private/fixed-trial
```

[Trial report](fixed-trial-boot.json) passes every loaded-file CRC and matches
running system
`/nix/store/yndjf2iz1q1r0dndsbx154yr47bycak8-nixos-system-nixos-26.11.20260919.20b1ddd`
and Image
`/nix/store/17mn8cyc2bls0yrphlhpcikn77f491kq-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/Image`.
The persistent profile remains the protected panel system. No manual I2C
recovery, connector force or custom modeline was required on this fresh boot.

[Live state](fixed-live-state.txt), first captured at `2026-10-09T06:35:39Z`
and repeated with a case-insensitive Goodix log filter, records:

- Goodix input registration at 2.570689 seconds, before LT9611 revision
  `0xe2` at 2.739239 seconds.
- Initial 1920-pixel video and DSI lane rate 891000 kbps, `hsfreqrange 0x96`.
- Automatic `connected` HDMI status, a 256-byte EDID and its mode list.
- Sway's selected EDID mode **1280×800 at 59.910 Hz**, transform 90,
  logical 800×1280. The corresponding later bridge check decodes 1280 pixels,
  lane rate 445500 kbps and `hsfreqrange 0x96`.
- Four active services: `shell`, `shell-ui`, `theme-helper` and the configured
  `k230-touch-trackpad`; `/dev/uinput` exists, the relay grabs event1 and Sway
  recognizes the enabled virtual touchpad.

The vertical counter still reports one extra active line (1081, then 801).
No hsfreqrange tuning was performed. The relay's grab, rather than Sway's
raw-touch send-events flag, routes physical Goodix events exclusively to it.

The first [native capture](fixed-native-terminal.png), at
`2026-10-09T06:36:46Z`, shows the terminal started by the existing unconditional
Sway `exec` and a rendered cursor. An attempted base64 UART copy failed
padding validation and is not accepted as image proof. The private HTTP copy
passed the board/host SHA256 comparison; see [capture metadata](fixed-native-terminal.json).

The compositor then received `swaymsg 'card_shell home'`. At
`2026-10-09T06:41:04Z`, [native Home capture](fixed-native-home.png) shows the
shell and cursor at 800×1280. [Home metadata](fixed-native-home.json) records
commands, timestamp, dimensions and the matched transfer hash. This is a
native capture following an injected Home command, not a physical tap test
or monitor photograph. No pointer movement/click was injected during this
corrected-bundle trial.

The operator was asked to confirm the fresh monitor picture, finger-driven
cursor movement and taps, then replied: "yeah hdmi works great it's perfect
continue lmk what you need". [Operator acceptance](operator-acceptance.json)
records the exact response and a read-only serial check confirming the same
running system, connected HDMI and all four active services. This accepts the
trial overall; it does not enumerate individual gestures, supply a photograph
or establish gesture latency. Task 7.3 is complete. Groups 3–5 and archive
remain open. The board is left on the corrected **volatile HDMI trial**; an
ordinary reboot retains the protected panel selection.

## Publishing follow-up

The source/evidence checkpoint landed at `6c8d31a6`. Its
[CI run](https://github.com/knewter/tdisplay-k230/actions/runs/37895411379)
passed the test steps but rejected four PNGs missing from the binary inventory;
Pages deployment was skipped. The continuation owns this failure. Exact
per-file DATA rows and hashes were added to `docs/blob-inventory.md`, and
`python3 tools/blob-scan.py --no-vendor` then passed. The
[follow-up report](ci-inventory-followup.json) preserves the failed revision,
log hash, correction and narrow validation. This bookkeeping correction does
not change the board's running artifacts or finish the physical touch gate.
