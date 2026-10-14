# Dimmable key backlight on PWM4 (task 4.2)

Installed system `/nix/store/5dchd37z…-nixos-system-nixos-26.11.20260919.20b1ddd`
(`.#kernelMainlineDrmShellLandscapeBootFiles` from `impl/kbd-pwm-backlight`),
booted 2026-10-14 11:09 CDT on the second board in its keyboard case.

## Board-read

```
$ dmesg | grep pwm
[    2.499143] k230-pwm 9140a040.pwm: 100000000 Hz
$ cat /sys/class/leds/k230::kbd_backlight/max_brightness
255
$ grep "pin 52" /sys/kernel/debug/pinctrl/*/pinmux-pins
pin 52 (IO52): device keyboard-base-backlight function kbd-backlight-pins group kbd-backlight-cfg
```

PWM registers (`devmem`) after writing each brightness. 0x9140a040 is PWMCFG,
0x9140a060 is pwmcmp0 (the period), and 0x9140a068 is pwmcmp2 (channel 1, PWM4):

```
b=255 cfg=0xE0001200 cmp0=0x00001387 cmp2=0x00000000
b=128 cfg=0xA0001200 cmp0=0x00001387 cmp2=0x000009BB
b=32  cfg=0xA0001200 cmp0=0x00001387 cmp2=0x00001115
b=4   cfg=0xA0001200 cmp0=0x00001387 cmp2=0x0000133A
b=0   cfg=0xA0001200 cmp0=0x00001387 cmp2=0x00001388
```

The period is 5000 ticks of the 100 MHz clock (50 µs, 20 kHz). The compare
value is the period minus the on-time, so 0 is always on and 5000 is never on.
The top bits of PWMCFG are the block's interrupt-pending flags.

## Operator (camera waived)

With `shell-keyboard-base.service` stopped, a loop wrote 255, 128, 32, 4 and 0,
four seconds each, for six rounds. It ran twice. Operator, 2026-10-14: "it dims
fine, off is dark". This confirms the NORMAL-polarity reading of the
comparator in `nix/patches/mainline/pwm-k230.c`: the output is high while the
counter is >= pwmcmpN.

## Settings slider, live (board, 2026-10-14)

Settings stores the Key backlight level at each slider detent, and
`keyboard_based.py` polls the file every 0.2 s and lights the keys at a new
level for a 3 s preview. Board read, preference written over SSH, LED
brightness read 0.5 s after each write:

```
pref=medium led=0
low -> 20
medium -> 76
high -> 255
after preview -> 0
```

Operator, 2026-10-14, dragging the slider on the glass: "works live now".

`settings-slider-board-grim.png` is a native grim capture of the landscape
Settings page at 2026-10-14T14:27:03-05:00, the slider at High with its four
detents.
