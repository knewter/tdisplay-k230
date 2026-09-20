## Why

The reason to own this board rather than a headless one is the 4.1" AMOLED on
the front. After `the-board-boots-what-we-built` it runs our Linux and answers
on a serial cable, and the screen is dark. Everything this project is actually
for — AtomVM with something to show, the Dozer core with a shell — is waiting
on a panel and a working touch surface.

The shipped RT-Smart firmware drives both, so the hardware is known good and
the init sequence is known: it is sitting in LilyGO's `rm69a10.c`. What is
missing is the same thing expressed to Linux.

## What Changes

- **A device tree for the RM69A10 AMOLED.** The kernel already carries
  `panel-canaan-universal`, which takes its init command sequence, timings,
  lane count and reset GPIO from the device tree. So this is a new `.dtsi`
  transcribed from the vendor's working init sequence, not a new driver.
- **GT9895 touch.** The Xuantie kernel carries the older GT9xx `goodix.c`; this
  panel's controller is the Goodix Berlin generation, supported in mainline
  since roughly 6.7. This backports that support onto the 6.6-based tree.
- **The board is usable without a serial cable.** A console on the panel, so
  the screen is demonstrably being driven by something other than a test
  pattern.
- **Evidence that is a photograph.** A framebuffer that claims success while
  showing nothing is exactly the failure this project already hit once with the
  Wi-Fi radio, where the driver reported `start ap successs!` and transmitted
  nothing. A `/dev/fb0` that exists is not a screen that works.

**Non-goals.** The backlight beyond what is needed to see the panel at all.
Any GPU or acceleration — the K230's 2.5D block has no Mesa or Vulkan driver
and everything here is software-rendered. Rotation, colour calibration, or
power management. Choosing a UI toolkit; that is a later decision and this
change deliberately does not constrain it.

## Capabilities

### New Capabilities

- `display/panel`: what is on the screen and how the panel is driven.
- `display/touch`: what happens when a person touches it.

### Modified Capabilities

- `system/kernel`: gains the obligation to carry this board's panel and touch
  support, and to say how it diverges from the upstream Xuantie tree.

## Impact

Adds a device tree source for this board and a kernel patch or overlay
backporting `goodix_berlin`. Both land in the kernel derivation, so this change
touches how the system is built, not only what it contains.

Carrying a backport means the kernel derivation stops being a pinned upstream
revision and becomes a pinned revision plus patches. That is a maintenance cost
this change knowingly takes on, and it is the first patch in the tree.

Needs the physical board throughout. Nothing here can be proven under QEMU —
its `k230` machine models no display pipeline at all.
