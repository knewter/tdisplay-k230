## ADDED Requirements

### Requirement: Stage 1 lights the panel before it loads the kernel

Stage 1 SHALL initialise the panel and put a splash image on it before the
kernel is loaded, from a file it finds on the boot partition by exact name,
and SHALL skip the splash without failing the boot when that file is absent.
Stage 1 owns this. The image format, the filename, the address the image is
scanned out from and the display mode used are properties of the stage 1 this
project builds and SHALL be recorded where the other things stage 1 requires
of the boot partition are recorded.

*Grounding: Canaan's U-Boot overlay ships the mechanism for a different panel
(`board/canaan/common/logo/k230_logo.c`, gated by `CONFIG_K230_BARE_DISP_LOGO`
in `arch/riscv/cpu/k230/Kconfig:35` and run from `last_stage_init()`), and
LILYGO's BSP overlay carries the RM69A10 case of it —
`CONFIG_K230_BARE_DISP_LOGO_RM69A10`, `/logo.xrgb`, 568x1232 XRGB8888 at
`0x1f000000` (an address this change rejects; `docs/evidence/stage1-memory-map.md`), reset on GPIO22 — in
`k230_bsp/overlay/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/board/canaan/common/logo/`
of `Xinyuan-LilyGO/T-Display-K230`, read 2026-09-22. Neither is enabled in
the `k230_canmv_v3_defconfig` this project builds.*

<!-- UNVERIFIED in full: docs/evidence/boot-splash.md and
 docs/evidence/splash-uboot-motion/README.md record this project's source-built
 stage 1 displaying its asset before Starting kernel, including a held U-Boot
 prompt. These are USB-attached warm-reset trials. The specified second-card
 and power-on acceptance procedure remains open. -->

#### Scenario: The boot partition is inspected

- **WHEN** someone lists what stage 1 requires of the boot partition
- **THEN** the splash file is listed by name and format alongside `Image`, the device tree, the initrd and `bootargs.txt`, with the address it is scanned out from

#### Scenario: A board boots with the splash file removed

- **WHEN** the file is deleted from the card and the board is powered on
- **THEN** the console shows stage 1 noting the missing file and continuing, and the kernel boots

### Requirement: Every address stage 1 loads into is recorded in one map

The project SHALL keep one document listing every physical address stage 1
loads something to or hands to the next stage — the kernel image and its
extent, the initrd and where `bootm` relocates it, the device tree as loaded
and as OpenSBI passes it on, OpenSBI itself, the environment import buffer,
U-Boot's own relocated code and heap, and the splash buffer — with the size
of each and the source it was read from. Any new address stage 1 uses SHALL
be chosen against that map and added to it. The splash buffer SHALL be
reserved from the kernel through the device tree, and the address SHALL be
written in exactly one place in the flake from which both stage 1 and the
device tree take it.

*Grounding: the map does not exist, and its absence has already cost a
corrupted kernel. `docs/evidence/opensbi-fdt-lands-in-kernel-image.md` proves
on the board that OpenSBI copies the device tree to `0x2200000`, 32 MiB into
the 57 MiB kernel at `0x200000`, and that the board survives only because
that lands in `.BTF`. The vendor's logo path stages its picture at
`0x1000000` (`k230_logo.c:206`), also inside our kernel. The addresses known
so far, from `firmware/stage1/tdisplay.env` and
`docs/evidence/stage1-emergency-mode.md`: `Image` at `0x200000`,
`bootargs.txt` at `0x7000000`, OpenSBI at `0x8000000`, the DTB at
`0x8400000`, the initrd at `0x9000000`, `CONFIG_SYS_LOAD_ADDR=0xc000000`; RAM
is 1 GiB and the kernel's CMA is half of it (`k230_defconfig`,
`CONFIG_CMA_SIZE_PERCENTAGE=50`).*

*Grounding: `docs/evidence/stage1-memory-map.md` §§2.1–2.4 records physical
`bdinfo`, U-Boot relocation/LMB/malloc/stack ranges, actual `bootm` initrd and
DTB relocation messages, and the resulting splash address decision. The map
classifies loaded, relocated, scratch, U-Boot, and kernel-time ranges.*

#### Scenario: A new load address is needed

- **WHEN** someone needs stage 1 to load something new
- **THEN** the map says what is free, and the addition is recorded there before it reaches the environment

#### Scenario: The kernel is inspected for the splash region

- **WHEN** someone reads `/proc/iomem` or the device tree on the running board
- **THEN** the splash buffer appears as a reserved region at the address the map records, and the kernel has not allocated from it

### Requirement: Stage 1 tells the kernel whether it lit the panel

Before handing over, stage 1 SHALL record in the device tree it passes to the
kernel whether the panel is initialised and scanning out, and SHALL record it
only when that is true. This is a fact about the boot in progress, not about
the board, so it SHALL NOT be a static property of the device tree source.

*Grounding: the vendor U-Boot already edits the device tree before boot —
`ft_board_setup()` in `board/canaan/common/k230_board_common.c:574` rewrites
the memory node, and `board_fdt_chosen_bootargs()` in `k230_img.c:110`
rewrites `/chosen/bootargs` (`docs/evidence/stage1-emergency-mode.md`). The
flag is one more property in the same place. LILYGO's kernel patch 0051 keys
the kernel's behaviour on a static `canaan,preserve-boot-splash` instead;
that design leaves the panel dark on any boot where the logo failed to
load.*

*Grounding: `docs/evidence/splash-initial-scene-ready/inspection.txt` records
`/chosen/canaan,stage1-splash` present on the splash boot;
`docs/evidence/splash-preserve-trial/no-logo-inspection.txt` records
`NO_SPLASH_FLAG` when the logo is absent. The same captures show the
corresponding no-fbdev and full-initialization/fbdev paths. These are physical
serial-initiated warm boots; they do not claim battery-only operation.*

#### Scenario: The running device tree is read after a splash boot

- **WHEN** stage 1 lit the panel
- **THEN** `/proc/device-tree/chosen` on the booted board carries the flag

#### Scenario: The running device tree is read after a boot without a splash

- **WHEN** stage 1 did not light the panel
- **THEN** the flag is absent, and the kernel initialised the panel itself

## MODIFIED Requirements

### Requirement: Stage 1 hands control to our kernel

*Grounding: observed on hardware. The vendored chain loaded our kernel, our
device tree and our initrd from the card and reached userspace: `uname -a` on
the board reports `Linux nixos 6.6.36 #1-NixOS ... riscv64`
(`docs/evidence/hardware-userspace.md`). Stage 1 itself was not modified; the
two things it required of us were recorded rather than rediscovered — the
literal filenames its `blinux` variable `ext4load`s, and the fact that the
kernel command line comes from the U-Boot environment and not from
`/chosen/bootargs` (`docs/evidence/stage1-emergency-mode.md`).*

*Since then stage 1 has been modified twice, and deliberately: its
environment loads `bootargs.txt` and the initrd and moved OpenSBI and the
device tree above the kernel (`docs/blob-inventory.md`, row A3), and
`every-blob-is-built-from-source-or-named` builds it from source. The clause
that forbade modifying it is therefore removed. What survives is the
obligation to record what stage 1 requires of us.*

Stage 1 SHALL load the kernel, device tree and initrd this project builds
from the SD card. Where stage 1 requires a particular filename, location,
image format or load address, that requirement SHALL be recorded as a
property of the stage 1 this project builds rather than discovered again each
time. Where stage 1 has already lit the panel, it SHALL hand the kernel a
running display and the fact that it is running, and the kernel SHALL be
able to tell that boot from one where it must light the panel itself.

#### Scenario: A built system is placed on a card and the board is powered on

- **WHEN** the board boots with our image on its SD card
- **THEN** stage 1 loads our kernel, and the console shows it starting

#### Scenario: The panel is lit when the kernel starts

- **WHEN** stage 1 lit the panel before loading the kernel
- **THEN** the panel is still showing stage 1's image when the kernel reaches userspace, and the kernel log says it left the panel as it found it
