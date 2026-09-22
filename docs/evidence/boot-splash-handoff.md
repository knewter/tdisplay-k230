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

## Read-only register diagnostic

`tools/vo-registers.c`, built with `nix/vo-registers.nix`, snapshots only named
VO/DSI registers from the pinned register headers and device-tree addresses.
It contains no write path. The target build used the same flake's cross pkgs:

```
nix build --impure --expr 'let f = builtins.getFlake "<absolute-worktree>"; in f.nixosConfigurations.k230.pkgs.callPackage ./nix/vo-registers.nix {}' --option max-jobs 1 --option cores 1
```

The helper compiled with `-Wall -Wextra -Werror`, was transferred with hash
verification, and was run on the no-logo control boot. The running kernel
[refused its mmap with Operation not permitted](splash-handoff/normal-vo-registers.txt).
A preceding [read attempt through dd](splash-handoff/devmem-read-failed.txt)
returned Bad address. Neither transcript contains successful register values.
Comparison of actual normal/splash register state remains unverified; the
probe failure is not evidence that a particular register caused the defect.


### Successful comparison with temporary diagnostic boot arguments

The kernel permitted the same read-only probe after temporarily adding
`iomem=relaxed`. This is a diagnostic boot setting, not an image default.
The [control preparation](splash-handoff/register-control-prepare.txt),
[control boot](splash-handoff/register-control-boot.txt), and
[normal snapshot](splash-handoff/normal-vo-registers-relaxed.txt) record the
no-logo boot. The [logo preparation](splash-handoff/register-logo-prepare.txt),
[logo boot](splash-handoff/register-logo-boot.txt), and
[logo snapshot](splash-handoff/logo-vo-registers-relaxed.txt) record the same
image with the known logo installed and Sway running.

All sampled registers match except the framebuffer address and
`VO_OSD4_ADDR_SEL_MODE` at VO offset `0x8a0`: the normal boot reads `0x1100`,
while the logo boot reads `0x0100`. The framebuffer addresses are `0x1e300000`
and `0x1e200000`, respectively, and can vary with allocation. Both snapshots
have RGB565 format `2`, stride `0x8e`, DMA control `0x4f`, and identical sampled
DSI timing values. This narrows the investigation but does not establish that
the address-selection difference causes the physical defect; the probe samples
only a subset of registers, and no corrective write was attempted.

The [restoration transcript](splash-handoff/register-restore.txt) restores the
original boot arguments and removes the logo before the
[recovery reboot](splash-handoff/register-recovery-boot.txt).

[Recovery inspection](splash-handoff/register-recovery.txt) confirms the original
command line without `iomem=relaxed`, no logo or splash flag, `/dev/fb0` present,
and active shell and seatd services.
