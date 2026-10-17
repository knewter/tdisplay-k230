## Why

Plugging in HDMI can leave the monitor dark. On 2026-10-16, after about two
hours of uptime, the operator plugged in the HP 27wm and saw nothing. The
compositor could not allocate a scanout buffer for any mode from 1920x1080
down to 1280x800: every attempt logged `Failed to create DRM dumb buffer:
Cannot allocate memory`. It fell back to 1280x720, which the monitor did not
show.

A power-key wake 60 s later did get a 1280x800 buffer, by chance. The same
allocation failures appear at boot (11:52:57 the same day), where 1920x1080
always fails.

The kernel has no CMA, so every scanout buffer must come from the page
allocator as one physically contiguous block:

- A 1280x800 XRGB buffer is 4 MiB, the allocator's largest block. At the time
  of the failure, `/proc/buddyinfo` showed two free 4 MiB blocks and none of
  2 MiB.
- 1920x1080 needs 8 MiB, which the page allocator can never supply.

Fragmentation grows with uptime, so plug-in grows less reliable the longer
the handheld runs.

## What Changes

- The mainline DRM kernel enables `CMA` and `DMA_CMA` with a 64 MiB default
  area. Contiguous scanout buffers then come from a reserved pool that
  ordinary movable pages may borrow while it is free.
- Sway pins `output HDMI-A-1` to 1280x800, the mode the shell has been
  accepted and tuned at. With CMA, 1920x1080 would become allocatable and Sway
  would pick it as the monitor's preferred mode. That would roughly triple the
  per-frame CPU work of the Pixman rotation pass, and 1080p over this DSI link
  is unproven. A monitor without 1280x800 keeps Sway's own preferred-mode
  choice.

## Non-goals

- Supporting 1080p or other modes. Only allocation reliability is in scope.
- Explaining why the monitor showed nothing at 1280x720. That is a separate
  question; pinning 1280x800 avoids the mode.
- Changing the panel path, which uses 16-bit buffers at 568x1232.

## Board

Needs a kernel rebuild and a reboot. The final proof needs the operator to
plug the cable in after hours of uptime. Host checks: the kernel config
contains `CONFIG_DMA_CMA=y` and `CONFIG_CMA_SIZE_MBYTES=64`, and the system
closure builds.
