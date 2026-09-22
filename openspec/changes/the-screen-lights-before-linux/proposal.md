## Why

Turn the board on and nothing happens. The glass stays black through DDR
training, through U-Boot's five-second countdown, and through the first
three and a half seconds of Linux; then a wall of kernel text appears on it.
A person holding the device has no way to tell a board that is booting from
one that is dead until the console arrives, and what arrives is a console.
That is the experience of a development kit, not of a thing.

Josh's ask, verbatim: *"have uboot drive the display because i don't see any
output til linux starts booting and the console comes out, and we'll want a
nice boot animation that transitions smoothly from uboot to when linux takes
over plymouth-style".*

He also said *"should be easy right"*. It is not, and the shape of why is the
shape of this change. Lighting the panel from U-Boot is the smallest of four
pieces. The other three are: the kernel today **resets the panel and replays
its whole init sequence** the moment it probes, which would extinguish
anything U-Boot lit; the kernel's framebuffer console **clears the screen** on
takeover; and a splash that survives the kernel only matters if something on
the Linux side then owns the screen and carries the image forward rather
than cutting to black. Each of those is a different layer — stage 1, kernel,
device tree, Nix, userspace — and each has its own proof.

## What Changes

- **Stage 1 lights the panel and shows an image before it loads the kernel.**
  Canaan's U-Boot already carries a bare-metal display path for the CanMV's
  ST7701 (`board/canaan/common/logo/` in the SDK overlay), and LILYGO's
  published BSP extends that same path to this exact panel — a 568x1232
  XRGB8888 logo loaded from the boot partition, scanned out from a fixed
  address, with the RM69A10 init sequence and reset on GPIO22. This change
  vendors that work onto the U-Boot this project builds, and corrects the one
  value both vendors get wrong: the DSI PHY calibration band, which is
  `0x87` on this SoC at our lane rate, not `0x96`.
- **The kernel does not extinguish what stage 1 lit.** When stage 1 says at
  runtime that the panel is up, the panel driver leaves the reset line alone
  and skips the init sequence on its first prepare, and the DRM driver does
  not bring up its fbdev emulation — which is the thing that would otherwise
  modeset a zeroed buffer onto the screen from a workqueue during boot.
  When stage 1 did *not* light the panel, the kernel does everything it does
  today. Both are kernel patches, recorded as the `system/kernel` capability
  requires.
- **The splash buffer has an address, and the address is in one memory
  map.** Stage 1 loads a 57 MiB kernel to `0x200000`, and OpenSBI then copies
  the device tree to `0x2200000` — 32 MiB *into* that kernel — which the
  board survives only because the bytes land in `.BTF`
  (`docs/evidence/opensbi-fdt-lands-in-kernel-image.md`). The vendor's own
  logo path stages its picture at `0x1000000`, also inside our kernel. There
  is no map of what stage 1 puts where. This change writes one, chooses the
  splash address against it, reserves it from the kernel through the device
  tree, and makes U-Boot and the device tree take the number from a single
  place in the flake.
- **Something on the Linux side owns the transition.** The splash must be
  carried, not cut: the first thing Linux draws is the same image stage 1
  drew, an animation may run from there, and the last frame is retained
  until the shell's first frame replaces it. Plymouth is the obvious
  implementation and the design weighs it against a minimal DRM splash and
  against simply letting the shell take over; the choice is made by a
  measured cross-build cost, not assumed. The animation lives on the Linux
  side by construction — U-Boot is a single-threaded loader and every frame
  drawn there is a frame the kernel waits for.
- **The console on the panel becomes a switch, off by default.** Today
  `console=tty0` puts boot text on the glass. With a splash that is the
  wrong default, and it is also what triggers the framebuffer console's
  clear. The switch restores exactly today's behaviour for bring-up work.

**Non-goals.** A NixOS generations menu, or any interactivity in U-Boot.
Changing U-Boot's `bootdelay` — the splash appears before the countdown, so
the countdown delays the kernel, not the picture, and shortening it is a
separate decision that affects `the-card-is-flashed-over-usb-from-u-boot`.
Brightness or backlight control beyond the `51 FE` the init sequence already
sends. Touch during boot. HDMI. Any change to which shell the board runs or
how the shell draws — this change ends where the shell's first frame begins.
Shrinking the boot itself: userspace starts around 22 s after the kernel
does today and this change hides that, it does not fix it.

**Sequencing, and this is a hard dependency.** Stage 1 on `master` is a
vendored binary. Nothing here can be done to a binary: the display code, the
Kconfig that enables it, the environment line that runs it and the `/chosen`
fixup all live in U-Boot source. `every-blob-is-built-from-source-or-named`
builds U-Boot and OpenSBI in the flake (`nix/uboot-k230.nix`,
`nix/opensbi-k230.nix`) and **must land first**. This change does not touch
`firmware/stage1/` and does not plan around the vendored binaries at all. It
also expects that change to have moved OpenSBI's device-tree copy out of the
kernel image, since the memory map this change writes would otherwise have
to document a collision it cannot fix.

`the-screen-runs-a-shell-not-a-console` is in flight and independent: it
delivers the thing that eventually replaces the splash. What this change
hands it is a contract — the screen is lit and showing a known image when
the compositor starts, and the compositor's first frame is the end of the
splash — not a dependency in either direction.

**Needs the physical board** for everything that matters. Building U-Boot
with the display code enabled, producing the splash asset, compiling the
device tree, and measuring what Plymouth costs to cross-build are laptop
work. Whether the panel lights under U-Boot, whether it stays lit across the
kernel, and whether the handoff shows a dark frame can only be photographed
and captured on hardware; QEMU's `k230` machine models neither stage 1 nor a
display.

## How big this is

Four pieces, each proven separately:

| piece | layer | size |
| --- | --- | --- |
| Light the panel from U-Boot with the right PHY band | stage 1 (U-Boot overlay, Kconfig, env) | vendored from LILYGO; one measured value to change |
| An address that survives the handoff, and a map | stage 1 env, device tree, Nix | small, but it is the place a wrong number corrupts a kernel silently |
| Probe and first modeset leave a lit panel alone | kernel (two drivers), U-Boot `/chosen` fixup | real driver work; the display block reset on first enable is the open risk |
| Own the screen from the initrd to the shell without a cut | Nix, userspace | the largest cross-build in the change if it is Plymouth |

## Capabilities

### New Capabilities

- `display/boot-splash`: what the panel shows from power-on until the system
  draws its first frame, who owns each stage of that, and how one stage hands
  the lit panel to the next.

### Modified Capabilities

- `display/panel`: "The panel displays what the system draws" currently
  promises that a boot ends with *the console* photographed on the screen and
  that the panel is presented as an fbdev framebuffer. Both become a
  configuration rather than the default: the panel is a DRM device at
  568x1232, the console can be put on it, and by default what a boot shows is
  the splash.
- `image/boot-chain`: gains the obligations that stage 1 lights the panel,
  that it tells the kernel it did so, and that every address stage 1 loads
  into is recorded in one map the splash buffer is chosen against. "Stage 1
  hands control to our kernel" loses its "without modification to stage 1
  itself" clause, which `every-blob-is-built-from-source-or-named` already
  made untrue.

## Impact

Adds U-Boot source patches (the RM69A10 logo path, a `/chosen` fixup) to
`nix/uboot-k230.nix`, a Kconfig fragment enabling `K230_BARE_DISP_LOGO`, and
a line in the generated stage 1 environment. Adds a splash-asset derivation
and puts its output on the boot partition next to `Image`. Adds a
`reserved-memory` node to `nix/dts/k230-tdisplay.dts`. Adds two kernel
patches to `nix/kernel.nix` and records them in
`docs/evidence/kernel-patches.md`. Adds either `boot.plymouth` and a theme, or
a small DRM splash package, to the system closure — a riscv64 cross-build
with no binary cache either way, so it is sized before it is chosen. Removes
`console=tty0` from the default kernel command line behind a new option.

Vendor source this change reads and cites by path:
`.build/k230_linux_sdk/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/board/canaan/common/logo/{display_logo.c,k230_logo.c,st7701.c}`,
and LILYGO's `Xinyuan-LilyGO/T-Display-K230` at
`k230_bsp/overlay/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/board/canaan/common/logo/`
plus its Linux patches `0027`, `0038` and `0051`. The first task records the
LILYGO diff under `docs/evidence/` so that the grounding does not depend on a
GitHub repository staying where it is.
