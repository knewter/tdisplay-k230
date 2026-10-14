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

## Shortcut recording (2026-10-14 01:12–01:17 UTC)

`shortcuts-evemu-record-2026-10-14T0112Z.txt` is `evemu-record` on the real
`tca8418` device while the operator pressed LILYGO+Tab five times and was asked
for Fn+LILYGO; `shortcuts-sway-bindings-2026-10-14T0112Z.json` is
`swaymsg -t subscribe -m '["binding"]'` over the same window (**board-read**).

- Presses 1–3: Tab arrived with only LILYGO held (Shift, if any, in the same
  report after it), and `card_shell enter` fired three times.
- Presses 4–5: Shift arrived 23 ms and 46 ms before Tab, so the modifiers were
  Super+Shift and no binding matched.
- No `KEY_RIGHTALT` (Fn) event appears anywhere in the recording.

## Why the overview chord leaked Tab (2026-10-14 ~02:10 UTC, **injected**)

After the Super+Shift+Tab binding landed, the operator reported that LILYGO+Tab
opened the overview but also sent Tab to the terminal. Reproduced with an
`evemu-device` clone of the `tca8418` keypad (same `1:1:tca8418` identifier),
with foot focused, by rebinding Mod4+Tab at runtime with `swaymsg`:

| Binding | Terminal after LILYGO+Tab |
| --- | --- |
| `bindsym --input-device=1:1:tca8418 Mod4+Tab nop` | received `CSI 27;9;9~` (Super+Tab) |
| `bindsym --input-device=1:1:tca8418 Mod4+Tab exec true` | received `CSI 27;9;9~` |
| `bindsym Mod4+Tab nop` (no `--input-device`) | nothing |
| `bindsym Mod4+Tab card_shell enter` and `Mod4+Shift+Tab card_shell enter` | overview opened; nothing |

So Sway ran the `--input-device` binding and still delivered the key. The
chord bindings are now global; the operator's earlier presses had left five
`;10;9~` (Super+Shift+Tab) and one `;9;9~` in the terminal.

## Fn and the fixed overview chord (2026-10-14 ~02:40 UTC)

`fn-evemu-record-2026-10-14T0237Z.txt` and `fn-sway-bindings-2026-10-14T0237Z.json`
(**board-read**, real keypad, operator presses): Fn alone three times arrives
as `KEY_RIGHTALT` press/release; Fn held with Up gives `KEY_UP` inside the
`KEY_RIGHTALT` press; one LILYGO+Tab gives a single `card_shell enter` binding
event with the global bindings. Whether the terminal stayed clean after this
real press is not recorded; the injected check above showed nothing reached it.
