## Layers

Everything here lands in **stage 1** (SPL, U-Boot proper, OpenSBI) and the
**Nix** derivations that build and package it. The kernel, device tree and
userspace are untouched. Stage 1 also owns the splash and its reserved-memory
handoff; the kernel side of that contract does not change.

## Research record (2026-10-30)

### Upstream U-Boot

Newest stable: **v2026.10** (tag `5508406582`); master is `v2027.01-rc1`
(`dfcfc4c9f7`). K230 support has been upstream since **v2026.01**
(`riscv: cpu: k230: Add support for Canaan Kendryte K230 SoC` `78d9ce3e36`,
`riscv: canaan: k230_canmv: Add initial support` `9c402a54df`, Junhui Liu,
carrying Yangyu Chen's dts). Read from the tree, not from docs:

| Piece | Upstream v2026.10 | Gap for this board |
| --- | --- | --- |
| Board/SoC | `configs/k230_canmv_defconfig`, `board/canaan/k230_canmv/`, `arch/riscv/cpu/k230/` (`dram.c`, `cpu.c`, both nearly empty), `arch/riscv/dts/k230.dtsi`, `k230-canmv.dts`, `k230-u-boot.dtsi` | Our board is T-Display-K230 (1 GiB, RM69A10, GT9895): new dts and defconfig. Upstream dts says 512 MiB and `TEXT_BASE=0x0`. |
| Run model | **U-Boot proper only.** `doc/board/canaan/k230_canmv.rst`: "we rely on vendor u-boot-spl to initialize the ddr and load the u-boot image", written to the card at 2 MiB wrapped with the vendor `firmware_gen.py` header. binman emits `u-boot-gz.img` (legacy uImage, gzip, `-a/-e TEXT_BASE`). | This is exactly stage a. No SPL, no DDR training, no SD boot of its own. |
| UART | `snps,dw-apb-uart` -> ns16550, 115200 | None; vendor `ns16550.c` fractional-divisor change is not needed. |
| Timer/IRQ | `RISCV_TIMER`, `canaan,k230-clint`/`plic`, `syscon-reboot` at `0x91102000+0x60` | Vendor `harts_early_init` enables the mtimer clock gates (`0x91108020/30`) and the STC (`0x91108000`) first; upstream assumes SPL did. Verify, else port. |
| USB | `canaan,k230-otg` + `snps,dwc2`, **host only** (`usb1`, RTL8152 via `usb start`, in the upstream boot log). Linux binding `canaan,k230-usb-phy` exists in `dts/upstream/Bindings`, no U-Boot driver. | Gadget/`ums` on `usb0` (J3): vendor `dwc2_udc_otg.c` PHY pull-down handling (`USB0_TEST_CTL3` bits 8/9 at `0x9158507c`) and `harts_early_init` PHY control writes (`0x91585000+0xb0..0xbc`). Our existing patches 0001-0003 (usbotg0 peripheral, host/gadget bind split) are largely made unnecessary by upstream's `canaan,k230-otg` compatible. |
| MMC | **None for K230.** `drivers/mmc/snps_sdhci.c` (`MMC_SDHCI_SNPS`, DWC MSHC, TH1520) exists. | Vendor's own `snps_sdhci.c` (261 lines) adds the K230 PHY pad/delay setup (`0x300..0x326`) that mainline's lacks; Linux has a v5 series "Add SDHCI support for Canaan K230 SoC" (Jiayu Du, March 2026, linux-riscv) to use as register reference. Plus vendor `sdhci.c` hunks (`SDHCI_PROG_CLOCK_MODE`, 1.8 V flag, 4-bit cap removal) and `SD0_CTRL` bits (`0x91585000`). |
| Clocks/resets | **No K230 clock or reset driver in U-Boot** (Linux 7.3 has `COMMON_CLK_K230`, `RESET_K230`). Dtsi uses fixed clocks. | Stage a follows the vendor: fixed-clock nodes, clocks left as SPL/BootROM set them. A clock/reset driver is a later, optional port from Linux. |
| Pinctrl | None (Linux `PINCTRL_K230`; binding vendored in `dts/upstream`). | Vendor uses `pinctrl-single` over `0x91105000` with a 64-pin table in `k230_canmv_v3.dts`. Stage a keeps that table; the 2022.10 `pinctrl-single` casts are not needed on 2026.10. |
| Cache | `SYS_CACHE_THEAD_CMO` (`arch/riscv/lib/thead_cmo.c`, `dcache.ipa/cpa`), generic Zicbom. `icache_enable()`/`dcache_enable()` are empty weak stubs. | Vendor `cache.c` enables I/D caches through `MHCR`/`MCOR`/`MCCR2`/`MHINT`/`SMPEN` and issues `l2cache.ciall` (`.long 0x0170000b`). Port that small part (about 120 of its 333 lines); take range operations from `thead_cmo.c`. |
| SPL/DDR | **None** for K230. Sibling `arch/riscv/cpu/th1520/` shows the upstream pattern (SPL, vendor DDR blob via binman). | Whole of stage b. |
| Display | None. | Vendor `board/canaan/common/logo/*` (3 274 lines) plus our patches 0004/0005 (780 lines); port as board code. |
| Cyclic | Native (`CONFIG_CYCLIC`, `cyclic_register()`). | The Game of Life change (worktree `agent-a01598cc868d1ff20`, `nix/uboot-k230-life/`, `src/boot_frame.*`) hand-backports a minimal cyclic into 2022.10; on 2026.10 its callers move to the native API. Not edited here. |

No mailing-list series for U-Boot K230 SPL, DDR or MMC was found (lore blocks
scripted access; a web search found only the Linux SDHCI series above).
Out-of-tree there is nothing newer than Canaan's SDK; `kendryte/k230_sdk`'s
U-Boot is the same 2022.10 family.

### Upstream OpenSBI

Newest release **v1.9** (2026-07-01). It matches `canaan,kendryte-k230` in
`platform/generic/thead/thead-generic.c` with the T-Head PMU quirk only
(commit `019a8e6`). Our 1.4 build exists because Canaan's overlay *also*
clears `MXSTATUS.MAEE` for this compatible; v1.9 has no MAEE handling
(`git grep MAEE v1.9` is empty). The vendor delta is nine small files
(`nix/opensbi-k230.nix` lists them; `thead_c9xx_disable_maee.c` is 14
lines). Forward-port is a patch of roughly 40 lines against `thead-generic.c`
plus `c9xx_encoding.h`; the rest of the vendor overlay (`sbi_hart.c`,
`sbi_init.c`) is 1.4-specific plumbing to re-derive, not copy.
The `FW_JUMP_FDT_ADDR` departure (`docs/evidence/opensbi-fdt-passthrough.txt`)
carries over unchanged.

### What the vendor 2022.10 overlay does that must be kept

Sized from `nix/k230-sdk-src.nix` at `1104236`, diffed against vanilla 2022.10:

| Vendor piece | Size | Disposition |
| --- | --- | --- |
| DDR init (`ddr.sh`, `ddr_2d.sh`, 16 384-write C tables, `k230_spl.c`) | ~140+178 shell, ~18 700 lines data | stage b |
| SPL image loader (`k230_img.c`, 873) | 873 | SPL only: stage b |
| `unzip.c` hardware ugzip (362) + `lib/gunzip.c` CM-byte hook | 362+2 | SPL decompresses U-Boot, so **stage a needs none of it**; the existing packaging keeps `CM=0x09` |
| `harts_early_init` (clocks, PMP, USB PHY, SD ctrl) in `cpu.c` | ~60 | stage a: board `early_init` |
| `cleanup_before_linux` cache/CSR dance | ~30 | stage a |
| `cache.c` | 333 | stage a: enable/disable subset |
| `snps_sdhci.c` + 3 `sdhci.c`/`mmc.c` hunks | ~290 | stage a: PHY part as a K230 variant of upstream `snps_sdhci.c` |
| `dwc2*.c`, `dwc2.h` | ~75 | stage a: re-derive against 2026.10's driver |
| `k230_board_common.c` (590): env location, `k230_set_dtb`, `k230_gpio`, wifi reset, fdt fixup (our patch 0005) | ~590 | stage a, minus the burn/DFU/boot commands we do not use |
| logo + patches 0004/0005 | ~3 300+780 | stage a |
| `k230_board_common.c` DFU/burn, `dfu_otp.c`, `puf_fw/*`, SPI NOR/NAND, PWM, `designware_spi.c`, `env/spinand.c` | thousands | **dropped**: nothing on this board's boot path uses them (SD only; `quick_boot=false`; `tdisplay.env`'s `blinux` uses `ext4load`, `env import`, `bootm`) |

## Stage plan

All stages leave SPL slots at `0x100000` and `0x180000`, the environment at
`0x300000`/`0x320000` and the `/boot` ext4 partition as they are unless the
stage says otherwise (layout: `nix/stage1.nix` `layout`).

### Stage a0 - run the modern U-Boot from RAM (no write)

Load the new U-Boot binary from the card's `/boot` (or over ums-less
means: the running 2022.10 U-Boot can `ext4load` it) to a RAM address, quiesce
caches the way the vendor `k230_boot_uboot_uimage` does, and `go` to it. A
power cycle or reset returns to the 2022.10 on the card. Nothing on the card
changes except one extra file on `/boot` (a write through Linux, not boot
firmware). The binary is the same image as stage a; it is linked at
`TEXT_BASE=0x0` and relocates, so it is loaded at a scratch address only if
position-independent loading is proven by the host build (`readelf`/`PIE`
check); otherwise a0 is replaced by stage a with the card-reader rollback.
Open question recorded, not assumed: the RAM-trial needs the old U-Boot to
leave `0x0` unused after its own relocation, which task 3.1 checks from the
2022.10 `bdinfo` on the board (read-only).

- Proof: console transcript (CH342 console capture) showing the
  `U-Boot 2026.10` banner, DRAM size, `mmc list`, `mmc info`, `ext4ls mmc 1:1`,
  `ums 0 mmc 1` enumerating on the host, and a full `blinux` run to the NixOS
  login. Class: real board, console.
- Recovery: power cycle. Evidence class of the recovery: expected, verified by
  doing it.

### Stage a - modern U-Boot in the 2 MiB slot

Writes only the U-Boot slot: `fn_ug_u-boot.bin` at byte offset `0x200000`
(2 MiB), size must stay below 1 MiB (the next slot, the environment, starts at
`0x300000`; the build asserts it). SPL (both copies), environment (both
copies), `/boot`, rootfs and OpenSBI are preserved. Procedure and rollback are
in task group 4 and are reproduced in the handoff report before any write.

- Proof: cold-boot console showing `U-Boot 2026.10`, the splash lit, `ums 0 mmc 1`
  on J3 enumerating at 29f1:0230, `blinux` reaching userspace with the kernel
  log still reporting the panel left as found, and `sha256sum` of the raw
  2 MiB slot read back through ums equal to the build's `SHA256SUMS`.
- Recovery ladder, cheapest first:
  1. New U-Boot runs and `ums` works: host rewrites the saved 2022.10 slot
     image (`dd ... seek=2M`), verified by read-back.
  2. New U-Boot runs, `ums` does not: `mmc write` the saved 2022.10 slot image
     from `/boot` (kept there as `fn_ug_u-boot.2022.10.bin`) at sector `0x1000`.
  3. New U-Boot does not reach a console: pull the card, write the slot in a
     card reader. This is the proven floor (`docs/uboot-ums.md` section 6).
  4. BootROM USB recovery with SW3 held is **UNVERIFIED**
     (`openspec/changes/characterise-bootrom-usb-recovery`); it is not relied
     on.
- Failure mode this stage cannot hide: the vendor SPL jumps to `0x0` and runs
  whatever it decompressed; a bad U-Boot can hang silently with the panel dark
  (the SPL lights nothing). That is why a0 and card-reader access come first.

### Stage b - a modern SPL with DDR training

Port `k230_spl.c`, `ddr.sh`/`ddr_2d.sh`, the 16 384-write `lpddr4_init_32_swap_2667.c`
(vendored data, named in `docs/blob-inventory.md`), the MMC-at-SPL path
(`snps_sdhci` SPL variant), the ugzip hardware decompression of U-Boot proper
(or plain gunzip, slower, correct) and the BootROM `K230` header packaging
into an upstream-style `SPL`, using `th1520` as the structural reference.
SPL stays below `CONFIG_SPL_SIZE_LIMIT=0x80000`; DDR size 1 GiB.

- Gate: **the BootROM recovery route must be proven first** (task 6.1, it is
  `characterise-bootrom-usb-recovery`'s group 2), because a bad SPL leaves a
  board that the BootROM will not hand to anything we control. Until then
  stage b is host build and QEMU-free review only.
- Proof: cold-boot console (the CH342 bridge loses power with the board and
  re-enumerates for about 3.4 s, so the SPL banner and `PMU Major Msg:` lines
  need a UART tap or the `tools/capture-boot.py` reopen logic, as in
  `docs/evidence/boot-from-source-cold.txt`; if that fails, a warm `reset` from
  U-Boot reruns the SPL while the console stays up), DRAM size 1 GiB, a
  `memtest`/`mtest` pass, and a stage-a-equivalent boot to the shell.
- Recovery: write the first SPL copy only (`0x100000`), keep the second
  (`0x180000`) as the vendor-derived one **if** the BootROM falls back to it
  (UNVERIFIED, task 6.2 measures it on a disposable card); otherwise card
  reader.

### Stage c - modern OpenSBI

`fw_jump.bin` lives as a **file** on the `/boot` ext4 partition
(`/fw_jump_add_uboot_head.bin`), not in a raw slot. Replace OpenSBI 1.4 with
v1.9 + the MAEE patch. Rollback is renaming a file on `/boot` (reader, or from
Linux, or `ext4load`/`ext4write` is unavailable so reader or ums).

- Proof: console banner `OpenSBI v1.9`, `Platform Name : LILYGO T-Display-K230`,
  `Domain0 Next Arg1` equal to the `bootm` DTB address, a read of
  `mxstatus` (via the SBI-side trace or the existing T-Head probe,
  `nix/c908-bitmanip-probe.nix` pattern) showing `MAEE=0`, and the kernel
  booting to the shell with the compositor running.
- Recovery: put the previous `fw_jump_add_uboot_head.bin` back.

## Decisions

- **Base on v2026.10, not master.** It is the newest stable release and
  already carries K230 support. Re-pin when v2027.01 lands.
- **Keep the proven packaging.** `nix/stage1.nix`'s `packagingOf` (gzip -n -8,
  CM byte `0x09`, `mkimage -C gzip -a 0 -e 0 -n uboot`, K230 header with
  `firmware_gen_no_securiy.py -n`) is reused unchanged over the modern
  `u-boot.bin`. Upstream's binman `u-boot-gz.img` is *not* used: it does not set
  the CM byte and needs the vendor `firmware_gen.py` with crypto dependencies.
  The one file this change keeps from the SDK at stage a is the header
  generator script (113 lines of Python, text).
- **Out-of-tree board in our repo, not a fork.** The derivation unpacks the
  upstream tarball and applies reviewable patches from
  `nix/patches/uboot-modern/`, same style as `nix/patches/uboot-k230/`. New
  board files live in `nix/uboot-k230-modern/` and are copied in. Vendor
  files taken as-is (logo, `snps_sdhci` PHY tables) are copied from
  `nix/k230-sdk-src.nix` at build time so the BSD-2 licence text travels with
  them and nothing vendor is committed.
- **Environment compatibility.** `firmware/stage1/tdisplay.env` is reused so
  `bootcmd=run blinux` keeps working; commands it uses that modern U-Boot
  lacks (`k230_set_dtb`) are ported as a small board command (the `lcd_dtb`
  / `hdmi_dtb` / `force_dtb` choice) or the environment is migrated with a
  changed variable and a documented reason. `env import -t`, `ext4load` and
  `bootm` exist upstream.
- **Rejected: bring up SPL first (b before a).** Highest brick risk, needs the
  unproven BootROM recovery, and delivers nothing the user can see.
- **Rejected: wait for upstream SPL/MMC.** No series exists to wait for.
- **Rejected: run the kernel without U-Boot proper.** Loses `ums`, the splash
  hook and the environment flow.
- **Rejected: copy upstream `k230_canmv_defconfig` unmodified.** It has no MMC,
  no gadget, 512 MiB, no cache enable; it boots to a prompt over a
  vendor-initialised SoC, nothing more.
- **Uncached start is acceptable until the cache port is proven.** If the
  MHCR enable sequence misbehaves in stage a0, U-Boot runs with caches off
  (slow splash and ums, correct otherwise) and the cache port becomes its own
  task; this is recorded, not hidden.

## Risks

- Silent hang with a dark panel (stage a). Mitigated by a0, by the saved
  rollback image on `/boot`, and by keeping a card reader at hand.
- DDR size: vendor detects size by pattern probe (`detect_ddr_size`);
  upstream takes it from the DT. The board dts states 1 GiB; a wrong value
  is caught by a0 (`bdinfo`).
- DMA coherency with `dma-noncoherent` and caches on: sdhci SDMA/ADMA and
  dwc2 DMA need explicit flush/invalidate; wrong ops corrupt reads silently.
  Proof is a checksummed read (`ext4load` + `crc32`) twice, not a single boot.
- The Game of Life and splash changes land on 2022.10 first; rebasing them is
  part of this change (task 2.6), not a surprise afterwards.
