## ADDED Requirements

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
