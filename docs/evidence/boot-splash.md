# First physical U-Boot splash trial

On 2026-09-22, the source-built U-Boot displayed the K230 asset on the
physical panel while stopped at `K230#`, before any Linux load. This proves
stage-1 rendering. It does not prove a seamless Linux handoff.

## Artifacts and scope

- [Photograph extracted at video t=25 s](splash-trial/uboot-held-25s.jpg).
- [Raw 40 s camera recording](splash-trial/20260922T183200Z-uboot-splash-first-trial.mp4)
  and [capture metadata](splash-trial/20260922T183200Z-uboot-splash-first-trial.json).
- [Serial transcript held at U-Boot](splash-trial/uboot-held.txt) and
  [host scheduling timestamps](splash-trial/serial-timing.txt).
- [Subsequent Linux boot](splash-trial/linux-after-splash.txt),
  [late shell checks](splash-trial/linux-after-splash-late.txt), and
  [transition recording](splash-trial/20260922T183316Z-splash-to-linux-first-trial.mp4).
- [Guarded installer](splash-install-trial.sh) and
  [verified readback](splash-install-trial.txt).
- [USB host and UMS regression test](splash-trial/usb-coexist.txt): PASS before
  and after UMS, expected exported card, candidate bytes read back, Linux
  login reached, helper exit status 0. This tests enumeration and recovery,
  not Ethernet packet connectivity.

The trial replaced the U-Boot slot, DTB and logo on the identified running
card. It did not flash a second card or either full-image console variant;
OpenSpec task 3.6 remains unchecked because its prescribed second-card
procedure has not been completed. SPL, environments, OpenSBI, kernel and
rootfs were retained. The previous full U-Boot slot and DTB were backed up
on the board and verified before writing. The host also retains the complete
GC-rooted USB/portrait recovery image documented in
[recovery-usb-portrait-build.txt](recovery-usb-portrait-build.txt).

The trial used the built **0001–0004** U-Boot patch series from source
`cc3c37c`; the later runtime handoff flag patch 0005 was not in this binary.

| input | SHA-256 |
| --- | --- |
| packaged U-Boot, 385766 bytes | `fc59edb7057bd3ec7b6cda045bbad1545fb31a7bc19ade6cd8e7063e19f76d16` |
| complete 1 MiB slot after write | `f0c68fed7a6eec61576f8c8f7586a80b1aa4cf5326a56057ae12d8859110edfe` |
| logo, 2799104 bytes | `6c7a36086297597b359657ab53925ee0725e5201461484d543cbd950f5baa3af` |
| reserved-memory DTB | `ea95214b4bb8760f0de35c7d4126d0c98b2f9355284f7cae54812febdeb4fdb7` |

## What the board showed

U-Boot read exactly 2799104 bytes, printed
`RM69A10 direct XRGB8888 logo.xrgb full-screen OSD4`, and stopped at its
prompt. The t=25 s frame clearly shows K230. No `Starting kernel` occurs in
that held transcript; Linux was launched in the separate subsequent capture.
This is a serial-initiated warm reboot, not a battery-only cold boot or a
physical-touch test. The photograph is rotated 180 degrees for presentation;
the original camera video is retained unchanged.

Linux recorded the new `0x10000000..0x103fffff` 4096 KiB no-map reservation
and the same 512 MiB CMA allocation at `0x1e000000`. The existing shell service
returned active with one online CPU. The late command used `rg`, which is
absent on the board; its final filtering command failed. The reservation and
CMA claims come from the full boot transcript, not that failed command.

## Handoff defect remains open

The [native compositor screenshot](splash-trial/linux-native.png) shows the
expected Apps, Windows, Keyboard, System row and blue title strip. The
[physical panel after the splash](splash-trial/20260922T183432Z-shell-after-splash.jpg)
shows a horizontally wrapped row and changed colors. The first recording's
pre-reboot frames show the correct shell on the same camera, so this is a
real trial regression to investigate, not a successful clean handoff.

Possible retained VO/DSI state is a hypothesis, not an established cause.
The current kernel has no runtime splash-preservation changes. A comparison
boot with the logo renamed out of the loader's path is recorded in
[without-logo-boot.txt](splash-trial/without-logo-boot.txt). Leave splash
handoff tasks open until the physical presentation is corrected and measured.
No ArUco stability measurement was made in this trial.

The no-logo control boot reached Linux and the
[physical comparison photograph](splash-trial/20260922T184003Z-shell-without-logo.jpg)
shows the correct Apps, Windows, Keyboard, System order and blue title strip
again. U-Boot explicitly logged `logo.xrgb unavailable or unsafe, skip U-Boot
logo`. Only the logo was disabled; the new U-Boot and reserved-memory DTB
remained. The board is left with the asset saved as
`/boot/logo.xrgb.disabled-first-trial` until the handoff defect is resolved.

## Presentation clips and approximate timeline

[Rotated U-Boot clip](splash-trial/uboot-splash-held-rotated.mp4) and
[rotated Linux transition clip](splash-trial/splash-to-linux-rotated.mp4)
are 960x540 H.264/yuv420p exports with faststart. The originals above retain
full camera resolution and orientation. These are feature evidence assets,
not a claim that the continuous-splash feature is ready to ship.

Numerically ordered samples show the previous shell at t=0–6 s, shutdown text
at 8–10 s, a dark panel at 12 s and the K230 logo by 15 s, still visible at
39 s in the first clip. The separate transition clip shows the logo at
0–10 s and boot text by about 12 s. It ends before the shell appears; the
later still records the shell. These are coarse video-relative observations,
not power-on latency or calibrated refresh measurements. Camera glare and
focus limit readability. See the [U-Boot timeline](splash-trial/timeline-uboot.jpg)
and [Linux timeline](splash-trial/timeline-linux.jpg).

The board configuration now explicitly sets `k230.panelConsole = true` so
subsequent daily shell images omit `logo.xrgb`. This carries the observed
no-logo workaround into reproducible image builds. The splash package and
runtime handoff work remain available for an explicit experimental build;
changing the default back requires physical handoff evidence.
