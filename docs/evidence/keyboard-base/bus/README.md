# Keyboard-base bus on the installed device tree (task 2.2; board-read)

The device tree carries the pinctrl states for IO42, IO43, IO46, IO47 and IO52,
and hardware I2C4 at `0x91409000` (task 2.1). It went onto the board as part of
the landscape boot bundles (`deploy-bundle.sh`, which copies the bundle's DTB to
`/boot/k230-tdisplay.dtb`), not with `tools/push-file.py`. The board has been
running it since 2026-10-13. Host proof for 2.1: `nix build
.#deviceTreeMainlineDrm` built
`/nix/store/y4j8bwc0…-k230-tdisplay-mainline-drm.dtb` on 2026-10-14.

Board read, 2026-10-14T09:48:35-05:00, kernel `7.3.0-rc5`, over SSH:

```
$ sha256sum /boot/k230-tdisplay.dtb
f108555a2d2040216e6c2a9f631f319c1edab7826c9600156db688023deb557f  /boot/k230-tdisplay.dtb
$ systemctl list-units "serial-getty@*" --no-legend
  serial-getty@ttyS0.service loaded active running Serial Getty on ttyS0
$ cat /sys/class/drm/card0-DSI-1/status
connected
$ grep -E "goodix|tca8418" /proc/interrupts
  86:       2471  gpio-k230     23 Level     goodix-berlin
  88:         20  gpio-k230     10 Level     tca8418
$ i2cdetect -y -r 1        # i2c-1 is the base's I2C4 adapter
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: UU -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- UU -- -- -- 38 -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- UU -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- UU -- -- -- --
70: -- -- -- -- -- -- -- --
```

Every address from probe 1.2 answers. `UU` marks an address whose driver is
bound: 0x20 XL9555, 0x34 TCA8418, 0x55 BQ27220 gauge, 0x6b BQ25896 charger.
0x38 (LILYGO's AHT20) answers with no driver. The serial getty is running. On
the glass, the operator has used the panel and touch on this device tree
throughout 2026-10-13/14 (landscape 8.6). This read did not log in on
`/dev/ttyACM0` itself; it shows the getty is active.
