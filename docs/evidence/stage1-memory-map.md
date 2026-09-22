# Stage 1 memory map: what is loaded where, and what is free

Task 1.2 (static half) and task 2 (read from the board) of
`the-screen-lights-before-linux`. Required by `image/boot-chain`: "Every
address stage 1 loads into is recorded in one map". Before this file there
was no map, and `docs/evidence/opensbi-fdt-lands-in-kernel-image.md` is what
that cost.

RAM is 1 GiB at physical `0x0`: `nix/dts/k230-tdisplay.dts:39-41`
(`reg = <0x0 0x0 0x0 0x40000000>`), and the kernel's
`Memory: 398428K/1048576K available` (`docs/evidence/boot-from-source-cold.txt`
line 193). U-Boot sizes it at runtime by probing
(`arch/riscv/cpu/k230/dram.c:40-74`, `detect_ddr_size()`, doubling from
128 MiB until a write at `0` stops aliasing) and `ft_board_setup()`
(`board/canaan/common/k230_board_common.c:574-588`) rewrites the DTS memory
node from `env_get_bootm_low()`/`env_get_bootm_size()` before boot. All
vendor U-Boot paths are under
`.build/k230_linux_sdk/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/`
(the overlay `nix/uboot-k230.nix` builds from). Current sizes and relocation addresses are from the physical-board capture
`docs/evidence/uboot-usb-host-coexist.txt`, whose kernel is the pinned store
output named in §1.2. Earlier cold-boot values remain below as historical
measurements where they explain a difference.

## 1. Static half: read from files on disk

### 1.1 Every address in `firmware/stage1/tdisplay.env`

| line | variable | value | used by | what |
| --- | --- | --- | --- | --- |
| 12 | `dtb_addr` | `0xa000000` | nothing in `blinux` | vendor leftover |
| 13 | `fdt_high` | `0xa100000` | `bootm` | ceiling for the relocated FDT; **why the DTB lands at `0x0a0eb000`** (§2.2) |
| 14 | `fdtcontroladdr` | `80293880` | overwritten at runtime | stale: U-Boot sets it from `gd->fdt_blob` at boot (`OF_EMBED=y`); `0x80293880` is in on-chip SRAM, from when the vendor's U-Boot ran there |
| 17 | `kernel_addr` | `0xc100000` | nothing in `blinux` | vendor leftover |
| 18 | `loadaddr` | `0xc000000` | any load command given no address | equals `CONFIG_SYS_LOAD_ADDR`; `blinux` never omits an address |
| 22 | `ramdisk_addr` | `0xa100000` | nothing in `blinux` | vendor leftover; **inside the loaded initrd** (§1.3), so it must never be used |
| 28 | `blinux` | `0x7000000` | `ext4load … /bootargs.txt`, then `env import -t` | 211 bytes on 2026-09-22 |
| 28 | `blinux` | `0x8000000` | `ext4load … /fw_jump_add_uboot_head.bin` | OpenSBI uImage, 270 808 bytes → `0x080421d8` |
| 28 | `blinux` | `0x200000` | `ext4load … /Image` | the kernel, §1.2 |
| 28 | `blinux` | `0x8400000` | `ext4load … /force.dtb` | 71 298 bytes → `0x08411682` |
| 28 | `blinux` | `0x9000000` | `ext4load … /initrd.uimg` | §1.3 |
| 28 | `blinux` | `bootm 0x8000000 0x9000000 0x8400000` | | boots OpenSBI as "the kernel" with the initrd and the DTB |
| 30 | `bnuttx` | `0x7000000` | unused | vendor leftover |

Not in the env file but run by `bootcmd` through `k230_set_dtb`
(`k230_board_common.c`, the `force_dtb` probe): `ext4load mmc 1:1 0x15000000
force_dtb`, 17 bytes, visible as the first line after the countdown in
`boot-from-source-cold.txt`. `0x15000000` is scratch.

### 1.2 The kernel Image at `0x200000`

- File: **60 351 488 bytes**, read by U-Boot as `60351488 bytes read` in
  `docs/evidence/uboot-usb-host-coexist.txt` and verified from
  `/nix/store/1kgxy1xsvmyb2y8gzjxz4j2asirgy5ap-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie/Image`.
  The earlier cold-boot capture recorded 60 350 976 bytes; that is retained
  as a historical image measurement, not used for this candidate's map.
- In memory: the RISC-V Image header's `image_size` field (bytes 16-23 of
  the file) is **`0x3a25000`** (60 967 936; `od -An -tx8 -j8 -N16 Image` →
  `0000000000200000 0000000003a25000`), which is `_end - _start` in
  `System.map` (`_start ffffffff80000000`, `_end ffffffff83a25000`). The
  extra 0x397000 over the file is `.bss` (`__bss_start ffffffff8398f000`).
- **Extent: `0x00200000 .. 0x03c25000`** (58.1 MiB). `.BTF` is
  Image+`0x1fc78a4..0x30fef04` = `0x21c78a4..0x32fef04`.
- `text_offset` (header bytes 8-15) is `0x200000`: the kernel expects to run
  2 MiB above the start of RAM, which is why OpenSBI's `Domain0 Next Address`
  is `0x200000` and why `blinux` loads it there.

### 1.3 The initrd at `0x9000000`

- Current `initrd.uimg`: 27 295 118 bytes read from the card in
  `docs/evidence/uboot-usb-host-coexist.txt`; `bootm` reports a 27 295 054-byte
  payload after the 64-byte legacy header. The earlier 27 306 661-byte image
  in the cold-boot capture is historical only.
- **Current loaded extent: `0x09000000 .. 0x0aa07d8e`.** It overlaps
  `ramdisk_addr` and `fdt_high` from the env (both `0xa100000`); neither is a
  problem because `bootm` has already relocated both the FDT and the initrd
  (§2.2) before anything reads them, but it means `0x0a100000` is *not* a
  free address while `blinux` runs.

### 1.4 OpenSBI

- `nix/opensbi-k230.nix`: `FW_TEXT_START=0`, `FW_JUMP_ADDR=0x200000`
  (derived by upstream OpenSBI 1.4's `platform/generic/objects.mk:33`), **`FW_JUMP_FDT_ADDR`
  deliberately undefined** so `fw_jump` passes `a1` through
  (`docs/evidence/opensbi-fdt-passthrough.txt`). The vendor's value would be
  `0x2200000` (`objects.mk:35`, same file), inside the kernel at `.BTF`.
- `bootm` copies the uImage payload (270 744 bytes) to its load address
  `0x0`. The OpenSBI banner in `boot-from-source-cold.txt`: `Firmware Base
  0x0`, `Firmware Size 323 KB`, `RW Offset 0x40000`, `Heap Offset 0x48000`,
  `Heap Size 35 KB`. The kernel then sees `mmode_resv1@0`
  (`0x0..0x3ffff`) and `mmode_resv0@40000` (`0x40000..0x5ffff`) as `nomap`
  reserved memory (`boot-from-source-cold.txt` lines 159-160).
- **Extent: `0x00000000 .. 0x00060000`**, reserved for the life of the
  system.

### 1.5 U-Boot's own configuration (`result-uboot/.config` from `nix build .#uboot-k230`)

| symbol | value | meaning here |
| --- | --- | --- |
| `CONFIG_SYS_TEXT_BASE` | `0` | U-Boot proper is loaded at `0x0` by the SPL (`nix/stage1.nix`: `mkimage -a $base -e $base` with `CONFIG_MEM_LINUX_SYS_BASE 0x00000000` from `sdk_autoconf.h:10`) and relocates itself to the top of RAM |
| `CONFIG_SYS_LOAD_ADDR` | `0xc000000` | default for load commands with no address; `loadaddr` in the env |
| `CONFIG_SYS_BOOTM_LEN` | `0x8000000` | 128 MiB cap on what `bootm` will unpack; the thing `bootm` boots is OpenSBI (264 KiB), so the 58 MiB `Image` is never measured against it |
| `CONFIG_SYS_MALLOC_LEN` | `0x400000` | 4 MiB heap after relocation, carved below `relocaddr` |
| `CONFIG_SYS_MALLOC_F_LEN` | `0x40000` | 256 KiB pre-relocation heap |
| `CONFIG_NR_DRAM_BANKS` | `2` | only bank 0 is populated by `dram.c` |
| `CONFIG_SPL_TEXT_BASE` / `CONFIG_SPL_BSS_START_ADDR` | `0x80300000` / `0x80380000` | the SPL runs from on-chip SRAM, not DRAM; irrelevant to this map |
| `CONFIG_K230_BARE_DISP_LOGO` | not set | the logo path is not built today |
| `CONFIG_LAST_STAGE_INIT` | not set | selected by the symbol above once it is |

### 1.6 The vendor logo path's addresses (not built today; recorded because the change enables it)

- `k230_logo.c:206`: `ext4load mmc ${mmc_boot_dev_num}:1 0x1000000 /logo.yuv`
  — **`0x1000000` is inside our kernel Image** (`0x200000..0x3c25000`); the
  logo runs from `last_stage_init()` before `blinux` loads the kernel, so
  the collision is silent: the kernel load simply overwrites the staged
  picture after it has been copied away.
- `k230_logo.c:196-199`: the picture is then copied to
  `env_get_bootm_size()`, which with no `bootm_size` in the environment is
  the size of RAM (`gd->ram_size`, 1 GiB here) — i.e. `0x40000000`, the
  first byte *past* RAM. The SDK's comment says "reserve 1 M for the logo".
  The vendor's path is not a model for where to put a framebuffer.
- LILYGO's RM69A10 branch (`docs/evidence/lilygo-uboot-logo.md`) drops the
  staging copy and loads `/logo.xrgb` directly to `#define
  RM69A10_LOGO_FB_ADDR 0x1f000000UL`, 2 799 104 bytes, with a 4 MiB
  `no-map` reservation in their kernel DTS (patch 0038).

### 1.7 What the kernel does with the memory it is handed

From the same capture (`boot-from-source-cold.txt` lines 159-161 and 193), `[0.000000]`:

```
OF: reserved mem: 0x0000000000000000..0x000000000003ffff (256 KiB) nomap non-reusable mmode_resv1@0
OF: reserved mem: 0x0000000000040000..0x000000000005ffff (128 KiB) nomap non-reusable mmode_resv0@40000
cma: Reserved 512 MiB at 0x000000001e000000 on node -1
Memory: 398428K/1048576K available (14773K kernel code, 9455K rwdata, 24576K rodata, 8520K init, 598K bss, 125860K reserved, 524288K cma-reserved)
```

and at 3.46 s `Freeing initrd memory: 26664K`. `CONFIG_CMA_SIZE_PERCENTAGE=50`
with `CONFIG_CMA_SIZE_SEL_PERCENTAGE=y` (`arch/riscv/configs/k230_defconfig:242-243`
in the pinned tree) is where the 512 MiB comes from. The pool sits at
**`0x1e000000 .. 0x3e000000`**: `memblock` places it top-down in the
largest free range, and the top of that range is the relocated initrd
(§2.2), which is still reserved at that moment.

## 2. Read from the board

### 2.1 `bdinfo` at the U-Boot prompt (task 2.1)

Captured from the physical board before `ums 0 mmc 1` in
`docs/evidence/uboot-usb-host-coexist.txt`. This is the current source for
U-Boot's live placement:

```
DRAM bank start = 0x0000000000000000
DRAM bank size  = 0x0000000040000000
relocaddr       = 0x000000003ff3b000
reloc off       = 0x000000003ff3b000
fdt_blob        = 0x0000000000097020
reserved LMB    = 0x3fb37920..0x3fffffff (0x004c86e0 bytes)
malloc          = 0x3fb39000..0x3ff3b000
sp              = 0x3fb38970
```

The live environment leaves `initrd_high`, `bootm_low`, and `bootm_size`
unset, retains `fdt_high=0xa100000`, and has `loadaddr=0xc000000`. Thus
`bootm` uses its normal highest-free-range placement, bounded by the LMB
reservation above. `fdt addr -c` reported the embedded control FDT at
`0x00097020`; the following `fdt print /memory` failed because no *working*
FDT address was configured. That command failure says nothing about the
presence of the memory node and is not used as memory-map evidence.

The physical reservation starts at `0x3fb37920`, 3 026 bytes above the
current relocated-initrd end in §2.2. It confirms the former inferred
U-Boot bound and places all relocated code, heap, and stack 764 MiB above
the proposed splash range.

### 2.2 `bootm`'s relocation messages (task 2.2)

The current physical-board capture `docs/evidence/uboot-usb-host-coexist.txt`
records:

```
Loading Ramdisk to 3e12f000, end 3fb36d4e ... OK
Loading Device Tree to 000000000a0eb000, end 000000000a0ff681 ... OK
Domain0 Next Arg1         : 0x000000000a0eb000
```

- **Initrd, relocated: `0x3e12f000 .. 0x3fb36d4e`** (27 295 054-byte
  payload). With no `initrd_high`, `bootm` moves it to the highest free LMB
  range, directly below U-Boot's reservation. Its position moves with both
  initrd size and U-Boot's footprint.
- **Device tree, relocated: `0x0a0eb000 .. 0x0a0ff681`** (83 585 bytes).
  `fdt_high=0xa100000` caps it, which is why it lands here rather than at the
  top with the initrd.

The prior cold-boot capture put the initrd at `0x3e135000 .. 0x3fb3fa65` and
is retained as historical evidence. The current range above, captured from
the candidate image, is the one used for the address decision.

### 2.3 The map, with each address classified

`loaded` = written by `blinux` from the card; `relocated` = moved by
`bootm`; `scratch` = written and never read again once boot proceeds;
`kernel-time` = decided by Linux after stage 1 is gone. Ascending.

| from | to | what | class | source |
| --- | --- | --- | --- | --- |
| `0x00000000` | `0x00060000` | OpenSBI fw_jump (text, RW, heap) | loaded by `bootm` from the uImage at `0x8000000`; reserved for the life of the system | §1.4 |
| `0x00200000` | `0x03c25000` | kernel Image + `.bss` | loaded | §1.2 |
| `0x07000000` | `0x070000d3` | `bootargs.txt` | scratch (consumed by `env import`) | §1.1 |
| `0x08000000` | `0x080421d8` | OpenSBI uImage as loaded | scratch after `bootm` copies it to `0x0` | §1.1 |
| `0x08400000` | `0x08411682` | DTB as loaded | scratch after relocation | §1.1 |
| `0x09000000` | `0x0aa07d8e` | current `initrd.uimg` as loaded | scratch after relocation | §1.3 |
| `0x0a0eb000` | `0x0a0ff681` | DTB, relocated; handed to the kernel | relocated | §2.2 |
| `0x0c000000` | — | `CONFIG_SYS_LOAD_ADDR` / `loadaddr` | default target of an address-less load; unused by `blinux` | §1.5 |
| `0x15000000` | `0x15000011` | `force_dtb` probe | scratch | §1.1 |
| `0x1e000000` | `0x3e000000` | Linux CMA pool (512 MiB) | kernel-time; **placed against the relocated initrd** | §1.7 |
| `0x3e12f000` | `0x3fb36d4e` | current initrd, relocated and handed to the kernel | relocated | §2.2 |
| `0x3fb37920` | `0x40000000` | U-Boot relocated code, heap, stack, and LMB reservation | U-Boot only; free once the kernel runs | §2.1 |

Free at every moment of stage 1 *and* untouched by the kernel's own
placement, from the table: **`0x0aa10000 .. 0x0c000000`**,
**`0x0c100000 .. 0x15000000`** and **`0x15010000 .. 0x1e000000`** (the gap
between the loaded initrd's end and the bottom of the CMA pool, less the
two scratch addresses). Everything from `0x1e000000` up is spoken for by
the kernel or by `bootm`; `bdinfo` now gives the exact final U-Boot
reservation rather than an inferred bound.

### 2.4 The splash address (task 2.3 — chosen from the completed map)

The design's starting candidate is LILYGO's `0x1f000000`, 4 MiB. Against
this map it is clear of everything stage 1 loads or relocates, and it is
below U-Boot's relocation, so the two things task 2.3 says would move it do
not. **It fails on the kernel side instead:**

- `0x1f000000..0x1f400000` is inside the observed CMA pool
  (`0x1e000000..0x3e000000`, §1.7). That is grounded in the boot log.
- A `reserved-memory` node with `no-map` there is excluded from
  `memblock` allocation (`drivers/of/fdt.c:479-494`
  `early_init_dt_reserve_memory()` → `memblock_mark_nomap()`;
  `mm/memblock.c:1001-1025` `should_skip_region()` skips `nomap` regions
  for ordinary allocations — pinned tree). The free range CMA is placed in
  is then split: `0x0a100000..0x1f000000` is 335 MiB and
  `0x1f400000..0x3e135000` is 493 MiB, and 512 MiB fits in neither. The
  consequence — `cma: Failed to reserve 512 MiB` and the display driver's
  `dma_alloc_wc` falling back to the page allocator — is reasoning from
  source, **UNVERIFIED on the board**, and the reason not to find out the
  hard way.
- LILYGO's images do not hit this because they boot without an initrd:
  their free range above the hole runs to the top of RAM, `0x1f400000..
  0x40000000` = 524 MiB, and 512 MiB fits by 12 MiB (patch 0038 in
  `docs/evidence/lilygo-uboot-logo.md`). This system pins 26 MiB of initrd
  at the top at exactly the moment CMA is placed.

**Chosen: `0x10000000`, 4 MiB (`0x10000000 .. 0x10400000`).** It is free
in every current row of the table: 86 MiB above the loaded initrd's end,
above `loadaddr` (`0x0c000000`) but clear of it, below the `force_dtb`
scratch address, 764 MiB below U-Boot's exact LMB reservation, and below
CMA. It leaves `0x10400000..0x3e12f000` = 733 MiB for CMA, so source
analysis predicts that the existing pool can remain at `0x1e000000` without
changing the kernel's layout. That prediction requires the reserved-memory
DTS build and a board boot before it becomes an observed result. The
`reserved-memory` node becomes `framebuffer@10000000`; one flake constant
must carry this value to both `CONFIG_K230_BARE_DISP_LOGO_FB_ADDR` and the
DTS.

Not chosen: anywhere above `0x1e000000` (splits CMA, above); the top of
RAM (U-Boot's heap and the relocated initrd are there); `0x0c000000`
(`loadaddr`, a foot-gun); anything below `0x0aa10000` (the loaded initrd
grows into it). 4 MiB rather than the 2 799 104 bytes the buffer needs:
LILYGO's reservation size, and `no-map` regions are best kept
2 MiB-aligned on a Sv39 kernel so the linear map is not fragmented at a
page granularity for 0.5 MiB of savings.

Tasks 2.1 and 2.3 are complete: the `bdinfo` transcript confirms the
U-Boot-side bound and the current `bootm` lines confirm that this range is
not a load or relocation target. This decision does not prove that a future
U-Boot logo can drive the panel; that remains task 3 hardware work.

### 2.5 Linux `no-map` reservation source (task 3.5, build pending)

The DTS source now declares `/reserved-memory/framebuffer@10000000` with
`reg = <0x0 0x10000000 0x0 0x00400000>` and `no-map`. Its address, 4 MiB
size, and unit address are preprocessor definitions derived by
`nix/device-tree.nix` from `nix/boot-splash.nix`; U-Boot uses that same
address attribute for its Kconfig framebuffer symbol. This is source review,
not DTB or hardware evidence: task 3.5 remains open until `.#deviceTree` and
`fdtget` confirm the encoded node. The existing CMA placement at
`0x1e000000` remains a prediction until a physical boot shows the kernel's
reservation and CMA lines.
