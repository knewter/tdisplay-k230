# Flashing the card over USB, without taking it out of the board

Investigated 2026-09-20. The question: can stage 1 expose the TF card to the
host as a USB block device — U-Boot's `ums` command, the way a PinePhone Pro
does — so that `./tools/flash-latest.sh` writes to the card *in the board*
instead of a human moving it to a reader every round trip?

Short answers:

- **The old U-Boot had no `ums`; the A1 stage-1 build added it and was flashed
  and measured.** The current source also contains a repaired A2 host/gadget
  build; its simultaneous host proof is recorded in
  `docs/evidence/uboot-usb-host-coexist-v2.txt` and
`docs/evidence/usb-host-second-candidate-linux.txt`.
- **Route A is real and small.** Canaan already ships a working USB-gadget
  configuration for this exact SoC in this exact U-Boot tree
  (`k230_canmv_burntool_defconfig`), so the Kconfig, the UDC driver and the
  device-tree binding are all known-good. The work is a defconfig delta, a
  one-line device-tree override, and one gotcha about driver binding.
- **Route B (mainline U-Boot) does not help.** K230 support landed upstream in
  v2025.04, but it is **U-Boot proper only** — no SPL, no DDR init — and its
  defconfig has no gadget support either. It is a different project with a
  different payoff.
- **There is a third route nobody asked about and it may be the best recovery
  story:** the K230 BootROM's USB boot mode, driven by Canaan's MIT-licensed
  `k230_flash`, writes the SD card over USB *with no working bootloader on the
  card at all*. The board has a button wired to `BOOT0` that should force it.

---

## 1. What the board can do today

### `ums` is absent

From the configured tree we build,
`.build/k230_linux_sdk/output/k230_canmv_v3_defconfig/build/uboot-2022.10/.config`:

```
CONFIG_USB=y
CONFIG_USB_DWC2=y            <- host controller driver
CONFIG_USB_HOST=y
CONFIG_USB_STORAGE=y         <- host-side storage class, not the gadget
CONFIG_CMD_USB=y
# CONFIG_USB_GADGET is not set
# CONFIG_DM_USB_GADGET is not set
# CONFIG_CMD_DFU is not set
```

`CONFIG_CMD_USB_MASS_STORAGE` does not appear at all. `CONFIG_USB_STORAGE=y`
is the *host* side — it lets U-Boot read a thumb drive — and is easy to
mistake for the gadget.

The source is all present and unbuilt: `cmd/usb_mass_storage.c`,
`drivers/usb/gadget/f_mass_storage.c`, `drivers/usb/gadget/dwc2_udc_otg.c`.
Nothing has to be fetched.

### But `k230_dfu` *is* compiled in, and it is a clue

`board/canaan/common/k230_board_common.c` registers a `k230_dfu` command
inside `#ifndef CONFIG_SPL_BUILD` — **not** behind `CONFIG_CMD_DFU`. So our
U-Boot has the command and it will fail, because the `run_command("dfu 0")`
it ends in has no `dfu` to run. Reading it is what unlocked the rest of this
document: it decodes a `struct BurnImageConfig` out of SRAM, builds
`dfu_alt_info` for `mmc 1=...`, `sf 0:0:...` or `mtd`, and runs `dfu 0`. That
is the on-target half of Canaan's USB burning tool, and it writes the SD card.

## 2. The USB topology of this board

Three facts, from `repo/schematic/T-Display K230_V1.0_NEW.pdf` and confirmed
against the boot log in `docs/evidence/hardware-boot.txt`.

| K230 controller | Address | Goes to |
| --- | --- | --- |
| `usbotg0` | `0x91500000` | **J3, the data USB-C** — `USB0_P`/`USB0_N` to `J3` pins A6/A7/B6/B7, with `USB0_ID` and `USB0_VBUS` |
| `usbotg1` | `0x91540000` | **an onboard `RTL8152B-VB-CG`** USB 10/100 Ethernet |
| (neither) | — | **J2, the charge USB-C** — `USB_P`/`USB_N` go to the CH342 UART bridge, not to the SoC |

The boot log agrees: Linux brings up `dwc2 91500000.usb` as bus 1 with nothing
attached, and `dwc2 91540000.usb` as bus 2 with `usb 2-1: Realtek USB 10/100
LAN` on it. So the Realtek interface is soldered down, not a dongle, and
`docs/findings.md`'s "No Ethernet" note is about the absent RJ45, not about
this chip.

**This settles which port `ums` must use: `usbotg0`, on J3.** J3 also carries
`USB_VBUS` to the PMU, so one cable to the host both powers the board and
carries the gadget.

In the U-Boot device tree, `arch/riscv/dts/k230.dtsi`:

```dts
usbotg0: usb-otg@91500000 {
        compatible = "snps,dwc2";
        reg = <0x0 0x91500000 0x0 0x10000>;
        g-tx-fifo-size = <128 128 128 128 128 128>;
        dr_mode = "otg";
        otg-rev = <0x200>;
#ifndef CONFIG_CMD_DFU
        status = "disabled";       /* <- so usbotg0 is OFF in our build */
#endif
};
```

and `k230_canmv_v3.dts` enables only `&usbotg1`. Other Canaan boards
(`k230_canmv_mrt.dts`, `_lckfb`, `_gt6700`) already contain a plain
`&usbotg0 { status = "okay"; };`, so the override pattern is established in
the vendor tree.

The PHY does not need board glue: `arch/riscv/cpu/k230/cpu.c`
`harts_early_init()` sets `USB_IDPULLUP0` and writes `USB0_CTL0`/`USB0_CTL1`
(and the USB1 pair) **unconditionally**, before any Kconfig choice.

## 3. Route A — turn on `ums` in the U-Boot we already build

### The defconfig delta

Canaan's own `k230_canmv_burntool_defconfig`, in the same tree, is a working
K230 USB-gadget configuration. Diffing it against `k230_canmv_v3_defconfig`
gives exactly the symbols we need:

```
CONFIG_USB_GADGET=y
CONFIG_DM_USB_GADGET=y
CONFIG_USB_GADGET_DWC2_OTG=y
CONFIG_USB_GADGET_DOWNLOAD=y
CONFIG_USB_GADGET_VENDOR_NUM=0x29f1
CONFIG_USB_GADGET_PRODUCT_NUM=0x0230
```

plus the one Canaan did not need, because they wanted DFU and we want a block
device:

```
CONFIG_CMD_USB_MASS_STORAGE=y
```

`cmd/Kconfig` in this tree says `CMD_USB_MASS_STORAGE` `depends on
USB_GADGET_DOWNLOAD`, `depends on BLK && USB_GADGET`, and `select
USB_FUNCTION_MASS_STORAGE`. All three dependencies are satisfied by the lines
above plus `CONFIG_BLK=y`, which is already on.

No board C code is required. With `CONFIG_DM_USB_GADGET=y`, `dwc2_udc_otg.c`
compiles its DM half and populates `struct dwc2_plat_otg_data` from the device
tree in `dwc2_udc_otg_of_to_plat()`. The legacy path — where a board must call
`dwc2_udc_probe()` by hand, as Rockchip and Meson do — is the `#if
!CONFIG_IS_ENABLED(DM_USB_GADGET)` branch and we do not take it.

### The device-tree override

One line in `arch/riscv/dts/k230_canmv_v3.dts`:

```dts
&usbotg0 {
        status = "okay";
        dr_mode = "peripheral";
};
```

`status = "okay"` because the `#ifndef CONFIG_CMD_DFU` in `k230.dtsi` leaves
`usbotg0` disabled otherwise. Setting `CONFIG_CMD_DFU=y` would also flip it,
but it drags in `select DFU` and — see `cpu.c` — it *removes* the PMP entries
that lock the `0x91213000`/`0x91214000` window. Prefer the explicit override;
it is a one-line change that says what it means.

### The gotcha: host and gadget fight over `snps,dwc2`

Both drivers match the same compatible string:

- `drivers/usb/host/dwc2.c` → `U_BOOT_DRIVER(usb_dwc2)`, `UCLASS_USB`,
  matches `snps,dwc2`
- `drivers/usb/gadget/dwc2_udc_otg.c` → `U_BOOT_DRIVER(dwc2_udc_otg)`,
  `UCLASS_USB_GADGET_GENERIC`, also matches `snps,dwc2`

At the Kconfig level they coexist happily. At the **driver-model bind** level
they do not, in this version:

- `lists_bind_fdt()` in `drivers/core/lists.c` walks the driver linker list,
  binds the **first** driver whose `of_match` hits, and `break`s. It only
  continues past a match if `device_bind_with_driver_data()` returns
  `-ENODEV`, which happens when the driver's `.bind` refuses.
- **Neither driver declares a `.bind`.** Verified: `grep '\.bind'` finds
  nothing in either file.
- The gadget driver's `dr_mode` check — "Invalid mode", `return -ENODEV` — is
  in `dwc2_udc_otg_of_to_plat()`, which runs at *probe*, far too late to let
  another driver bind the node.
- Linker-list entries are emitted as `__u_boot_list_2_driver_2_<name>` and
  `SORT`ed, and `dwc2_udc_otg` sorts before `usb_dwc2`.

So with both enabled and only the generic compatible, the **gadget driver
claims every `snps,dwc2` node**, including `usbotg1`, and U-Boot's USB host
stack goes dark. The initial gadget build confirmed that binding conflict.
The first coexistence candidate then rejected host nodes in gadget `.bind`,
leaving `usbotg1` unbound: `lists_bind_fdt()` advances to the next compatible
string, not another driver for the same string. That failed attempt is
preserved in `docs/evidence/uboot-usb-host-coexist.txt`.

The repaired A2 source adds `canaan,k230-usbotg-host` first on `usbotg1`
and adds that ID to the host driver, while retaining the gadget bind guard.
Its build evidence is in `docs/evidence/uboot-ums-build.txt`; the repaired
candidate's host/gadget result and return to Linux are in
`docs/evidence/uboot-usb-host-coexist-v2.txt` and
`docs/evidence/usb-host-second-candidate-linux.txt`. The record does not
claim packet traffic.

Corroboration for the historical A1 choice: Canaan's
`k230_canmv_burntool_defconfig` enables the gadget and **drops
`CONFIG_USB_DWC2`**.

Two ways out:

- **A1, minimal.** Add the gadget symbols and add `# CONFIG_USB_DWC2 is not
  set`. One binary, unambiguous, no USB host in U-Boot. We do not use USB host
  in U-Boot today — `bootcmd` is `run blinux`, which touches only `mmc` (see
  `docs/evidence/uboot-env.txt`) — so nothing in the current boot path
  regresses.
- **A2, preferred and built.** Keep the host driver, set `dr_mode =
  "peripheral"` on `usbotg0` and `dr_mode = "host"` on `usbotg1`, add
  the gadget bind guard, and put the K230-specific host compatible before
  `snps,dwc2`. This keeps the door open for a TFTP loop over the onboard
  Ethernet. The repaired candidate's hardware result is recorded in
  `docs/evidence/uboot-usb-host-coexist-v2.txt` and
`docs/evidence/usb-host-second-candidate-linux.txt`.

### Where the change lands, and the sequencing problem

`tools/gen-stage1.sh` does not run `make` — it packages an already-configured,
already-built tree under `.build/k230_linux_sdk/output/`. A defconfig change
has to reach the compile step, and the compile step is currently outside this
repository.

That is precisely what the in-flight change
`every-blob-is-built-from-source-or-named` is moving into the flake. **Route A
should land on top of it, not beside it**, or we will grow a second, divergent
way to build stage 1. Under the requirement it replaces — "Stage 1 … SHALL NOT
be built from source by this project", from
`the-board-boots-what-we-built/specs/image/boot-chain/spec.md` — Route A is
not merely awkward, it is forbidden.

### What it costs

| Item | Estimate |
| --- | --- |
| Defconfig fragment + DTS override | 15 min |
| Wiring it into whatever builds U-Boot (after `every-blob…` lands) | 1 h |
| Rebuild U-Boot in the container | ~5 min |
| One card-reader cycle to install the new stage 1 | 10 min |
| Bring-up: does J3 enumerate, does `ums 0 mmc 1` appear as a block device | 30 min – 2 h |
| A2 follow-up (`.bind` patch, keep host) | 1 h |

**Realistic total: half a day**, dominated by the risk that the dwc2 gadget
does not come up first try. The classic dwc2 failure is B-session/VBUS
detection; the mitigations are the device-tree properties
`u-boot,force-b-session-valid` and `u-boot,force-vbus-detection`, both read by
`dwc2_udc_otg_of_to_plat()` in this tree. J3 has real `USB0_ID` and
`USB0_VBUS` wiring and `cpu.c` already sets `IDPULLUP0`, so there is a good
chance neither is needed.

### What it actually buys

Less than the round trip suggests, and more than throughput suggests.

The current image is **2.21 GB** (`k230-sd-image.img` in the store). U-Boot
`ums` over DWC2 high-speed realistically moves 5–20 MB/s, so a *full* image
write is 2–7 minutes — not obviously faster than a card reader.
**Measured 2026-09-22** (`docs/evidence/uboot-ums-write.txt`,
`uboot-ums-enumerate.txt` session 8): **12.6 MB/s written**, 175 s for
2 210 918 400 bytes, `dd bs=4M oflag=sync conv=fsync`; **12.0 MB/s read**,
184 s. Three minutes either way, with nobody at the desk.

The win is not bandwidth, it is:

1. **No human in the loop.** `flash-latest.sh` can run unattended.
2. **Partial writes become possible.** With the card as a host block device,
   a kernel-only change is `mount` + copy of ~60 MB into the boot partition,
   not 2.21 GB. That is the order-of-magnitude change, and it is the thing to
   actually implement once `ums` works.

## 4. Route B — build current upstream U-Boot

**It landed.** "riscv: canaan: k230_canmv: Add initial support", commit
`9c402a5`, merged 2025-01-16, first released in **v2025.04**. Files:
`configs/k230_canmv_defconfig`, `board/canaan/k230_canmv/`,
`arch/riscv/cpu/k230/`, `arch/riscv/dts/k230.dtsi`, `k230-canmv.dts`,
`k230-u-boot.dtsi`, `doc/board/canaan/k230_canmv.rst`.

**It is not an SPL.** Upstream's own board document says it plainly:
"Currently, we rely on vendor u-boot-spl to initialize the ddr and load the
u-boot image, then bootup from it." There is no `CONFIG_SPL` in the K230
Kconfig, and `arch/riscv/cpu/k230/dram.c` only calls
`fdtdec_setup_mem_size_base()` / `fdtdec_setup_memory_banksize()` — it reads a
`/memory` node someone else established. No DDR PHY training code exists
upstream.

Mapped onto `docs/blob-inventory.md`:

| Blob | Could mainline replace it? |
| --- | --- |
| **A1** `fn_u-boot-spl.bin` | **No.** Upstream has no K230 SPL. |
| **A5/A6** DDR PMU training firmware | **No.** It lives inside A1, and upstream has no equivalent. |
| **A2** `fn_ug_u-boot.bin` (U-Boot proper) | **Yes, in principle.** This is the only piece in scope. |
| **A3** `env.env` | Already ours. |
| **A8** BootROM | Never. |

So "mainline U-Boot" here means "mainline U-Boot proper, still started by
Canaan's SPL and its training blob". Additional costs:

- The Canaan firmware header is **not** upstream. No `mkimage` type, no
  Binman entry; the board doc tells you to run the vendor's `firmware_gen.py`
  as an external step. We already reproduce that step, so this is survivable.
- Only **CanMV-K230** exists upstream. No T-Display-K230, no `k230d`.
- Upstream's `k230_canmv_defconfig` has **no gadget and no `ums`** either —
  only `USB_DWC2` host plus `USB_ETHER_RTL8152`. Route B does not deliver the
  thing we are asking for; it would need the same Route A work on top.
- **A board-specific hazard.** `docs/dts-evidence.md` records that there is no
  pinctrl in the Linux device tree at all — FPIOA muxing is inherited from
  U-Boot's `pinctrl-single` node. Replacing vendor U-Boot proper means
  replacing the thing that muxes IO54–59 to MMC1 and the panel and UART pins.
  That is not a port of a bootloader, it is a port of the board.

**Verdict: not now.** Route B is worth doing eventually, to stop carrying
Canaan's U-Boot fork, and it is a change of its own. It is not the answer to
"how do we stop walking the card across the desk".

## 5. Route C — the BootROM's USB boot mode

This is the one that surprised me, and it is the better *recovery* mechanism.

**Host tooling exists and is open.** Canaan publishes `kendryte/k230_flash_py`
(MIT, Python, `pyusb`, also on PyPI as `k230-flash`), plus a C++ CLI
`kendryte/k230_flash` and a GUI `kendryte/k230_burning_tool`. The device
enumerates as **VID `0x29f1`, PID `0x0230`**; the documented udev rule is

```
SUBSYSTEM=="usb", ATTRS{idVendor}=="29f1", ATTRS{idProduct}=="0230", MODE="0666"
```

**That VID/PID is the same pair in `k230_canmv_burntool_defconfig`**
(`CONFIG_USB_GADGET_VENDOR_NUM=0x29f1`, `CONFIG_USB_GADGET_PRODUCT_NUM=0x0230`).
The tool's "trimmed-down U-Boot" loader *is* the burntool build of the very
tree we already compile. The flow is: BootROM enumerates → host pushes the
loader into SRAM → it re-enumerates → `k230_dfu` reads the burn config out of
the protected SRAM window, sets `dfu_alt_info` to `mmc 1=…`, runs `dfu 0` →
the host DFU-writes the card. `KBURN_USB_ISP_SDIO1` is the SD card. All of
that is readable in
`buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/board/canaan/common/k230_board_common.c`.

**And this board has the button.** From the schematic:

```
BOOT0 = 0, BOOT1 = 0  SPI Nor
BOOT0 = 0, BOOT1 = 1  eMMC
BOOT0 = 1, BOOT1 = 0  SPI Nand
BOOT0 = 1, BOOT1 = 1  SD Card
```

`SW3` is a pushbutton between `BOOT0` and `GND`. `BOOT0` also appears on a
header. Holding `SW3` at power-on therefore selects `0,1` = **eMMC**, which is
not populated on this board, so the BootROM should fall through to USB boot —
Canaan's hardware guide says USB/UART boot is the fallback when the selected
medium fails.

<!-- UNVERIFIED: the fall-through has not been observed on this board. The
test is free and is in §7. -->

## 6. If the new U-Boot does not boot, how do we recover?

**The premise checks out: this board has no boot medium other than the TF
card.**

- LilyGO's own product table lists `FLASH` as "SD Card" for this board.
- The schematic contains no SPI NOR or NAND part — searching the extracted
  netlist for `NOR`, `FLASH`, `W25Q`, `GD25` finds nothing. The `OSPI_*` pins
  that could host one carry `IO16_MOSI` / `IO19_BUSY`, i.e. the SX1262/LR2021
  LoRa radio.
- MMC0 is the RTL8189FTV SDIO radio and MMC1 is the TF card
  (`docs/findings.md`, corrected). No eMMC.
- The straps sit at `BOOT0=1, BOOT1=1` = SD Card, which is consistent with the
  board booting from the card today.

A third-party wiki page claims this module has onboard SPI NOR. It also
describes the Wi-Fi as an ESP32-S3 co-processor, which `docs/findings.md`
already records as contradicted by the schematic. Treating that page as
unreliable for this board.

So there are **two independent nets**:

1. **Pull the card, write it in a reader.** Always works, because the card is
   the only boot medium. This is the floor, and it is the same loop we have
   today — the failure mode of Route A is "we are back where we started",
   not "the board is a brick".
2. **`k230_flash` over J3 with `SW3` held.** Needs no working bootloader on
   the card at all. Unverified, free to test.

## 7. Commands to run on the board (and on the host)

I did not touch the serial port. These are cheap, read-only, and each one
settles something in this document.

**At the `K230#` prompt** (interrupt the 5-second `bootdelay`):

```
version
help ums
help k230_dfu
```

Expected: `version` prints the U-Boot build; `ums` reports "Unknown command"
(confirming §1); `k230_dfu` prints "k230 burntool enter dfu" (confirming that
the source in `.build/` really is what is on the card). If `ums` is somehow
*present*, stop reading — try `ums 0 mmc 1` immediately.

```
dm tree
```

The important one. It lists every bound device and its driver. Today
`usb-otg@91540000` should show as `dwc2_usb` in `UCLASS_USB` and
`usb-otg@91500000` should be absent (disabled). After Route A lands, this same
command is what proves or disproves §3's driver-binding claim.

```
mmc list
mmc dev 1
mmc info
```

Confirms the card is `mmc 1` and how big U-Boot thinks it is — `ums 0 mmc 1`
will take the same argument.

```
usb start
usb tree
```

Does U-Boot currently enumerate the onboard RTL8152? This is the exact thing
A1 gives up, so it is worth knowing whether we have it at all.

**On the host:**

```
lsusb
```
with a cable in **J3** (the data USB-C, not the charge one with the two
CDC-ACM ports on it) while the board sits at the U-Boot prompt. Expect
nothing — no gadget is configured. This is the baseline to compare against
after Route A.

```
# Route C test, no risk, nothing is written:
#   1. power off
#   2. take the TF card OUT
#   3. hold SW3 (the button wired to BOOT0) and apply power via J3
#   4. on the host:
watch -n1 'lsusb | grep -i 29f1'
```

If `29f1:0230` appears, Route C is live and we have an
unbrickable recovery path plus a second flashing route. Try it with the card
out first, since that removes the SD boot path without needing the strap to
work.

## 8. Recommendation

1. **Do Route A**, as variant A1 first, stacked on
   `every-blob-is-built-from-source-or-named`. Half a day. Proposed as
   `openspec/changes/the-card-is-flashed-over-usb-from-u-boot/`.
2. **Test Route C tonight** — it costs one power cycle and, if it works, it
   is the thing that makes Route A safe to iterate on.
3. **Once `ums` works, change what we write.** Writing 2.21 GB per iteration
   is the real cost; a mounted boot partition and a 60 MB copy is the
   order-of-magnitude win, and `ums` is what makes it available.
4. **Do not do Route B for this.** Revisit it as its own change when the goal
   is dropping Canaan's U-Boot fork, and know going in that it cannot touch
   the SPL or the DDR training blob.

---

## 9. What has been observed since (2026-09-22)

Written after `every-blob-is-built-from-source-or-named` landed, so "the
U-Boot we build" now means `nix/uboot-k230.nix`, and after the first session
at the board's own prompt for
`the-card-is-flashed-over-usb-from-u-boot`. Everything here is in
`docs/evidence/uboot-ums-hardware.txt` or `docs/evidence/uboot-ums-build.txt`.

**§1 confirmed on the board.** `help ums` → `Unknown command 'ums'`;
`help k230_dfu` → `k230 burntool enter dfu`. `version` reports
`riscv64-unknown-linux-gnu-gcc (GCC) 15.3.0`: the card carries this
project's build, not the Docker one, and it has no gadget.

**§2 confirmed on the board.** `usb start; usb tree` on today's U-Boot finds
`Realtek USB 10/100 LAN` behind `usb-otg@91540000` — the onboard RTL8152 on
`usbotg1`, as the schematic and the Linux boot log said. `usb-otg@91500000`
does not appear in `dm tree` at all, which is `k230.dtsi`'s
`status = "disabled"` doing what §2 says it does. `mmc list` names the card
`mmc1@91581000: 1 (SD)`, 119.1 GiB; `ums 0 mmc 1` is the argument.

**§3's driver-binding claim: the before half is observed.** `dm tree` shows
`usb-otg@91540000` bound to `dwc2_usb`, the host driver, and nothing else in
`UCLASS_USB`. What the gadget driver binds once it exists is still the
after half, and it needs the new build on the board.

**§3's build, done.** `nix/uboot-k230-ums.config` carries the six gadget
symbols plus `CONFIG_CMD_USB_MASS_STORAGE=y` and `# CONFIG_USB_DWC2 is not
set`, with D3's reasoning next to that line;
`nix/patches/uboot-k230/0001-k230_canmv_v3-enable-usbotg0-as-a-peripheral.patch`
is the device-tree override. Two things the plan did not foresee, both in
`docs/evidence/uboot-ums-build.txt`: turning `USB_GADGET` on exposes
Kconfig symbols that a non-interactive build cannot answer, so the
derivation runs `olddefconfig` after appending the fragment; and Canaan's
own addition to `dwc2_udc_otg.c` (the `USB0_TEST_CTL3` pull-down clear,
passing a `u32` address to `readl`) is an error under GCC ≥ 14's
`-Wint-conversion`, so the build demotes that one diagnostic rather than
pin the whole tree to GCC 13. The result: `ums` in the binary
(`do_usb_mass_storage`, `UMS: LUN %d, dev %s ...`), the gadget driver in the
linker list, the host driver gone, `usb-otg@91500000` `okay`/`peripheral`
in the embedded device tree, and U-Boot proper 31 KB *smaller* than before
because the USB host and Ethernet class drivers left with `USB_DWC2`.

**§7's warm-reboot detail, worth knowing.** A `reboot` from Linux does not
drop the CH342 console: the port stayed open through the SoC reset and
`tools/capture-boot.py --hammer` caught the 1 s `bootdelay` first time. A
cold boot is different (`docs/evidence/boot-from-source-cold.txt`): the
bridge loses power with the board and the prompt is unreachable from the
host until it re-enumerates.

**A caution for Route C, from LilyGO's own BSP** (reported by the agent
reading it for `the-screen-lights-before-linux`; their evidence file is
`docs/evidence/lilygo-uboot-logo.md` once that branch lands). LilyGO's
U-Boot overlay *deletes* `enter_to_usb_burn_mode()` from
`board/canaan/common/k230_board_common.c` and moves the environment to
offset `0x1e0000`, size `0x10000`. Neither is in the stage 1 this project
builds, which takes Canaan's SDK overlay and keeps the environment at 3 MiB
/ 3.5 MiB (`nix/sd-image.nix`) — which is why 1.1 found `k230_dfu` present,
as the SDK source says it should be. So if the BootROM/USB recovery path
behaves differently from what §5 reads out of the SDK, the first thing to
ask is which U-Boot was on the card; the characterisation in §5's tasks must
be made against *our* stage 1, and the RT-Smart image LilyGO shipped is not
evidence about it either way.

**§3's gadget, on the board (2026-09-22, `docs/evidence/uboot-ums-enumerate.txt`).**
`ums 0 mmc 1` runs: `UMS: LUN 0, dev mmc 1, hwpart 0, sector 0x0, count
0xee4c000` (the 119.1 GiB card), and `dm tree` shows both `snps,dwc2` nodes
bound to `dwc2-udc-otg` — `usbotg1` too, its `dr_mode` still `otg`, so the
A2 `.bind` is needed to keep USB host. Four sessions and two cables later
the host had still seen nothing; the core's own registers say why the
usual suspects are wrong. `GOTGCTL` reads `0x000d0000` with the cable in:
bit 19 `B_SESSION_VALID` set — **the PHY sees VBUS**, so §3's "classic dwc2
failure" is not this one. And the two `u-boot,force-*` properties named
there as the mitigation are inert on this SoC in this tree:
`dwc2_udc_otg_of_to_plat()` parses them (`dwc2_udc_otg.c:1014-1018`) but
`dwc2_udc_otg_probe()` acts on them only under
`if (plat->activate_stm_id_vb_detection)` (`:1121-1158`), a flag set solely
by `dwc2_set_stm32mp1_hsotg_params()` (`:1030-1043`), reached only through
`st,stm32mp15-hsotg`'s driver data. Struck from the plan. After `ums`:
`DCTL` bit 1 clear (D+ pulled up), `GINTSTS` with `INT_RESET` and
`INT_ENUMDONE` set (a host reset the bus and enumeration completed — at
**full** speed, `DSTS` EnumSpd 01, on a high-speed core), then
`INT_SUSPEND`. Meanwhile solomon's kernel log has no attach on any bus in
any window. Whatever reset that bus was a host, and it was not this machine.

**And then it enumerated (session 5).** The cable's far end was proven to
reach this machine with a phone first; moved to J3, `ums 0 mmc 1` on the
same firmware put `29f1:0230 … USB download gadget` on `usb 3-4` at
**480 Mb/s**, as `/dev/disk/by-id/usb-Linux_UMS_disk_0-0:0`, 249 872 384
sectors — the card — with `K230_BOOT` and `NIXOS_SD` visible, and the
2 MiB slot read back over USB hashing to the build's `fn_ug_u-boot.bin`.
`DSTS` this time reads high speed; the full-speed enumeration of sessions
3–4 was the other host's doing. Four failed sessions and the register
decode were the cost of not being able to see the bench: the board had
been right all along.

**Read back over `ums`, every byte (sessions 6–8).** The whole 2.2 GB
image region read from the gadget at **12.0 MB/s** (184 s, `dd bs=4M`,
high speed on xhci) — so §3's "5–20 MB/s" guess lands at the low-middle
for reads, and a full-image write will be about that or slower. The card
does not equal the image after a boot, and cannot: `k230_set_dtb_env()`
calls `env_save()` on every boot (`k230_board_common.c:511`), rewriting
the env copy at 3 MiB (only that one — this U-Boot has no
`CONFIG_ENV_OFFSET_REDUND`, so the 3.2 MiB copy the SDK layout writes is
dead weight it never reads), and Linux mounts both ext4 partitions
read-write. Compared region by region instead: `[0, 3 MiB)` identical;
partition 1's five files — `Image`, `fw_jump_add_uboot_head.bin`, the DTB,
`bootargs.txt`, `initrd.uimg`, 88 MB — byte-identical through `debugfs`
with no mount; and of 538 943 4 KiB blocks after the env, the 5 506 that
differ are all inside the two mounted filesystems, none in the gaps. The
transport is proven for reads; task 3.4's literal `cmp` check needs
rewording to say so.

**Written through, and booted (session 9,
`docs/evidence/uboot-ums-write.txt`).** The same image flashed onto the
card in the board by `tools/flash.sh` against the gadget's by-id path,
12.6 MB/s, 175 s; `reset`; the board came up to the login prompt and hashed
its own SPL and U-Boot slots to the image's bytes. The reset also put the
from-source SPL banner and the whole `PMU Major Msg` training sequence on
the record, which a cold boot never could. The loop this document was
written for exists: `./tools/flash-latest.sh --ums` with the board at
`ums 0 mmc 1`.

**A2 hardware proof (2026-09-22).** The repaired candidate's transcript
shows `usb start` finding the onboard RTL8152 host, `ums 0 mmc 1` exposing
the card and a successful readback, then Linux returning with the shell
active. See `docs/evidence/uboot-usb-host-coexist-v2.txt` and
`docs/evidence/usb-host-second-candidate-linux.txt`. This proves
the host/gadget coexistence path and recovery to Linux; it does not claim
network packet traffic.

### Unattended image verification

`tools/ums-session.py --flash IMAGE --expected-sectors SECTORS --out LOG`
now requires the card capacity observed from the board. For the card measured
in `docs/evidence/uboot-ums-write.txt`, that is `249872384` sectors. It refuses
a different capacity, more than one newly discovered disk, a name other than
`usb-Linux_UMS_disk_0-0:0`, or USB identity other than `29f1:0230`.

After `flash.sh` succeeds it compares every image byte against the gadget
using `dd iflag=direct,count_bytes` piped into `cmp`, checking both exit
statuses. Direct I/O bypasses the host page cache. This comparison must
happen before resetting the board: U-Boot
saves its environment and Linux modifies the mounted filesystems. Failure
leaves U-Boot in mass-storage mode so a known-good image can be restored.
The pre-boot comparison has no hardware evidence yet; its next invocation
must record the result alongside the boot transcript. Host refusal checks:
`python3 -m unittest discover -s tests -p test_ums_target.py`.
