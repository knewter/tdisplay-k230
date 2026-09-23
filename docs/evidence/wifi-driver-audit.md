# RTL8189FTV driver audit

Date: 2026-09-22. This is a host-side source and configuration audit. It does
not claim that the physical board has bound a driver or that its radio works.

## Observed board function and current kernel closure

[`wifi-preflight.txt`](wifi-preflight.txt) records one SDIO function at
`mmc0:0001:1`, with vendor `0x024c`, device `0xf179`, and modalias
`sdio:c07v024CdF179`. Its `driver` symlink is empty, `/sys/class/ieee80211`
is empty, and the deployed 6.6.36 closure's Realtek directory contains only
`rtw88`. The same capture establishes that `iw`, `wpa_supplicant`,
`wpa_cli`, and `regulatory.db` were absent. It is the source for the
enumeration and loaded-module conclusions here.

The credential-free boot log in
[`shell-features/desktop-launcher/image-boot.txt`](shell-features/desktop-launcher/image-boot.txt)
records `Linux version 6.6.36`, the SDIO enumeration, and `cfg80211` loading
before it reports that `regulatory.db` is absent. That establishes generic
wireless support in the running kernel, without substituting for a driver
binding.

The exact kernel is the Xuantie source pin in
[`nix/kernel-src.nix`](../../nix/kernel-src.nix):
[`ruyisdk/linux-xuantie-kernel` commit
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`](https://github.com/ruyisdk/linux-xuantie-kernel/tree/7d4e1f444f461dbe3833bd99a4640e7b6c2cd529),
built by [`nix/kernel.nix`](../../nix/kernel.nix) as version `6.6.36-xuantie`
with module directory `6.6.36`. Its built configuration has `CONFIG_MMC=y`,
`CONFIG_MMC_SDHCI=y`, `CONFIG_MMC_SDHCI_OF_DWCMSHC_KENDRYTE=y`,
`CONFIG_CFG80211=y`, `CONFIG_MAC80211=y`, and `CONFIG_FW_LOADER=y`; it has
only the unrelated `RTW88` Realtek module family and no RTL8189 SDIO module.
The supplied board DTS enables the SDIO controller but names no Wi-Fi
regulator or GPIO power control
([`nix/dts/k230-tdisplay.dts`](../../nix/dts/k230-tdisplay.dts)). Since the
function already enumerates, no device-tree GPIO change is justified by this
host audit; task 1.2 remains a board-and-boot-log decision.

## Selected source and compatible ID

The selected source is
[`jwrdegoede/rtl8189ES_linux` commit
`94cc959d56c1425fbca4f6e49e949cf58ec5dc8d`](https://github.com/jwrdegoede/rtl8189ES_linux/tree/94cc959d56c1425fbca4f6e49e949cf58ec5dc8d),
pinned in [`nix/k230-wifi-driver.nix`](../../nix/k230-wifi-driver.nix) with a
fixed SHA-256. Its SDIO table has
[`SDIO_DEVICE(0x024c, 0xF179)`](https://github.com/jwrdegoede/rtl8189ES_linux/blob/94cc959d56c1425fbca4f6e49e949cf58ec5dc8d/os_dep/linux/sdio_intf.c#L71),
conditionally selected by `CONFIG_RTL8188F`, and exports the table with
`MODULE_DEVICE_TABLE(sdio, sdio_ids)`. The source's SDIO configuration selects
that chipset and calls the output module
[`8189fs`](https://github.com/jwrdegoede/rtl8189ES_linux/blob/94cc959d56c1425fbca4f6e49e949cf58ec5dc8d/Makefile#L720-L731).
Therefore the installed module is `8189fs.ko`; the marketing name RTL8189FTV
and the source's RTL8188F chipset label are not interchangeable evidence of a
bound board driver.

Source files carry GPL version 2 notices, including
[`sdio_intf.c`](https://github.com/jwrdegoede/rtl8189ES_linux/blob/94cc959d56c1425fbca4f6e49e949cf58ec5dc8d/os_dep/linux/sdio_intf.c#L3-L12),
and the Nix derivation declares `GPL-2.0-only`.

## Kernel API and firmware conclusions

The selected revision includes compatibility branches through Linux 6.13;
notably its cfg80211 code has a branch for the 6.3--6.8 API interval and later
branches. The authoritative compatibility result is the derivation's narrow
build against the exact `6.6.36` kernel headers, rather than a version-range
claim. On 2026-09-22, `nix build .#k230-wifi-driver --max-jobs 1 --cores 8`
succeeded. The produced `8189fs.ko` reports `vermagic: 6.6.36 SMP mod_unload
riscv`, `license: GPL`, and `alias: sdio:c*v024CdF179*`. This proves its
build-time ABI and modalias metadata only; a board bind remains unverified.

No separate firmware package is required for this driver. The selected
RTL8188F configuration defines `LOAD_FW_HEADER_FROM_DRIVER` in
[`include/autoconf.h`](https://github.com/jwrdegoede/rtl8189ES_linux/blob/94cc959d56c1425fbca4f6e49e949cf58ec5dc8d/include/autoconf.h#L150),
and the firmware array is compiled from
[`hal/rtl8188f/hal8188f_fw.c`](https://github.com/jwrdegoede/rtl8189ES_linux/blob/94cc959d56c1425fbca4f6e49e949cf58ec5dc8d/hal/rtl8188f/hal8188f_fw.c#L20).
`regulatory.db` remains a separate regulatory-data requirement for userspace
and cfg80211, not RTL8189 firmware.
