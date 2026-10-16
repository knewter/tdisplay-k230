# Widgets respond across their whole area (HDMI, 1280x800)

Evidence class: **injected pointer + native grim capture**. Not an operator
observation and not a camera recording.

System: `/nix/store/kzcwv5rqml2s6fgy4c1fi6zw69jdirs9-nixos-system-nixos-26.11.20260919.20b1ddd`
(source 9b33d477), activated live with `switch-to-configuration test` at
about 19:58 CDT on 2026-10-15.

Before the fix, `tools/board-pointer.py 'hold 300 300 2500; up'` on the
Battery - Details widget produced only `pointer-down`/`pointer-up` in the shell
log, with no rearrange mode. At 1280x800, (300, 300) lies in the gap between
cell columns 1 and 2 (x 282.7-300.7) and between rows 0 and 1 (y 286-304).

After the fix, `hold 300 300 900; up` landed on page 1, inside the Clock
widget's area and in the same gaps, because the scripted swipe to page 2 ran
before the restarted shell was ready. Rearrange mode opened:
`long-press-in-clock-gap-1280x800-grim.png` shows Remove, Done and the icons'
remove badges. Done was then clicked.

Limit: shown on the Clock widget, not on the Battery - Details widget. The host
regression test covers the Battery - Details case.
