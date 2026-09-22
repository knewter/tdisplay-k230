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
DSI timing values. Later repeated control reads found both address-selection values during a
correctly rendered session (see the phase diagnostic below). The single-pair
difference does not establish a cause of the physical defect; the probe samples
only a subset of registers, and no corrective write was attempted.

The [restoration transcript](splash-handoff/register-restore.txt) restores the
original boot arguments and removes the logo before the
[recovery reboot](splash-handoff/register-recovery-boot.txt).

[Recovery inspection](splash-handoff/register-recovery.txt) confirms the original
command line without `iomem=relaxed`, no logo or splash flag, `/dev/fb0` present,
and active shell and seatd services.

### Address-select source audit and next diagnostic

The pinned Linux `drivers/gpu/drm/canaan/canaan_vo.c` writes `0x100` directly
to `VO_OSD0_7_ADDR_SEL_MODE_REG_OFFSET` in `canaan_vo_update_osd()`. The
U-Boot RM69A10 path in `0004-rm69a10-logo-port.patch` writes `0x1100` to its
same OSD4 register. Neither the pinned Linux `canaan_vo_regs.h` nor the
vendor U-Boot `display_logo.h` defines individual bits for that register, so
the source does not establish whether bit 12 is writable mode state, a latch,
or a readback/status bit. The earlier research's description of the value as
flip-related reports a LILYGO change; it is not a hardware-register semantic.

The missing-logo path gives no U-Boot explanation for the normal snapshot's
`0x1100`: `_k230_display_logo_load_pic()` returns before display power or
`st7701_init()` when `/logo.xrgb` is absent, so it cannot write the OSD4
register. That leaves a reset/default or unobserved Linux/hardware transition.
No corrective register write is justified from these snapshots alone.

`tools/vo-registers.c` now reads the complete named OSD4 buffer block,
`VO_OSD4_BD_CTL`, DMA setup, mix/alpha/background/dither/CLUT, and the two
global conversion controls. It remains read-only. Collect it at the retained
stage-1 frame, immediately after the first Linux atomic commit, and steady
Sway to distinguish a hardware/latch transition from a software writer.


## Separate retained-logo, Linux-owner and compositor phases

The 2026-09-22 follow-up uses the verified daily image from
[daily-shell-image.md](daily-shell-image.md), source image commit `7a83afa`,
system `n5lqa24jxmlw5sn1q89y58js3ag7p859`. It adds only temporary boot arguments
`iomem=relaxed systemd.mask=shell.service`, the known immutable logo copied to
`/boot/logo.xrgb`, and read-only/runtime diagnostic tools. No flash, kernel
replacement, home restoration, or MMIO write probe was involved.

The extended read-only probe is
`/nix/store/a3mf5xjpvxyg6imsjycgpaznz74d1gzc-k230-vo-registers-riscv64-unknown-linux-gnu-0.1/bin/vo-registers`.
The [control snapshot](splash-phases/control-registers.txt) and
[four repeated reads](splash-phases/control-repeat.txt) establish that
`VO_OSD4_ADDR_SEL_MODE` changes between `0x100` and `0x1100` during normal,
correct display operation with the same framebuffer address. This invalidates
the earlier single-pair address-mode hypothesis; no forced register write is
justified.

The [retained U-Boot frame snapshot](splash-phases/retained-logo-registers.txt)
and [first Linux owner commit](splash-phases/owner-registers.txt) show:

| Register group | Retained stage 1 | Linux RG16 owner |
| --- | --- | --- |
| VO and OSD4 Y window | `04df0010` | `04e00011` |
| RGB-to-YUV / YUV-to-RGB | `0` / `0` | `00010101` / `1` |
| OSD4 format / stride | `3` / `11c` | `2` / `8e` |
| OSD4 DMA | `40` | `4f` |
| Buffer addresses | all `10000000` | all `1e300000` |
| Sampled DSI video timing | identical | identical |

The first Linux commit still logs two PHY status timeouts (`1529 != 1fbd`),
then reports successful RG16 framebuffer 49 scanout. These samples cannot
establish internal panel state or the cause of a visual defect.

The diagnostic owner uses the repository's unchanged `drm-splash.c`, built
with only `DEFAULT_ASSET=/tmp/logo.xrgb` to make the same source logo available
on the daily image. Its output is
`/nix/store/hk73za1q6bc327lv4zx4d524xxxrq2s0-k230-drm-splash-riscv64-unknown-linux-gnu-0.1`.
The [25-second first-owner recording](splash-phases/20260922T205934Z-logo-to-drm-owner.mp4)
shows the logo, but camera startup raced the serial start; it is not proof of
uninterrupted first-modeset continuity.

The subsequent [owner-to-Sway recording](splash-phases/20260922T210027Z-drm-owner-to-sway.mp4)
starts four seconds before the serial handoff command. The
[console and registers](splash-phases/sway-registers.txt) show the owner dropping
DRM master, retaining framebuffer 49, detecting its replacement, and exiting.
The physical panel shows Apps, Windows, Keyboard, System in the same order and
colors as the [native screenshot](splash-phases/sway-native.png). The earlier
direct-to-Sway wrapped-control defect is absent in this trial. This is a
manually staged warm-boot diagnostic, not yet an automatic image-service or
power-on handoff proof.

Source reinspection also corrects the original design's first-enable reset
claim: in the pinned prepared `drivers/gpu/drm/canaan/canaan_vo.c`,
`canaan_vo_enable_crtc()` initializes VO and timing without calling
`k230_display_rst()`. The explicit block reset is in `canaan_vo_disable_crtc()`.
The `drm_atomic_helper_commit_tail_rpm` path enables modesets before updating
planes; DSI/PHY reprogramming still occurs during encoder enable. A bypass of
that initialization is not justified by the successful staged-owner trial.


### Controlled repeat: the geometry fault is intermittent

A [second warm boot](splash-phases/repeat-boot.txt) repeated the same owner and
Sway commands with the camera given four seconds to start. The
[40-second recording](splash-phases/20260922T210255Z-retained-logo-owner-sway-repeat.mp4)
shows a correct retained logo initially, a wrapped logo after the first Linux
owner modeset, and a wrapped/color-shifted Sway display. Extracted frames show
[retained stage 1 at 0.5 seconds](splash-phases/repeat-retained-logo.jpg),
[Linux owner at 10 seconds](splash-phases/repeat-owner.jpg), and
[Sway at 35 seconds](splash-phases/repeat-sway.jpg). Compare the earlier
[correct physical Sway frame](splash-phases/sway-first-physical.jpg).
The camera has glare and an oblique angle; it clearly distinguishes these
large geometry changes but does not establish calibrated color accuracy.

The [repeat console](splash-phases/repeat-registers.txt) reports successful
owner scanout and successor replacement, while the
[native screenshot](splash-phases/repeat-sway-native.png) is correct.
Software success and a correct compositor buffer therefore do not prove
correct physical scanout. The owner route is **not a fix**: first-mode takeover
can succeed or fail without a source/image change. No seamless-handoff task is
closed and no dark-frame-duration claim is made.

The daily boot arguments were [restored](splash-phases/restore.txt) and the
temporary logo removed. The experimental service copy exists only under
`/run` and disappears on reboot. The next diagnostic is a source-isolated,
first-enable preservation trial; it is not part of the daily image.


The [recovery boot](splash-phases/recovery-boot.txt),
[inspection](splash-phases/recovery.txt), and
[physical frame](splash-phases/20260922T210603Z-phase-normal-recovery.jpg)
confirm the restored normal configuration: no diagnostic arguments, no logo or
splash flag, `/dev/fb0` present, and shell, seatd and firewall active.

## First-enable preservation image trial

The [diagnostic image trial](splash-preserve-trial/README.md) records three
correctly arranged automatic shell boots, visible successive color updates,
and the same-kernel missing-logo console fallback. It also records a measured
approximately 1.1–1.2 second camera-visible dark gap before Sway content.
The candidate remains separate from the daily default; seamless handoff is
not proved.

## Initial compositor scene candidate

The [first scene trial](splash-initial-scene-trial/README.md) removed the
previous long dark interval from the sampled transition but failed to retire
its logo node because it expected the wrong bar layer. The
[corrected candidate](splash-initial-scene-ready/README.md) uses the actual
mapped Swaybar panel, records both seed and removal, and again shows no dark
frame in the dense warm-boot transition samples. The carried kernel and
optional compositor build successfully; the daily defaults remain the console
and ordinary Sway. This is progress toward the power-on handoff requirement,
not its final acceptance or a claim of uninterrupted animation.

The [keyboard visibility follow-up](splash-initial-scene-ready/keyboard-visibility-audit.md)
completes the candidate's filmed keyboard show/hide regression at a farther
camera focus, without claiming finger accuracy or complete label readability.
The [U-Boot motion measurement attempt](splash-uboot-motion/README.md) was
rejected by the existing registration tool because only two markers were
usable. No calibrated motion figure or task 3.7 completion is claimed.
