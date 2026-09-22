# Controlled first Linux modeset after stage-1 preservation

This trial separates the idle Linux kernel, the first Linux logo owner, and
Sway on the current exact-mode preservation image. It is a serial-initiated
warm boot on the existing card, not the second-card or power-on procedure.

## Image and setup

The image remains the corrected initial-scene candidate from source `12c1b0e`,
whose code was integrated in `61dcc90`. Its full image hash and derivation are
in [initial-scene build provenance](../splash-initial-scene-ready/build.txt).
The running system is
`/nix/store/24h4sb1msncgbasnwl3ckdlxqf9v2g6r-nixos-system-nixos-26.11.20260919.20b1ddd`.
No source changed, no image was flashed, and no home state was restored.

[Preparation](prepare.txt) temporarily adds
`systemd.mask=shell.service systemd.mask=k230-drm-splash.service` to the boot
arguments. [Idle boot capture](idle-boot.txt) and
[idle inspection](idle-inspection.txt) establish:

- The runtime splash flag is present and `/dev/fb0` is absent.
- Both display services are inactive; seatd and firewall are active.
- The DRM debugfs client table contains its header and no clients.
- The kernel logs `stage 1 splash: leaving fbdev unset`, with no panel prepare
  or VO/DSI first-enable message yet.
- The [idle physical photograph](20260922T225553Z-first-modeset-idle-logo.jpg)
  shows the retained K230 logo at the serial prompt.

This supplies the display-behavior evidence for task 4.3; its specified
second-card prerequisite is still outstanding, so that task remains open.

## Why the test uses the immutable logo owner

The installed `modetest -h` output in `idle-inspection.txt` offers built-in
`-F` patterns and a writeback output file, but no input image. It cannot scan
out a supplied copy of the U-Boot logo. The corrected same-image procedure
uses the existing unchanged `nix/drm-splash/drm-splash.c`: `read_asset()`
validates the immutable 2,799,104-byte B,G,R,X asset; `fill_buffer()` converts
it to RG16; primary-plane format discovery checks support; and the first
`drmModeSetCrtc()` displays that buffer. The unit's immutable executable is
`/nix/store/qkvxyd8cajqsz2ablbngzxnzsn4a62cn-k230-drm-splash-riscv64-unknown-linux-gnu-0.1/bin/k230-drm-splash`.

The [capture script](capture.py.txt) copies the built owner and shell units to
alternate names under `/run/systemd/system/`. This allows deliberate startup
while leaving the original command-line masks in place. It starts
`first-modeset-owner`, then signals it to drop master and starts
`first-modeset-shell`. No persistent unit override is installed.

## First owner and successor

The [65-second physical recording](20260922T225553Z-preserved-first-owner-to-sway.mp4)
starts four seconds before the first owner command. The
[camera audit](video-audit.md) records the visible transitions and limits.
The [Sway inspection](sway-inspection.txt) includes the owner journal:
framebuffer 49, connector 48, CRTC 46, RG16; master dropped while retaining
that buffer; successor replacement; successful owner exit. It also records
Sway's initial scene seed and removal at replacement commit sequence 7.
The [native screenshot](sway-native.png) is a separate compositor-layout aid.

The completed audit reviews every captured frame from 2–16 seconds around
the first owner start (420 frames at 30 fps): the logo remains visible in
all of them. All 18 frames from 22.45–23.05 seconds cover the shell transition;
the last logo-only frame is approximately 22.82 seconds and the first shell
bar approximately 22.85 seconds. The observed dark interval is zero captured
frames. This satisfies task 4.4's filmed first-modeset check without triggering
its dark-interval fallback; it does not rule out a sub-frame interruption.

`owner-inspection.txt` contains only the submitted command: its console
capture window ended before the response. It is not evidence that those
queries returned. The later journal captures provide the missing output.
[Previous-boot kernel journal](previous-kernel.txt) identifies controlled
boot `581861b66ba74a00ad7d227226e3e99b`, matching `idle-boot.txt`, and records
first VO preservation, the panel's one-shot prepare skip, and first DSI
preservation at the manual owner start. No full prepare or PHY timeout line
appears in that filtered kernel journal. This is software-path evidence,
not an electrical measurement of DCS traffic.

## Recovery

The [boot-argument restoration](bootargs-restored.txt) restores and compares
the original file before the display experiment. Its SHA-256 is
`90d0b406f88fe6cba2b175569f2a4402c5fe46e4e5db9549cb50cf7eb24a703e`.
[Recovery boot](recovery-boot.txt), [inspection](recovery-inspection.txt), and
[physical shell photograph](20260922T230013Z-first-modeset-recovery-shell.jpg)
record normal automatic startup again: no mask arguments, original units
loaded, runtime test units gone, shell/seatd/firewall active, owner replacement
and Sway seed/removal logged. The logo remains the immutable image asset.

This trial does not establish battery-only operation, real-finger input,
calibrated motion/geometry, or task 5.4's complete power-on continuity.
