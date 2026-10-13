# Keyboard base LEDs and keyboard service (tasks 3.3, 4.1, 6.1; board-read)

Evidence class: **board-read** only. No camera was attached (`/dev/video0`
absent on the host), so nothing here shows that an LED is visibly lit.

## Installed system

The board ran system `q4nzfdkw…` (bundle
`.#kernelMainlineDrmShellLandscapeBootFiles` from `impl/keyboard-base`),
installed on 2026-10-13 ~23:30 UTC the same way as `../keys/README.md`. The
previous boot files are in `/var/lib/k230/boot-backup-20261013-pre-kbd3/`.

An earlier build in this series lacked `NEW_LEDS`/`LEDS_CLASS`, so
`LEDS_GPIO` was silently dropped and `/sys/class/leds` did not exist; the
kernel config now enables both.

## After boot

`/sys/class/leds` holds `k230:green:capslock`, `k230:status-1`,
`k230:status-2` and `k230::kbd_backlight`. The udev rule makes the
Caps Lock and backlight `brightness` files `root:shell 0664`.

`shell-keyboard-base.service` is active and logs
`reading /dev/input/event2`.

Writing `1` to the Caps Lock and backlight LEDs, then `0`, gave in
`/sys/kernel/debug/gpio`:

```
on:
 gpio-20  (                    |k230::kbd_backlight ) out hi
 gpio-3   (                    |k230:green:capslock ) out lo ACTIVE LOW
 gpio-4   (                    |k230:status-1       ) out hi ACTIVE LOW
 gpio-5   (                    |k230:status-2       ) out hi ACTIVE LOW
off:
 gpio-20  (                    |k230::kbd_backlight ) out lo
 gpio-3   (                    |k230:green:capslock ) out hi ACTIVE LOW
```

So the XL9555 P0.3 line goes low for Caps Lock on. LILYGO's own code
lights it that way (0xF7). IO52 goes high for the backlight.

## Limits

- **Visibility:** whether either LED lights is **UNVERIFIED**; task 4.1
  needs camera frames.
- **Backlight polarity:** IO52's active-high polarity is an assumption.
