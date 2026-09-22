# What this project carries on top of the pinned kernel

Required by the `system/kernel` requirement: *"every patch this project
carries on top SHALL be recorded with what it does and why it is needed"*, and
*"so a later kernel bump can tell whether it is still required"*.

**Pin:** `ruyisdk/linux-xuantie-kernel` at
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529` (6.6.36), `k230_defconfig`. This is
the revision and defconfig `k230_canmv_v3_defconfig` builds in
`kendryte/k230_linux_sdk`. Why not mainline: `docs/evidence/why-xuantie-kernel.txt`.

Everything below lives in `nix/kernel.nix`. All of it is applied through
`applyPatches` on `src`, **not** through the derivation's `postPatch` —
`buildLinux` does not forward `postPatch`, so setting it there is a silent
no-op that returns the same store path with none of the changes applied. That
cost a debugging cycle and was only caught because the derivation hash did not
change.

## 1. Three device trees the vendor Makefile omits

| Added to `arch/riscv/boot/dts/canaan/Makefile` | Why |
| --- | --- |
| `k230-canmv-v3.dtb` | The reference board's DTB. The vendor Makefile genuinely does not list it, so the tree cannot build the board its own defconfig is named after. |
| `k230-canmv-v3-lcd.dtb` | The reference board's LCD variant, kept as the comparison point for our divergence record. |

**Drop when:** upstream lists them itself.

`k230-tdisplay.dtb` used to be a third row here. It is not built by the
kernel any more — see below.

## 2. This board's device tree — NO LONGER IN THE KERNEL

`nix/dts/k230-tdisplay.dts` and `nix/dts/display-rm69a10-568x1232.dtsi` were
copied into `arch/riscv/boot/dts/canaan/` from `applyPatches`' `postPatch`,
which put them in the kernel's `src`. Correct, and very slow: a one-byte edit
to `panel-init-sequence` — the thing actively being iterated on to bring the
panel up — invalidated the whole kernel and cost a ~20 minute cross-compile.

A DTB needs the kernel's *headers*, not a built kernel. So the pin moved to
`nix/kernel-src.nix` and the DTS is preprocessed and compiled on its own in
`nix/device-tree.nix`, exposed as `nix build --impure .#deviceTree`. That
takes about 1.5 seconds, and `nix/sd-image.nix` takes the DTB from there
instead of from `${kernel}/dtbs/canaan/`.

The output is **byte-identical** to what the kernel build produced: same
preprocessor flags as `scripts/Makefile.lib`'s `cmd_dtc`, plus the `-@` that
nixpkgs' kernel builder adds to every `make dtbs`
(`pkgs/os-specific/linux/kernel/build.nix`). Verified by `cmp` against
`${kernel}/dtbs/canaan/k230-tdisplay.dtb` from the previous build.

Configuration rather than a code patch: `panel-canaan-universal` is already in
the pinned tree and is driven entirely from the device tree, so the RM69A10 is
described rather than coded. Divergences from the `k230-canmv-v3-lcd`
reference — which describes a different panel, an ST7701 at 480x800 — are
recorded in `docs/evidence/dts-divergence.md`.

**Drop when:** never, unless the board is upstreamed.

## 3. `goodix_berlin`, backported from v6.12

Source in `nix/patches/goodix-berlin/`, copied into
`drivers/input/touchscreen/`, with a Kconfig and Makefile stanza appended.

The pinned 6.6 tree has only the older GT9xx `goodix.c`, which does not speak
the Berlin protocol at all. **This driver does not match the GT9895 upstream
either** — see `gt9895-touch.md`; mainline has no GT9895 support at any
version. The device tree therefore declares `"goodix,gt9895", "goodix,gt9916"`
so the backport can attach via the fallback. Whether a GT9895 answers the
Berlin protocol is an open experiment, not an established fact.

One edit to the backported source:

```
sed -i 's|#include <linux/unaligned.h>|#include <asm/unaligned.h>|'
```

v6.12 moved `asm/unaligned.h` to `linux/unaligned.h`; 6.6 predates the move.

**Drop when:** the pinned kernel reaches a version that carries
`goodix_berlin` itself (v6.12+). The `unaligned.h` sed drops at the same time.
If the experiment fails, this whole item is replaced by a port of LilyGO's
RT-Smart `gt9895.c` instead.

## 4. `autoModules = false`

Not a patch, but it changes what is built and belongs in this record.

nixpkgs defaults `autoModules` to true, which enables every module it can on
top of the defconfig. Against a vendor tree that is actively harmful: it turns
on drivers the vendor never compiles and whose bugs have therefore never been
hit. The first build died in `drivers/rpmsg/th1520_rpmsg.c` with `redefinition
of init_module` — a driver for the **TH1520**, an unrelated SoC that
`k230_defconfig` does not enable. Greybus was compiling too.

`RPMSG_TH1520` is additionally forced off with `lib.mkForce no`.

**Drop when:** never, while building against a vendor tree.

## 5. Config that NixOS needs and a vendor defconfig does not set

`DEVTMPFS`, `DEVTMPFS_MOUNT`, `CGROUPS`, `INOTIFY_USER`, `SIGNALFD`,
`TIMERFD`, `EPOLL`, `NET`, `SYSFS`, `PROC_FS`, `FHANDLE`,
`CRYPTO_USER_API_HASH`, `CRYPTO_HMAC`, `CRYPTO_SHA256`, `TMPFS`,
`TMPFS_POSIX_ACL`, `SECCOMP`, `BLK_DEV_INITRD`, `RD_GZIP`, `RD_ZSTD`.

systemd refuses to boot without most of these, and the failure mode is an
initrd panic that says nothing about the real cause.

`TOUCHSCREEN_GOODIX_BERLIN_CORE` and `..._I2C` turn on item 3.

**Drop when:** never, while running NixOS.

## Not carried, and worth knowing

- **No patch for the panel driver.** `panel-canaan-universal` is stock.
- **No patch for thermal.** `canaan_thermal` is stock and built in, and its
  limitation — a tripless zone, so temperature is readable but nothing acts
  on it — is a property of the vendor driver, not of anything we changed.
  See `docs/thermal.md`.
- **No SMP patch.** Linux runs on one hart here because no K230 device tree
  declares a `cpu@1`. See `hardware-userspace.md`.

## Update after the first display bring-up (2026-09-20)

**Task 4.1b resolved to "no patch".** The GT9895 answers the Berlin protocol.
The v6.12 `goodix_berlin` backport already in item 3 binds it through a
`"goodix,gt9895", "goodix,gt9916"` fallback in the device tree, and registers
a touchscreen input device. Neither branch of 4.1b was taken: no chip entry
(there is no chip table), and no port of LilyGO's `gt9895.c`. Evidence:
`docs/evidence/touch-probe.txt`.

**One patch added: the DRM fbdev colour depth.**

```
sed -i 's|drm_fbdev_generic_setup(drm_dev, 32);|drm_fbdev_generic_setup(drm_dev, 16);|' \
  drivers/gpu/drm/canaan/canaan_drv.c
```

`canaan_drv.c:272` asks DRM's generic fbdev emulation for 32 bpp, which means
`XRGB8888`. The driver's own RGB planes advertise `AR24 AR12 AR15 RG24 RG16
BG24` — `XR24` is **not** among them — so format negotiation fails and no
`/dev/fb0` is created:

```
[drm] bpp/depth value of 32/24 not supported
[drm] No compatible format found
[drm] *ERROR* fbdev: Failed to setup generic emulation (ret=-22)
```

Observed on hardware, `docs/evidence/panel-probe.txt`. 16 bpp maps to
`RGB565`, which those planes do advertise.

This affects the fbdev console only. DRM clients negotiate format for
themselves and already work — `modetest -s 48:568x1232@AR24` sets a mode on
this panel with the unpatched driver.

**Drop when:** the vendor driver either advertises `XR24` on its RGB planes
or stops hardcoding 32 in the fbdev setup call. Worth re-checking on any
kernel bump, since a one-line constant is easy for upstream to change.

## Stage-1 splash preservation

The U-Boot handoff patch supplies an empty runtime `/chosen` property,
`canaan,stage1-splash`, only after its image load and RM69A10 initialization
succeed. The kernel does not treat that as a board property: an absent flag
keeps the ordinary reset, initialization, and fbdev setup path.

`panel-canaan-universal.c` reads the flag at probe into per-panel state. On a
flagged boot it requests `dsi_reset` with `GPIOD_ASIS`, leaving GPIO22 at the
stage-1 level instead of the vendor driver's `GPIOD_OUT_LOW`. Its first
`prepare()` logs `canaan_panel_prepare: left as stage 1 set it`, clears that
per-panel state, and returns before both the project reset pulses and the DCS
init sequence. A later prepare therefore runs the complete existing reset and
init path. The change is one-shot and does not persist through any later boot.

`canaan_drv.c` reads the same runtime property and skips
`drm_fbdev_generic_setup()` only when it is present. That avoids the initial
fbdev hotplug/modeset from scanning out a zeroed buffer over the U-Boot frame;
`/dev/fb0` is consequently absent on a flagged boot. A boot with no stage-1
success flag still creates the existing RGB565 fbdev console.

The source was checked before making this change. In the pinned tree,
`canaan_vo_enable_crtc()` initializes VO, programs timing/background, and
enables register load; it does **not** call the display reset. The
`0x91101090` write of zero then `0xffffffff` is in
`canaan_vo_disable_crtc()` only. Earlier text that placed that reset on the
enable path was wrong. This task intentionally does not change VO reset or
DSI/VO reprogramming; the first-modeset hardware task decides whether either
still causes a visible dark interval.

**Drop when:** stage 1 no longer owns a pre-kernel panel image, or a later
kernel handoff implementation adopts the running display state without the
fbdev modeset and has hardware evidence for both splash and no-splash boots.
If the first-modeset measurement shows a dark interval, restore the reset and
init work in `prepare()` as task 4.4 requires; do not hide that fallback.

## Prepared first-VO/DSI handoff trial — not built or tested

The first stage-1 preservation patch deliberately stopped at the panel reset,
DCS sequence, and fbdev.  The first real DRM client still runs the Canaan
runtime-PM commit order: CRTC enable calls `canaan_vo_enable_crtc()`, then the
encoder calls `canaan_dsi_encoder_enable()`, then the active plane update
writes the Linux framebuffer and `canaan_vo_flush_config()` loads it.  In the
pinned source this is `drm_atomic_helper_commit_tail_rpm()`, which enables
modesets before committing active planes.

A source-only trial is prepared in `nix/kernel.nix`.  Each VO and DSI driver
reads the runtime `/chosen/canaan,stage1-splash` boolean into an independent
one-shot flag.  It bypasses its first hardware reprogramming only when the
adjusted mode exactly matches the U-Boot RM69A10 mode: 49.5 MHz, 568x1232,
hsync 668..708 of 748, and vsync 1236..1252 of 1268.  On that path the DSI
still calls `drm_panel_prepare()` and `drm_panel_enable()`: the panel's
existing one-shot bookkeeping consumes its flag without reset or DCS writes.
The plane update and register load in that same atomic commit remain the
handoff point; this is not framebuffer adoption.

The VO bypass writes only the IRQ1 timing value which
`canaan_vo_set_timing()` would calculate, leaving visual registers alone;
normal DRM vblank enable remains responsible for its interrupt-enable bit.
A timing mismatch logs a warning and uses the ordinary VO/DSI setup.  The
panel sees that the DSI did not authorize preservation, clears its flag, then
explicitly restores the reset GPIO to output-high before its normal reset
pulses; a failure to set that direction is returned from `prepare()`.  A
disable before the first enable clears all three one-shot states, so a later
enable is also ordinary.

This is deliberately **not build or hardware evidence**.  It was prepared as
a bounded diagnostic after a stage-1 logo reached Linux but the first Sway
modeset showed a physical geometry/colour defect.  It may enter a dedicated
diagnostic image for a controlled physical comparison, but must not become a
default handoff path until that comparison establishes that retaining the
stage-1 VO/DSI state is safer than the normal first modeset.  In particular,
the source does not read back or prove the U-Boot hardware state, and the
physical owner experiment may show that normal Linux VO timing/conversion
programming is required before Sway takes the scanout.

**Drop when:** the physical first-frame evidence shows that ordinary VO/DSI
programming is the correct handoff, or a supported DRM handoff replaces this
one-shot vendor-driver experiment.  Do not retain it merely because the
stage-1 flag is present.
