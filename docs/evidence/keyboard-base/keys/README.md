# Keyboard base keys (task 3.4, partial)

## Installed system

The board ran `impl/keyboard-base` at `f8c0d5e4`'s tree:

- Bundle: `.#kernelMainlineDrmShellLandscapeBootFiles`, system `4g5whg4y…`.
- Install: copied with `nix copy` over SSH. The four boot files were staged
  in `/var/lib/k230/boot-staging-kbd`, hash-checked against the bundle's
  `SHA256SUMS`, and copied into `/boot`.
- Profile: set to the new system, then rebooted.
- Previous boot files: `/var/lib/k230/boot-backup-20261013-pre-kbd/`.

## Board-read after boot (2026-10-13 ~21:10 UTC)

`dmesg`:

```
tca8418_keypad 1-0034: overflow occurred
input: tca8418 as /devices/platform/soc/91409000.i2c/i2c-1/1-0034/input/input2
```

The single overflow at probe is the chip's event FIFO left full while
LILYGO's firmware last ran. The driver drains it.

`/proc/interrupts` shows `gpio-k230 10 Level tca8418` (IO42).

`swaymsg -t get_inputs` lists `1:1:tca8418`, a keyboard, with repeat
400/25 from the `nix/shell.nix` stanza. Sway's log says "Translated keysyms
using config for device '1:1:tca8418'" and reports no keymap error.

## Operator

- `evtest-2026-10-13T211125Z.log`: `evtest /dev/input/event2` for 300 s
  from 21:11:25 UTC. It holds 8 presses, `KEY_G` and `KEY_BACKSPACE` (DEL)
  4 each, from the operator at the keys (**board-read**, operator pressing).
- **Operator report** (2026-10-13, chat): "works great" after typing on the
  base.

## Still required for task 3.4

These are not covered by this evidence:

- `evtest` for every key;
- `ls -la` in foot, as a native `grim` capture and a camera frame;
- a Shift-punctuation line;
- Caps Lock with its LED, which needs task 3.3.
