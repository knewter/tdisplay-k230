# Is there onboard Bluetooth, without a USB dongle?

Compiled 2026-09-26, in response to a direct question after
`the-handheld-talks-bluetooth` enabled kernel Bluetooth + BlueZ: with no USB
dongle plugged in, `bluetooth.service` is inactive (no `hci0`). Does *this*
physical board have any Bluetooth radio that doesn't need one?

**Answer: no. This board's Wi-Fi chip is the Wi-Fi-only member of its family,
the K230 SoC has no Bluetooth IP, and the only Bluetooth path that has ever
been built or specified for this project is the USB dongle path already in
`the-handheld-talks-bluetooth`.** Two things exist that *sound* like
onboard Bluetooth and are not, for this board: LILYGO's own BSP documents an
alternate main-board SKU with a genuine combo Wi-Fi+BT chip (not this
board's chip, confirmed by the chip's own device ID below), and the
optional nRF52840 accessory base (not the base this project owns) provides
BLE only via a proprietary bridge protocol, not a Linux HCI controller.

Grounding tiers follow `.skills/k230-spec-change/SKILL.md`: **tier 1** is
this board's own captured evidence (`docs/evidence/wifi-preflight.txt`),
**tier 2** is vendor/open-source driver code and BSP docs read directly,
cited by path or commit. Nothing below rests on a datasheet or marketing
page alone.

## 1. The Wi-Fi chip: Wi-Fi-only, not a combo, on this specific board

This board's own already-captured SDIO enumeration
(`docs/evidence/wifi-preflight.txt`, board capture, **tier 1**) shows
exactly one SDIO function, `mmc0:0001:1`, reporting:

```
vendor:   0x024c
device:   0xf179
modalias: sdio:c07v024CdF179
```

`0x024c` is Realtek's SDIO vendor ID. The device ID `0xf179` is not
ambiguous: the out-of-tree Realtek SDIO driver's own device table —
[`lwfinger/rtl8723ds`, commit `52e593e8c889b68ba58bd51cbdbcad7fe71362e4`,
`os_dep/linux/sdio_intf.c`](https://github.com/lwfinger/rtl8723ds/blob/52e593e8c889b68ba58bd51cbdbcad7fe71362e4/os_dep/linux/sdio_intf.c#L57-L88)
(**tier 2**) — lists every Realtek SDIO Wi-Fi/combo part side by side:

```c
{ SDIO_DEVICE(0x024c, 0xB723), .driver_data = RTL8723B},
{ SDIO_DEVICE(0x024c, 0x8179), .driver_data = RTL8188E},
{ SDIO_DEVICE(0x024c, 0x8821), .driver_data = RTL8821},
{ SDIO_DEVICE(0x024c, 0x818B), .driver_data = RTL8192E},
{ SDIO_DEVICE(0x024c, 0xB703), .driver_data = RTL8703B},
{SDIO_DEVICE(0x024c, 0xF179), .driver_data = RTL8188F},   // <- this board
{SDIO_DEVICE(0x024c, 0xB822), .driver_data = RTL8822B},
{ SDIO_DEVICE(0x024c, 0xD723), .driver_data = RTL8723D},  // <- combo part
{ SDIO_DEVICE(0x024c, 0xD724), .driver_data = RTL8723D},  // <- combo part
{SDIO_DEVICE(0x024c, 0xB821), .driver_data = RTL8821C},
```

This board's `0xF179` is `RTL8188F` — the same chip family our own
`docs/evidence/wifi-driver-audit.md` already identified and built a driver
for (`8189fs.ko` via `jwrdegoede/rtl8189ES_linux`, `CONFIG_RTL8188F`). The
genuine Realtek Wi-Fi+Bluetooth combo part, `RTL8723D`, reports an entirely
different device ID (`0xD723`/`0xD724`) in the very same table. A board
carrying the combo chip would have shown `vendor=0x024c device=0xd723` (or
`d724`) in that SDIO capture, not `0xf179`. It didn't — this specific unit's
Wi-Fi silicon is the Wi-Fi-only part.

This matches the marketing name already used elsewhere in this repo
(RTL8189FTV/RTL8189FS) — that family is built around the RTL8188F die and,
per Realtek's own product listing and the RTL8189FTV module datasheet
(SDIO2.0, LGA, single 1T1R WLAN radio, no Bluetooth section) is Wi-Fi-only.
That datasheet detail is not load-bearing here (a datasheet alone isn't
grounding); the load-bearing fact is the device-ID match against the
vendor driver's own table above.

### LILYGO documents an alternate SKU — but names it as an alternate, and it isn't this board

LILYGO's own upstream BSP,
[`Xinyuan-LilyGO/T-Display-K230`, `k230_bsp/docs/HARDWARE_PINMAP.md`
(commit `7ee13ce7028b98dd08fc8f21f994d3609a7decdc`)](https://github.com/Xinyuan-LilyGO/T-Display-K230/blob/7ee13ce7028b98dd08fc8f21f994d3609a7decdc/k230_bsp/docs/HARDWARE_PINMAP.md)
(**tier 2**), the same repo `docs/findings.md` and `docs/dts-evidence.md`
already treat as authoritative for this board's pin map, has this exact
row in its main-board device table:

> | Wi-Fi | SDIO | I/O | RTL8189FS or RTL8723DS Wi-Fi | RTL8723DS Bluetooth
> requires separate BT UART hardware signals; SDIO covers Wi-Fi only. |

Read literally, this names **two alternate main-board Wi-Fi SKUs** —
RTL8189FS (Wi-Fi-only, our device ID) or RTL8723DS (combo, but even then
Bluetooth doesn't ride the SDIO bus at all — it needs its own, separately
wired BT UART). A public issue on LILYGO's documentation repo,
[`Xinyuan-LilyGO/documentation#13`](https://github.com/Xinyuan-LilyGO/documentation/issues/13)
(**tier 2**, a reported user observation, not board-observed by us),
independently confirms real units ship with either chip and that the
wiki's "ESP32-S3 Wi-Fi/BT" claim is simply wrong — no ESP32-S3 network
device exists on any reported unit; it's Realtek SDIO on all of them. That
issue reports RTL8189FS units have no onboard Bluetooth at all, matching
the analysis above.

**Conclusion for this board**: it is the RTL8189FS/RTL8188F SKU. No BT UART
wiring is needed or present for that SKU — LILYGO's own pinmap only
mentions a BT UART requirement for the *other* SKU. Even if this board
somehow were the RTL8723DS SKU, LILYGO's own main-board pinmap table does
not list which K230 GPIO/UART carries that chip's BT UART (unlike the
fully-pinned nRF52840/nRF9151 base-board UARTs in the same document) — so
enabling it would require a fresh schematic/BOM lookup, not just a Kconfig
flip. This is moot for the physical unit in hand, whose device ID has
already ruled it out.

## 2. Other silicon that might carry Bluetooth

### The K230 SoC itself: no BT IP

Canaan's K230 is a dual-core RISC-V (C908) AIOT vision SoC (NPU/ISP/video
codec focus). Its documented peripheral set — GPIO, UART, SPI, I2C, SDIO,
USB (DWC2 OTG ×2), MIPI-CSI/DSI, PWM, ADC, crypto/TRNG/OTP — is already
fully enumerated in `docs/research/board-capability-inventory.md` from a
direct read of the pinned kernel tree's `k230.dtsi` and `k230_defconfig`
(**tier 2**, our own checkout); none of that enumeration, nor any Canaan
datasheet page, includes a Bluetooth/HCI radio block. This project has
never found or needed a `CONFIG_BT*`-adjacent SoC-internal driver, and
neither `nix/dts/k230-tdisplay.dts` nor the upstream `k230.dtsi` declares
one. No further probing changes this; there is no on-chip radio to find.

### The nRF52840 base board: BLE, but not this board, and not a Linux HCI controller

The optional nRF52840 BLE/audio/sensor base (documented in the same
LILYGO `HARDWARE_PINMAP.md`, and in its own repo,
[`Xinyuan-LilyGO/T-Display-K230-nRF52840`, `README.MD`
(commit `4646a728580739d487126f47a521e9b8032b3c2c`)](https://github.com/Xinyuan-LilyGO/T-Display-K230-nRF52840/blob/4646a728580739d487126f47a521e9b8032b3c2c/README.MD))
does carry a real BLE radio (the nRF52840 itself). But:

- **This project's board does not have that base attached** — the
  keyboard/nRF9151 base is the one in hand (per the task and
  `board-capability-inventory.md`'s base-board rows).
- Even if it were attached, its BLE is **not** exposed as a standard HCI
  UART controller the way Zephyr's `hci_uart` sample or a genuine
  Bluetooth module would expose it. The base's own README states: *"The
  firmware exposes a simple UART AT protocol for BLE Central operations"*
  and *"The nRF52840 only bridges BLE packets to UART; K230 owns protobuf
  parsing and all [application] behavior."* Linux would need a
  purpose-built userspace bridge speaking that AT protocol over
  `/dev/ttyS1` (115200 8N1, per `HARDWARE_PINMAP.md`'s nRF52840 UART row);
  it would never appear as `hci0` to BlueZ. This is a different, unrelated
  integration from `the-handheld-talks-bluetooth`'s BlueZ/`btusb` path, out
  of scope for "does this board have onboard BT the existing kernel/BlueZ
  work can already use" — the answer for that specific question is no
  either way.

### The nRF9151 base board (the one actually installed): no Bluetooth

Nordic's own nRF9151 product page states the SiP supports LTE-M, NB-IoT,
NB-NTN (satellite), DECT NR+, and GNSS
([nordicsemi.com/Products/nRF9151](https://www.nordicsemi.com/Products/nRF9151),
**tier 2**, vendor source read directly) — no Bluetooth/BLE radio is
listed or exists in that SiP; it targets cellular/non-terrestrial/DECT use
cases, not short-range radio. This project's own `HARDWARE_PINMAP.md`
reading confirms the nRF9151 base wires only an AT-command cellular UART
(`GPIO28`/`GPIO29`, `/dev/ttyS3`) plus a power-enable GPIO — no BT-shaped
signal anywhere in that base's row set. **Confirmed: the installed base
board contributes no Bluetooth.**

## 3. Onboard USB: no BT chip on the bus

The board's current `lsusb`-equivalent enumeration (per the task
description, matching this project's own USB host validation work) shows
only `0bda:8152` (Realtek's own **RTL8152B USB-Ethernet** chip — a wired
LAN adapter, unrelated to Bluetooth despite sharing a vendor prefix with
the Wi-Fi part) plus two DWC2 OTG root hubs. No hub-embedded Bluetooth
controller, no second USB Bluetooth-class device. LILYGO's own
`HARDWARE_PINMAP.md` lists "USB Bluetooth" only under the generic "USB
host" row alongside "USB Ethernet, USB modem" — i.e. their own BSP treats
Bluetooth as something a person plugs in over USB host, exactly matching
`the-handheld-talks-bluetooth`'s existing design. There is no undocumented
onboard USB device to find here.

## 4. What the running board can show, and the probe script

Everything above is a documentation/vendor-source conclusion plus this
project's one already-captured SDIO preflight. To let a future board
session re-derive (or falsify) it directly instead of trusting this
document, `tools/bt-probe.sh` is a new, strictly read-only probe. It
prints:

- every SDIO device's function name, vendor/device ID, modalias, and bound
  driver (a second function on the same card, or an ID other than
  `0x024c`/`0xf179`, would falsify this document's conclusion for whatever
  unit it's run on);
- the full `ttyS*` list with any device-tree node and `compatible` string
  (would surface a UART-attached BT controller, `BT_EN`-style DT wiring,
  or an `hci_uart`/`btattach`-bound line);
- `rfkill list` (read-only);
- `hciconfig -a` and `btmgmt info`, run with no state-changing subcommand;
- `dmesg | grep -iE 'bt|bluetooth|hci|rtk'`;
- every USB device's `idVendor:idProduct` and `product` string from sysfs.

It never loads/unloads a module, never blocks/unblocks rfkill, never
powers a controller up or down, and never touches `/dev/ttyACM0` (it runs
on the board, not over the console link). Usage, on the board:

```sh
sh tools/bt-probe.sh
```

or captured over the console the way other probes in this repo are, e.g.
`tools/console.py --send 'sh tools/bt-probe.sh'`. A host-side fixture test,
`tools/test-bt-probe.sh` (same `BOARD_INVENTORY_ROOT`-style pattern as
`tools/test-board-inventory-probe.sh`, via `BT_PROBE_ROOT`), proves the
script's parsing logic against a synthetic tree without a board; it was
run on this host (`bash tools/test-bt-probe.sh` → `bt-probe fixture: PASS`)
as this change's host-build evidence. Running it for real against the
physical board is a separate, board-owning-agent's task; this document
does not claim that board run happened.

## 5. If a future unit *is* the RTL8723DS SKU

Recorded for completeness, since LILYGO's own pinmap documents it as a
real alternate build, even though it is not this board:

- **Driver**: `CONFIG_RTW88_8723D` (mainline `rtw88`, already selectable
  in our pinned kernel tree per `docs/evidence/wifi-driver-audit.md`'s
  survey of that directory) for the Wi-Fi half; the Bluetooth half needs
  `drivers/bluetooth/hci_uart` (`CONFIG_BT_HCIUART`) with Realtek protocol
  support (`CONFIG_BT_HCIUART_RTL`), since RTL8723DS Bluetooth is UART-
  attached, not SDIO — matching LILYGO's own pinmap note.
- **DT**: a UART node with `status = "okay"` for whichever K230 UART
  carries the BT half (not named in LILYGO's own main-board pinmap table —
  unlike the base-board UARTs, no exact GPIO pair is given for this), plus
  likely a `BT_EN`/reset GPIO the schematic would need to identify. This
  is the one piece that is genuinely unknown from documentation alone and
  would need a schematic read or a board probe (`tools/bt-probe.sh`'s
  `ttyS`/DT section) on that specific unit.
- **Firmware**: Realtek ships a separate `rtl8723d_fw.bin`-style blob for
  the Bluetooth half (distinct from the Wi-Fi firmware already tracked in
  `docs/blob-inventory.md`), loaded via the standard `hci_uart`/Realtek
  protocol firmware-request path, not compiled into the driver the way the
  Wi-Fi RTL8188F firmware is.
- **Userspace**: `btattach -B /dev/ttySx -P realtek` (or `hciattach`) to
  bind the line discipline, then BlueZ as already planned.

None of this applies to the unit this project currently has; it is
recorded so it isn't rediscovered from scratch if a different unit or
revision ever shows a different SDIO device ID.

## Bottom line

- No onboard Bluetooth on this board, with or without a dongle plugged in.
- The Wi-Fi chip is confirmed (by this board's own SDIO device ID against
  the vendor driver's own ID table) to be the Wi-Fi-only RTL8188F/RTL8189FS
  part, not the RTL8723DS combo LILYGO documents as an alternate SKU.
- The K230 SoC has no Bluetooth IP; the installed nRF9151 base has no
  Bluetooth; the (not installed) nRF52840 base has BLE but only via a
  proprietary AT-UART bridge, never a Linux HCI controller.
- `the-handheld-talks-bluetooth`'s USB-dongle-only design is correct as
  the only Bluetooth path for this hardware; user should not expect BT to
  work "without a dongle" on this unit.
