# image/boot-chain Specification

## Purpose
Defines what executes before our kernel on this board, which parts are
vendored, and how control reaches the system we built.

## Requirements

### Requirement: Stage 1 is built from source this project can read

The boot chain before our kernel — U-Boot SPL, U-Boot 2022.10 and its
environment — SHALL be produced by this project from source, pinned by the
hash of that source rather than of the binary, and SHALL NOT be carried in
the repository as a committed binary. The packaging steps that turn the
compiled output into what the BootROM will load SHALL be expressed in the
flake rather than in a shell script run by hand.

This reverses the previous requirement, which held that stage 1 SHALL NOT be
built from source. The reason it held was a belief that the source was
unavailable or the build unreasonable. Both are false: the source is open and
on disk, and every packaging step has been reproduced with stock tools.

*Grounding: `docs/blob-inventory.md` §A1–A2 and §D. The sources are U-Boot
2022.10 upstream, sha256
`50b4482a505bc281ba8470c399a3c26e145e29b23500bc35c50debd7fa46bdf8`, plus
Canaan's rsync overlay applied by `UBOOT_OVERLAY_DIRS` in the SDK's
`buildroot-overlay/boot/uboot/uboot.mk`, both open. Measured 2026-09-20:
nixpkgs `ubootTools` reproduces the committed `env.env` byte for byte, and
nixpkgs `gzip` plus `mkimage` plus the U-Boot tree's own
`firmware_gen_no_securiy.py` reproduce both committed firmware images byte for
byte from the compiled U-Boot. `readelf -A` reports the compiled SPL as
`rv64i2p1_m2p0_a2p1_c2p0_zicsr2p0_zifencei2p0_zmmul1p0` — no vendor ISA — and
the T-Head cache operations are hand-encoded as `.long` words, so the vendor
toolchain is not required to assemble them. Built 2026-09-22 and recorded in
`docs/evidence/stage1-from-nix.txt`: `nix build .#uboot-k230` compiles
U-Boot and its SPL with nixpkgs GCC 15.3.0 (SPL 222 816 bytes against the
524 288-byte `CONFIG_SPL_SIZE_LIMIT`; `readelf -A` reports
`rv64i2p1_m2p0_a2p1_c2p0_zicsr2p0_zifencei2p0_zmmul1p0_zaamo1p0_zalrsc1p0_zca1p0`,
no vendor extension; zero `th.` mnemonics), `nix build .#opensbi-k230`
compiles OpenSBI 1.4 with the overlay under a GCC 13 pin, and `nix build
.#stage1` wraps both into the five files the card carries, with the `K230`
magic, a CM byte of `0x09`, and the environment's `mkenvimage` step
reproducing the SDK default byte for byte
(`f522ba13aa8a2e643e61e4fde9f2babb604e86b2f38a487be37c7bdc0b14c957`).
One deliberate departure from the vendor's build: the vendor's OpenSBI is
compiled with `FW_JUMP_FDT_ADDR = FW_TEXT_START + 0x2200000`, so `fw_jump`
copies the device tree to `0x2200000` — inside the kernel image loaded at
`0x200000`, in its `.BTF` section, as
`docs/evidence/opensbi-fdt-lands-in-kernel-image.md` reads back from
`/sys/kernel/btf/vmlinux` on the board. The OpenSBI this project builds
leaves `FW_JUMP_FDT_ADDR` undefined and passes the device tree through where
`bootm` placed it; `docs/evidence/opensbi-fdt-passthrough.txt` is the
`fw_next_arg1` disassembly before and after.*

*Grounding, on hardware: `docs/evidence/stage1-from-source.txt`. On
2026-09-22 the board booted the pure `nix build .#sdImage` to the NixOS
login prompt with no panic and no emergency shell, and hashed its own
card's raw slots from Linux: SPL at 1 MiB `fe3d537f…`, U-Boot at 2 MiB
`805bd543…`, `/boot/fw_jump_add_uboot_head.bin` `9627edbe…` — the bytes
`result-stage1/SHA256SUMS` lists for this flake's output. The BootROM ran
this SPL, it trained the DRAM and ran this U-Boot, and U-Boot ran this
OpenSBI; nothing vendor-compiled was on that card.
`docs/evidence/boot-from-source-cold.txt` is a second capture from power-on:
bootm's `Loading Device Tree to 000000000a0eb000` followed by this flake's
OpenSBI banner reporting `Platform Name : LILYGO T-Display-K230` and
`Domain0 Next Arg1 : 0x000000000a0eb000` — the device tree handed on where
`bootm` put it, not at `0x2200000`. What neither transcript holds: the SPL's
`PMU Major Msg:` lines and the `U-Boot 2022.10` banner. The CH342 console
bridge loses power with the board and takes about 3.4 s to re-enumerate,
and stage 1 prints inside that window; the cold capture's `--- port lost`
/ `--- port opened` markers at 10.7 s and 14.1 s bracket it. The boot is
observed; the banners are inferred from it.*

#### Scenario: Someone needs to change how the board boots

- **WHEN** a person wants the boot command, a memory timing, or the environment to be different
- **THEN** the thing they edit is a file in this repository, and the change reaches the card by rebuilding

#### Scenario: The vendored firmware is inspected

- **WHEN** someone asks where the bootloader on the card came from
- **THEN** the flake names its sources and their hashes, and the build that turns them into what the card carries is the flake's own

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

### Requirement: The hardware boot path differs from the emulated one, and that difference is recorded

*Grounding: `docs/evidence/boot-path-differences.md` records the comparison,
started during `a-riscv-nixos-closure-cross-builds`. Two differences are
already observed rather than anticipated: QEMU's `k230` machine models no
block device, and it generates no FDT at all (`dumpdtb` answers "This machine
doesn't have an FDT").*

Under QEMU the kernel is loaded directly; on hardware it is loaded by vendored
U-Boot. The project SHALL record what differs between the two paths, so that a
failure on hardware after a success under emulation is diagnosed against a
written expectation rather than from memory.

#### Scenario: An image boots under QEMU but not on the board

- **WHEN** the two paths disagree
- **THEN** the recorded differences are the first place to look, and they are specific enough to be checked one at a time

### Requirement: What stays opaque inside stage 1 is named

Building stage 1 from source SHALL NOT be treated as making it transparent.
The parts of it that remain unreadable SHALL be listed by name, size and
sha256, with their location inside the produced binary, so that compiling
them ourselves does not remove them from view.

*Grounding: `docs/rtsmart-boot-log.txt` records this board's SPL printing
`PMU Major Msg: End of CA training` through `Firmware run has completed` —
the Synopsys DDR PHY training firmware running before anything else. It has no
source: it reaches us transliterated into 16 384 `reg_write()` calls in
Canaan's `lpddr4_init_32_swap_2667.c`, which the SDK's `ddr.sh` turns back
into an array at build time. Measured 2026-09-20 and recorded in
`docs/blob-inventory.md` §A5–A6: that image is 32 768 bytes of instruction
memory, sha256
`517aa534255e88c941882be40f5e5735349cd1e3b144b536155e51bdc6309c8b`, plus 1 660
bytes of data memory, and it sits verbatim at offset `0x1fc74` of the
vendor-compiled SPL — 15.9 % of it. In the SPL this flake compiles the same
bytes, same hashes, sit at `0x23f80` of `u-boot-spl.bin` and `0x24184` of
`fn_u-boot-spl.bin` — 14.7 % of a 222 816-byte SPL — measured 2026-09-22 and
recorded in `docs/evidence/stage1-from-nix.txt`. Compiling it moved it; it
did not shrink it.*

#### Scenario: A reader asks whether stage 1 is now fully open

- **WHEN** stage 1 is built from source
- **THEN** the answer is "all but the memory training firmware", and that firmware is named, sized, hashed and located rather than described as "a blob inside SPL"

### Requirement: No vendor executable runs in the firmware build

Producing anything that goes on the card SHALL NOT require executing a binary
this project cannot read. Where the vendor's own build does so, the project
SHALL substitute a readable equivalent and record the evidence that the
substitution changes nothing.

*Grounding: `docs/blob-inventory.md` §A4. The SDK's
`buildroot-overlay/board/canaan/k230-soc/post-image.sh` runs
`tools/k230_priv_gzip`, a stripped x86-64 ELF, to compress U-Boot. Its strings
identify it as GNU gzip 1.6 — the FSF copyright, `Written by Jean-loup
Gailly.`, `bug-gzip@gnu.org`, and gzip's unmodified option table
`ab:cdfhH?klLmMnNqrS:tvVZ123456789`, in which `-n8` is the ordinary `-n -8`.
Measured 2026-09-20 on the SDK's own 693 576-byte `u-boot.bin`: nixpkgs gzip
1.14 produces output identical to the vendor binary at every level the SDK
falls back through — `docs/evidence/gzip-equivalence.txt` is that
measurement, re-run 2026-09-22 with both sha256 sets at levels 4 through 9.
What is actually vendor-specific is a one-byte `sed` on the following line,
flipping the gzip header's CM field to `0x09` so that the SPL's
`k230_priv_unzip()` uses the SoC's hardware decompressor; `nix/stage1.nix`
carries that `sed`, and `docs/evidence/stage1-from-nix.txt` records the
packaging over the vendor-compiled U-Boot reproducing the on-card
`fn_ug_u-boot.bin` and `fn_u-boot-spl.bin` byte for byte with nixpkgs tools
alone, and exactly which 40 bytes the `sed` changes.*

#### Scenario: The firmware build is audited

- **WHEN** someone asks what code ran to produce the bytes on the card
- **THEN** every program involved is one whose source is available, and the vendor binary that used to run is recorded as replaced rather than merely unused

### Requirement: Stage 1 offers the card to a host over USB

Stage 1 SHALL be able to present the TF card to a host computer as a USB mass
storage device, over the data USB-C connector, without the card leaving the
board. Writing an image SHALL NOT require a person to move the card to a
reader.

Which connector and which controller this uses is a property of the board and
SHALL be recorded rather than rediscovered: the data USB-C is `J3`, it is
wired to the SoC's `usbotg0`, and the charging USB-C `J2` carries only the
CH342 console bridge and cannot be used for this.

*Grounding: `docs/uboot-ums.md` §2. `repo/schematic/T-Display
K230_V1.0_NEW.pdf` routes `USB0_P`/`USB0_N` to `J3` pins A6/A7/B6/B7 with
`USB0_ID` and `USB0_VBUS`, and `USB_P`/`USB_N` on `J2` to the CH342.
`docs/evidence/hardware-boot.txt` agrees: Linux registers `dwc2
91500000.usb` as bus 1 with nothing attached and `dwc2 91540000.usb` as bus 2
carrying an onboard `Realtek USB 10/100 LAN`. So does U-Boot itself:
`docs/evidence/uboot-ums-hardware.txt`, at the board's own `K230#` prompt
on 2026-09-22, shows `dm tree` with exactly one `snps,dwc2` node bound —
`usb-otg@91540000`, to the host driver — and `usb start; usb tree` finding
the RTL8152 behind it, while `usb-otg@91500000` is absent because the
vendor device tree disables it. The gadget configuration is not speculative
— Canaan ships one for this SoC in the same U-Boot tree, as
`k230_canmv_burntool_defconfig` — and this project's build of it
(`nix/uboot-k230-ums.config`, `docs/evidence/uboot-ums-build.txt`) puts
`ums` in the binary and enables `usb-otg@91500000` as a peripheral.*

*Grounding, on hardware: `docs/evidence/uboot-ums-enumerate.txt`, session 5,
2026-09-22. With the card in the slot and the ums stage 1 on it, `ums 0 mmc
1` at the `K230#` prompt made this host log `usb 3-4: new high-speed USB
device ... idVendor=29f1, idProduct=0230 ... Product: USB download gadget,
Manufacturer: U-Boot` and attach `/dev/disk/by-id/usb-Linux_UMS_disk_0-0:0`
as a 249 872 384-sector removable disk — the size `mmc info` reports for the
card and the count `ums` printed — with the image's `K230_BOOT` and
`NIXOS_SD` partitions visible to `lsblk`. 350 046 bytes read back from its
2 MiB offset hash to `bd562f2b…`, the `fn_ug_u-boot.bin` of that build.
Four earlier sessions had failed with the core's registers showing VBUS
valid and a bus reset received: the cable's far end was not this machine,
which a phone on the same cable then proved. Nothing was written.*

#### Scenario: A rebuilt image is written to the board

- **WHEN** a person has built a new image and the board is sitting at its bootloader prompt with a cable to the data USB-C
- **THEN** the card appears on the host as a block device, the image is written to it, and the board boots the new image after a reset — with nobody having touched the card

#### Scenario: Someone reaches for the wrong cable

- **WHEN** the only cable attached is the one that gives the two console ports
- **THEN** the documented answer is that this connector cannot carry the card, and which one can

### Requirement: The card is the only thing that has to be right to boot

The project SHALL record which boot media this board can start from, and SHALL
keep the recovery procedure for an unbootable stage 1 written down and true.
A change to stage 1 SHALL NOT be able to put the board beyond recovery by
rewriting its card.

*Grounding: `docs/uboot-ums.md` §6. The schematic's strap table reads `BOOT0=0,
BOOT1=0` SPI Nor / `BOOT0=0, BOOT1=1` eMMC / `BOOT0=1, BOOT1=0` SPI Nand /
`BOOT0=1, BOOT1=1` SD Card, and the board sits at `1,1`. No SPI NOR or NAND
part appears anywhere in the schematic — the `OSPI_*` pins carry `IO16_MOSI`
and `IO19_BUSY`, the LoRa radio. `docs/findings.md` records MMC0 as the
RTL8189FTV SDIO radio and MMC1 as the TF card, so there is no eMMC. LilyGO's
own product table lists this board's `FLASH` as "SD Card". A third-party wiki
claiming onboard SPI NOR also claims the Wi-Fi is an ESP32-S3 co-processor,
which `docs/findings.md` already records as contradicted by the schematic.*

#### Scenario: A stage 1 is built that does not boot

- **WHEN** the board is powered on and prints nothing at all
- **THEN** the card is moved to a reader, a known-good image is written, and the board boots — with no JTAG, no soldering and no vendor tooling

#### Scenario: Someone asks whether it is safe to experiment with the bootloader

- **WHEN** a change to stage 1 is proposed
- **THEN** the answer cites which boot media this board has, rather than assuming the SD card is the only one

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
 and power-on acceptance procedure moved 2026-10-11 to
 `the-mainline-kernel-keeps-the-boot-splash`, together with the mainline device
 tree reservation this requirement needs on the board's current kernel. -->

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
