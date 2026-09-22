## Context

See proposal.md — Why. What shapes the approach:

- **Stage 1 is source now, or this change does not exist.**
  `every-blob-is-built-from-source-or-named` gives the flake `nix/uboot-k230.nix`
  (U-Boot 2022.10 plus Canaan's rsync overlay, `k230_canmv_v3_defconfig`) and
  `nix/opensbi-k230.nix`, and generates the stage 1 environment from text.
  Every stage 1 piece of this design is a patch, a Kconfig line or an
  environment line on top of that. Layer: **stage 1**.
- **The display path in U-Boot exists and has been ported to this panel by
  the vendor.** Canaan's `board/canaan/common/logo/` drives VO, DSI and the
  D-PHY bare-metal and blits a logo for the CanMV's ST7701. LILYGO's BSP
  overlay (`Xinyuan-LilyGO/T-Display-K230`,
  `k230_bsp/overlay/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/`)
  adds `CONFIG_K230_BARE_DISP_LOGO_RM69A10`: a 2-lane PHY routine,
  `rm69a10_568x1232_init()` with a 13-command sequence, `GPIO_RST_PIN 22`,
  and an OSD4 XRGB8888 scanout of `/logo.xrgb` from `0x1f000000`. Read in
  full on 2026-09-22 at commit `bb831ab` and diffed against the SDK copy —
  `docs/evidence/lilygo-uboot-logo.md`, 549 lines over the four logo files.
  Their sequence is **not** the one our device tree sends: rows 6-8 are the
  partial-area block `31 …`, `30 …`, `12` (ENTER_PARTIAL_MODE), which lit
  this panel under Linux but glitched (`docs/evidence/panel-lit.md`, "Still
  wrong: the image is glitchy"), and which
  `nix/dts/display-rm69a10-568x1232.dtsi` replaced with `13`
  (ENTER_NORMAL_MODE). The port sends the DTSI's sequence, not LILYGO's.
  The same overlay also deletes `enter_to_usb_burn_mode()` from
  `k230_board_common.c` and moves the U-Boot environment to
  `ENV_OFFSET 0x1e0000` / `ENV_SIZE 0x10000`; neither is carried (see the
  vendoring decision below). It is authored by an AI agent and its
  commit messages are not to be trusted (`docs/research/linux-on-t-display-k230.md`
  §3), but LILYGO ships images in which it lights this panel.
- **Both vendors hardcode the wrong PHY band for our lane rate.** LILYGO's
  connector table says `hs_freq 0x96` at 475 Mbps, where it is correct;
  Linux's `canaan_dsi.c:383` (pristine pinned tree; line 428 in the tree
  `nix/kernel.nix` builds) said `0x96` at any rate until
  `canaan,hsfreqrange` was plumbed through the device tree. At our 594 Mbps the
  measured answer is `0x87` (`docs/evidence/dsi-hsfreqrange-hardcoded.md`).
- **The kernel extinguishes the panel at probe and again at first enable.**
  `panel-canaan-universal.c:318-329` pulses reset in probe; our
  `nix/kernel.nix` adds three more pulses in `prepare()` ahead of the init
  replay, because without them the panel did not answer. Then
  `canaan_vo_enable_crtc()` (`canaan_vo.c:675`) opens with
  `k230_display_rst()`: a write of 0 then `0xffffffff` to `0x91101090` and a VO
  software reset, before re-timing VO, and the encoder path reprograms the
  DSI controller and PHY. The first enable during boot is driven by the
  fbdev emulation from the output poll worker (`dsi-phy-hang.md` trace:
  `output_poll_execute → canaan_dsi_encoder_enable`), scanning out a buffer
  `drm_fbdev_generic.c:89-98` allocated zeroed.
- **There is no memory map, and the last unmapped address corrupted the
  kernel.** `docs/evidence/opensbi-fdt-lands-in-kernel-image.md`. The vendor
  logo path's staging address `0x1000000` is inside our 57 MiB kernel too.
- **Userspace is late.** `systemd[1]` first logs at ~22 s
  (`docs/evidence/panel-probe.txt`). Anything that only runs from the main
  system leaves the U-Boot frame static for twenty seconds.
- **Every riscv64 package is compiled.** No binary cache. The shell change
  measured its stack at 89 derivations / 875 MiB and rejected Hyprland at
  184 / 2.2 GiB; those are the yardsticks for anything this change adds.
- **The board is a shared resource.** Every hardware task here takes
  `/dev/ttyACM0` and says so.

## Goals / Non-Goals

**Goals:**

- The glass responds within stage 1, on our U-Boot, at our mode, with the
  measured PHY band.
- The kernel provably leaves a lit panel alone, and provably still lights an
  unlit one.
- One recorded memory map, and the splash address chosen against it from
  one constant in the flake.
- A Linux-side owner of the screen chosen by a number, with the handoff
  filmed.

**Non-Goals (design level, beyond the proposal's):**

- A U-Boot DM video driver for the K230 VO/DSI. The bare-metal path is
  register pokes with no uclass; wrapping it as a `video` driver so that
  `bmp display` and `fdt_simplefb` work would be a rewrite of code we did
  not write, for no visible benefit.
- Making the kernel adopt the running hardware state (a "no-op modeset"
  when U-Boot's mode matches). That is a rewrite of `canaan_vo_enable_crtc`,
  which starts with a block reset, and of the encoder path. Considered and
  deferred: the measurement in task 4.4 decides whether it is even needed.
- Continuity in the strict sense of one scanout buffer never touched. See the
  decision below; the design carries the *image* across, not the buffer.

## Decisions

**Vendor LILYGO's U-Boot logo path as patches on the SDK overlay, and cite
it; do not write our own.** LILYGO's diff against Canaan's four files is the
only U-Boot code known to light this panel. It goes into
`nix/uboot-k230.nix` as a patch series applied after the overlay copy, with
the source commit recorded, plus a Kconfig fragment enabling
`K230_BARE_DISP_LOGO` and `_RM69A10`. Rejected: transcribing the sequence
into fresh code — a second implementation of a bring-up we only just got
right in Linux, with a second set of timing bugs. Rejected: taking LILYGO's
whole overlay — it also carries their defconfig and board files, and this
project's stage 1 is deliberately `k230_canmv_v3` plus recorded deltas.
Concretely, three things in that overlay are left out on purpose
(`docs/evidence/lilygo-uboot-logo.md`, "What LILYGO's U-Boot overlay
contains", item 9): their `k230_board_common.c` deletes
`enter_to_usb_burn_mode()` and inlines it into `do_2_burn_mode`, a file
`the-card-is-flashed-over-usb-from-u-boot` owns; their defconfig moves the
environment to `ENV_OFFSET 0x1e0000` / `ENV_SIZE 0x10000` where this
project's card has it at 3 MiB and 3.5 MiB, 8 KiB (`nix/stage1.nix`); and
their `board.c` drives GPIO52 low at `board_init()` for a keyboard
backlight this change has no opinion on. What is carried is the four
`logo/` files and the one Kconfig hunk. The init sequence inside `st7701.c`
is rewritten to the DTSI's (`13` for LILYGO's `31/30/12`), so that stage 1
and the kernel initialise the panel identically. Layer: **stage 1 (Nix
over vendor source)**.

**Drive the same mode from U-Boot that Linux drives: 49.5 MHz, 594 Mbps,
hsfreqrange `0x87`, with the PLL `m/n/voc` derived by the same arithmetic
`canaan_dsi_clk_cfg()` uses.** A handoff that is also a mode change re-times
the panel in the middle of the thing we are trying to make seamless, and
the 39.6 MHz LILYGO uses is the refresh the device tree's own comment
identifies as the source of AMOLED flicker. The band value is the measured
one; the vendor's `0x96` in the connector table is replaced, not defaulted.
Also matched, register by register: `VID_MODE_CFG` (Linux writes `0xbf02`,
`canaan_dsi.c:280`; LILYGO's U-Boot writes `0x3f02`), `DPI_COLOR_CODING`
(`0x105` in Linux, `canaan_dsi.c:288`; `0x005` in LILYGO's U-Boot). Each
divergence from LILYGO's numbers is recorded in the same table as the
device tree divergences. **Fallback, in order:** if the panel does not light
or rolls under U-Boot at our numbers, first prove the path with LILYGO's
exact table (39.6 MHz / `0x96`), then move one parameter at a time — the
same method that found `0x87` in the first place. Rejected: shipping
LILYGO's numbers — it works, and it hands Linux a panel at the wrong
refresh that then has to be re-timed. Layer: **stage 1**.

**The "panel is lit" fact crosses to the kernel at runtime, in `/chosen`,
written only on success.** `k230_display_logo()` clears a process-local C
readiness flag before every attempt and sets it only after the bounded asset
load and `st7701_init()` both succeed. `ft_board_setup()` — which the vendor
already uses to rewrite the memory node — asks that exported function and
writes `canaan,stage1-splash` as an empty boolean in `/chosen`. The state is
never put in the U-Boot environment: `k230_set_dtb` calls `env_save()`, so an
environment variable could survive a prior boot and falsely suppress Linux
reset/init. A boot with a missing or malformed logo, a PHY/init failure, or
an FDT write failure has no flag and the kernel follows its normal reset
path. Rejected: LILYGO's static `canaan,preserve-boot-splash` in the panel
node (patch 0051). It is simpler, and it turns every stage 1 hiccup into a
permanently dark screen with no log line to say why. Rejected: passing it on
the kernel command line — `bootargs.txt` is generated by Nix before stage 1
runs and cannot know what stage 1 will manage to do. Layer: **stage 1 →
device tree → kernel**.

**Kernel side: skip reset and init on the first prepare, and do not set up
fbdev, when the flag is present; both are per-boot, not per-board.** Three
edits, all in `nix/kernel.nix` as the existing patches are:

1. `panel-canaan-universal.c` probe: request the reset GPIO `GPIOD_ASIS`
   when lit (LILYGO 0051's hunk, keyed on the runtime flag).
2. `canaan_panel_prepare()`: when lit and this is the first prepare, skip
   the reset pulses and the sequence, log that it did, and clear the flag;
   any later prepare (DPMS, a second modeset after a disable) runs the full
   path. Our own added reset pulses live in the same `if`.
3. `canaan_drv.c`: skip `drm_fbdev_generic_setup()` when lit (LILYGO 0051's
   other hunk). This removes the boot-time modeset entirely; nothing touches
   the pipeline until a DRM client opens the device. `/dev/fb0` does not
   exist on a splash boot, which is why `display/panel` is modified.

Rejected: `CONFIG_FRAMEBUFFER_CONSOLE_DEFERRED_TAKEOVER` with fbdev kept.
It defers *fbcon*, but the modeset that clears the screen is the helper's
own, from `drm_fb_helper_hotplug_event → drm_fb_helper_set_par`
(`drm_fb_helper.c:1990`) when the poll worker first sees the connector
change from `unknown` to `connected`; and the takeover itself fires on the
first console output at the current loglevel, which on this board is a
`pr_warn` about BTF every boot. Rejected: pre-filling the fbdev buffer with
the splash so the modeset is invisible — a patch to DRM core, not the
vendor driver, to solve a problem removing fbdev solves outright.
Layer: **kernel**.

**Carry the image across the handoff, not the buffer.** The reserved
region exists so the kernel does not allocate over what VO is still
scanning out; nothing in Linux reads it. The first Linux frame is the same
picture because the owner draws the same asset, from the store. Rejected:
a `simple-framebuffer` handoff. `simpledrm` would be evicted by
`canaan-drm` at probe through the aperture helpers, and `canaan-drm`'s
first enable begins with a block reset regardless of what it inherited;
the buffer identity buys nothing. Rejected: making the reserved region the
CMA pool so the first GEM allocation lands on the U-Boot buffer — the
address is not guaranteed and `dma_alloc_wc` zeroes it anyway. Layer:
**device tree, userspace**.

**The address is one constant in the flake, and it is chosen against a
recorded map — candidate `0x10000000`, 4 MiB
(`0x10000000..0x10400000`).** `docs/evidence/stage1-memory-map.md` now
records the physical-board `bdinfo` and the candidate image's `bootm` lines:
the range is 86 MiB above the loaded initrd end (`0x0aa07d8e`), above but
clear of `loadaddr` (`0x0c000000`), below the `force_dtb` scratch address,
and 764 MiB below U-Boot's exact LMB reservation beginning at `0x3fb37920`.
The current initrd relocates to `0x3e12f000`, leaving
`0x10400000..0x3e12f000` = 733 MiB for CMA. Source analysis therefore
predicts that the 512 MiB CMA pool can remain at the logged `0x1e000000`;
a reserved-memory DTS build and board boot must verify that the kernel layout
is unchanged. **Rejected:
`0x1f000000`, LILYGO's number.** It is clear of everything stage 1 loads
or relocates, but it is *inside* the CMA pool the kernel places at
`0x1e000000..0x3e000000`. A `no-map` reservation there is excluded from
`memblock` allocation (`drivers/of/fdt.c:479-494`,
`mm/memblock.c:1001-1025`), splitting the free range into 335 MiB below
the hole and 493 MiB above it, and 512 MiB fits in neither; the likely
result is `cma: Failed to reserve` and the display driver's `dma_alloc_wc`
falling back to the page allocator — reasoning from source, unverified on
the board, and the reason not to find out on the board. LILYGO's images
survive it because they boot without an initrd, so their free range above
the hole runs to the top of RAM (524 MiB); this system pins 26 MiB of
initrd at the top at exactly the moment CMA is placed. The
constant feeds `CONFIG_K230_BARE_DISP_LOGO_FB_ADDR` (a new Kconfig symbol
replacing LILYGO's `#define`) and the `reserved-memory` node's `reg`
through the device tree's preprocessor, so they cannot disagree. Rejected:
the vendor's `env_get_bootm_size()`-as-an-address trick (`k230_logo.c:198`)
— it returns the *size* of the bootm region, is meaningful only by
accident, and its staging copy at `0x1000000` sits inside our kernel.
Rejected: `no-map` omitted so the kernel could reuse the 4 MiB — VO is
still reading it when the kernel starts, and 4 MiB of 1 GiB is not worth
the class of bug. Layer: **Nix, stage 1, device tree**.

**Splash format: XRGB8888, as LILYGO's path scans out; one asset, one
derivation.** A PNG in the repository; a Nix derivation renders it to
`568x1232` XRGB8888 with a size check equal to `2 799 104` bytes
(568 x 1232 x 4; LILYGO's `RM69A10_LOGO_XRGB_SIZE`, and the U-Boot code
refuses any other `filesize`), and the same derivation produces the frames
the Linux-side owner uses, so frame 0 on both sides is the same bytes
through different pipelines. Rejected: RGB565 to halve the buffer — it
would diverge from the only U-Boot scanout configuration proven on this
panel, to save 1.4 MiB. Layer: **Nix**.

**Linux-side owner: Plymouth in the systemd initrd if it cross-builds
within the shell stack's budget; otherwise a minimal DRM splash in the main
system, with no animation until the shell.** The rule is written here so
that the task that measures it does not also get to decide it. Budget:
no more than the 89 derivations / 875 MiB the shell change measured for
`sway + foot + wvkbd`, counted with the same method
(`docs/display-environment-options.md`). Why Plymouth first: it already does
the whole job — starts from the initrd, opens DRM, animates, and
`plymouth quit --retain-splash` leaves the last frame for the compositor —
and NixOS's `boot.plymouth` module integrates it with the systemd initrd
this board uses. Why not assume it: nixpkgs' `plymouth` lists
`platforms.linux` and no riscv64 exclusion, but nobody has built it for
riscv64 here, and its dependency graph (systemd, libdrm, freetype, pango
for the label plugin) is exactly the kind that arrives with a second
toolchain. Why the fallback has no animation: a splash that starts at 22 s
cannot animate anything a person is still waiting to see; it exists only
to satisfy the retain-until-the-shell property. Rejected as the sole
approach: letting the shell change's compositor own the screen from the
start — sway starts after the same 22 s and its first act is a clear to its
background; it is the *end* of the handoff, never the middle. Rejected: an
animation in U-Boot — single-threaded, and every frame is time the kernel
is not being loaded. Layer: **Nix, userspace**.

**Console on the panel becomes `k230.panelConsole`, off by default.** On:
`console=tty0` stays, `FRAMEBUFFER_CONSOLE` is used, and Nix omits the
splash file from the boot partition, so stage 1 leaves the panel dark and
the kernel path is exactly today's. Off: no `console=tty0`, splash file
present. The kernel is the same binary in both; the switch is a file on the
card and a command line, which is why it is cheap to flip while chasing a
panel regression. Rejected: a kernel command-line knob to turn off the
splash preservation — it would let the two sides disagree, and the failure
would look like a dead panel. Layer: **Nix**.

## Risks / Trade-offs

- **The display block reset at Linux's first enable visibly blanks the
  panel, or the panel does not come back without its init sequence.** →
  This is the open question the whole "smooth" claim rests on, and it is
  measured before anything is built on it (task 4.4). If a dark interval
  shows, the fallback is to keep reset + init in prepare and accept a blink
  at the owner's first frame; the splash still covers stage 1 and the
  kernel boot, and the boot-splash requirement is restated to what was
  measured. If the panel does not recover at all, the fallback is the same.
- **`0x87` behaves differently under U-Boot's PHY routine.** → LILYGO's
  2-lane routine waits 20 ms where the SDK waits 1 ms and orders the resets
  differently from `canaan_phy.c`. Prove the path on LILYGO's numbers first,
  then change one parameter at a time, measuring with `tools/panel-measure.py`.
- **`0x10000000` is under U-Boot's heap or where `bootm` relocates the
  initrd.** → The physical-board `bdinfo` puts U-Boot's LMB reservation at
  `0x3fb37920..0x40000000`, and the current `Loading Ramdisk to` line ends
  at `0x3fb36d4e`; both are far above the chosen range. The remaining risk
  is a future load command added without updating the recorded map. The CMA
  placement risk is handled by the address decision above.
- **Plymouth drags in a second cross toolchain or fails to build.** →
  The decision rule caps it; the fallback is written down and is small.
- **Losing boot text on the glass by default.** → Real. Every panel
  diagnosis so far watched the console. The switch restores it in one
  option, and the serial console never moved.
- **The U-Boot sequence and the device tree sequence drift.** → They
  already differ: LILYGO's C sends `31/30/12`, our DT bytes send `13`, and
  the port rewrites the C to match the DT. Record both in
  `docs/evidence/rm69a10-init-sequence.md` side by side, and make the
  divergence table the place a future change has to edit.
- **LILYGO moves or rewrites their repository.** → The diff is committed
  under `docs/evidence/` in task 1.1, with the commit hash, before anything
  depends on it.

## Migration Plan

Nothing here is destructive, and every step is reversible by removing a
file. The splash file absent from the boot partition is the old behaviour
in stage 1; the `/chosen` flag absent is the old behaviour in the kernel;
`k230.panelConsole = true` is the old behaviour in Nix. Stage 1 changes ride
the from-source build, so a stage 1 that fails to boot is recovered the way
`every-blob-is-built-from-source-or-named` recovers: a second card with the
last known-good image. The kernel patches are gated by the flag, so a
kernel carrying them boots identically on a card without a splash, which
is how they are tested before the U-Boot side lands.

## Open Questions

- Whether `plymouth quit --retain-splash` and the compositor's first modeset
  compose cleanly on this driver, or whether the compositor's `drmModeSetCrtc`
  triggers the panel disable/enable path (and so, on the fallback, a
  blink). Answerable only once the shell change has a compositor to start;
  it changes how task 5.4 is filmed, not what is built.
- Whether the 5-second `bootdelay` should shrink now that the splash makes
  the wait visible. Out of scope here and noted for
  `the-card-is-flashed-over-usb-from-u-boot`, which is the change that needs
  the prompt.
