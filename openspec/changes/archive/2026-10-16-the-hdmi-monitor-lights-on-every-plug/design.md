## Context

The compositor allocates scanout buffers through wlroots' DRM dumb-buffer
allocator. The canaan DRM driver backs those buffers with DMA-coherent
memory. Without CMA, that memory comes straight from the buddy allocator, so
the largest contiguous block is `MAX_PAGE_ORDER` (4 MiB at 4 KiB pages), and
any block is only available while memory is unfragmented.

## Decisions

1. **A default CMA area of 64 MiB, set in the kernel config**
   (`CMA_SIZE_MBYTES`), not on the command line. The boot files carry their
   own `bootargs.txt`, and keeping the size in the kernel's config means
   every boot path gets it. 64 MiB holds a triple-buffered 1280x800 XRGB
   swapchain (12 MiB) plus cursor and client buffers with room to spare.
   While unused, the pages remain available for movable allocations.
2. **Pin 1280x800 in Sway's HDMI output block.** The shell's HDMI layout,
   touch calibration and frame budgets were all accepted at that size. A
   monitor that does not list the mode falls back to Sway's preferred-mode
   choice, which is today's behaviour.

## Risks

- A wrong CMA placement could collide with the stage 1 framebuffer
  reservation (`framebuffer@10000000`). The kernel places the default CMA area
  through memblock, which avoids reserved regions. The boot log will show
  where it landed.
- 64 MiB reserved at boot slightly reduces memory for unmovable kernel
  allocations. That is acceptable at 1 GiB.
