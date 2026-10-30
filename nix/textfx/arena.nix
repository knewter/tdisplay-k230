# The stage 1 engine arena (openspec change the-boot-plays-terminal-text-effects,
# design D14): the fixed DRAM range the no_std ttfx engine allocates from while U-Boot
# runs.  tools/check-boot-textfx-memory.py proves it against the real boot layout.
#
# 0x18000000 lies in the gap the stage 1 memory map records as free at every moment of
# stage 1 and untouched by the kernel's own placement
# (docs/evidence/stage1-memory-map.md, 2.3: 0x15010000..0x1e000000), clear of the splash
# reservation (0x10000000..0x10400000), of the CMA pool that begins at 0x1e000000, and of
# the relocated initrd and U-Boot at the top of RAM.  32 MiB against a measured
# worst-case engine heap of 13.4 MiB (rings): 2.4x.
{
  arenaAddress = "0x18000000";
  arenaSize = "0x02000000";
  # The engine never takes more than this fraction of the arena for itself: an
  # effect is allowed in the default per-boot list only if its measured peak heap
  # is at most arenaSize / arenaMarginDivisor.
  arenaMarginDivisor = 2;
  # A private stack for engine steps is carved from the top of the arena.
  engineStackSize = "0x00010000";
}
