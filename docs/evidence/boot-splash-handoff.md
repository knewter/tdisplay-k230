# Splash handoff trial, 2026-09-22

The runtime U-Boot flag and conditional kernel path now preserve the stage-1
logo until Linux reaches its serial prompt, with the shell held back. The
first Sway modeset still produces incorrect physical geometry/colors. This
is partial progress; a usable splash-to-shell handoff is not verified.

The trial used the source-built daily image documented in
[daily-shell-image-3f397a6.md](daily-shell-image-3f397a6.md), including U-Boot
patch 0005 and the `c99a14f0q7wzfqplpzk223f79i7rjbp0` kernel. Only the
known logo asset and a temporary `systemd.mask=shell.service` boot argument
were installed. No flash or full readback was performed; no second card was
used. [Preparation](splash-handoff/prepare.txt) records the asset hash.

## Stage 1 to idle Linux

[100-second physical recording](splash-handoff/20260922T195817Z-splash-kernel-preservation.mp4),
[boot transcript](splash-handoff/boot.txt),
[serial inspection](splash-handoff/preservation.txt), and
[frame at 90 seconds](splash-handoff/preserved-at-linux-prompt.png).

The logo is still visible at the Linux prompt. `/chosen/canaan,stage1-splash`
is present, `/dev/fb0` is absent, and the kernel logs `stage 1 splash: leaving
fbdev unset`. Sway is masked. There is no panel prepare call at this stage;
the proposed expectation of a prepare-skip message before the first modeset
was incorrect. That message appears only when a DRM client actually starts.
USB is attached and the reboot is serial initiated, not a power-on or battery
trial. The video does not establish calibrated panel-motion statistics.

## First Sway modeset

[22-second physical recording](splash-handoff/20260922T200130Z-splash-to-shell.mp4),
[console](splash-handoff/first-modeset.txt),
[native screenshot](splash-handoff/first-shell-native.png), and
[physical frame at 18 seconds](splash-handoff/first-shell-physical.png).

A temporary copy of the image shell unit, named `shell-handoff`, starts Sway
with its normal configuration. The kernel logs `canaan_panel_prepare: left as
stage 1 set it`, while the PHY polls report `0x1529 != 0x1fbd`. The service is
active and the native screenshot has the correct control order. The physical
panel wraps System to the left and changes the bar/title colors. Preserving
reset and skipping panel initialization alone therefore does not fix the
handoff. Retained VO/DSI state is under investigation; no cause is established.

This tests the real compositor's first modeset, not the planned matching-logo
DRM buffer. No seamless-transition or dark-frame duration claim is made.

[Restore transcript](splash-handoff/restore.txt) puts back the original boot
arguments and removes the experimental logo before recovery. The temporary
unit is under `/run` and disappears at reboot. The daily image continues to
select `panelConsole=true` and omit the logo.

The [normal recovery boot](splash-handoff/normal-recovery-boot.txt) returned to
Linux; [inspection](splash-handoff/normal-recovery.txt) records active shell and
seatd with no drop-ins, no splash flag, `/dev/fb0` restored and no shell mask in
the command line. The [recovery photograph](splash-handoff/20260922T200502Z-normal-shell-recovered.jpg)
shows the correct control order and colors again.
