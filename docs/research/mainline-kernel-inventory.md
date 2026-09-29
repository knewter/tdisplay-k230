# Mainline kernel inventory: what upstream Linux can drive on this board

Researched 2026-09-29 for `openspec/changes/the-board-runs-a-mainline-kernel`.
Answers, per hardware function this board uses today
(`docs/research/board-capability-inventory.md`), one additional question that
document does not: **can mainline Linux drive this at all, and if not, what
is the exact blocking upstream state?**

## How to read this document

Same grounding tiers as `.skills/k230-spec-change/SKILL.md` and
`board-capability-inventory.md`. Two additional evidence tools used
specifically here, both checked directly on 2026-09-29 and cited by exact
command:

- **File existence in `torvalds/linux`**: `gh api
  repos/torvalds/linux/contents/<path>` — HTTP 200 means the file is present
  at the tip of the default branch, 404 means it is not. This is a strong,
  cheap, mechanical check; it is not a Kconfig/DT-wiring check (a present
  file can still be unusable for this board if no device-tree node
  references it — see the USB row).
- **Mainline device-tree contents**: fetched directly from
  `raw.githubusercontent.com/torvalds/linux/master/...` and from the pinned
  tag's tree (`git show v7.2:...`, `git ls-remote --tags`), not inferred from
  changelogs.

## Target version

**kernel.org, 2026-09-25**: latest stable is **7.2.8**; latest longterm is
**6.1.188**. Neither carries any Canaan K230 support — checked directly:
`git show v7.2:arch/riscv/boot/dts/canaan/` lists only `k210.dtsi`,
`k210_generic.dts`, `canaan_kd233.dts` and the four `sipeed_maix_*.dts`
files; no `k230.dtsi`.

Basic K230 support (`ARCH_CANAAN`'s `PINCTRL_K230`, `RESET_K230`,
`COMMON_CLK_K230`, and `arch/riscv/boot/dts/canaan/k230.dtsi` +
`k230-canmv.dts` + `k230-evb.dts`) merged for the **v7.3 merge window**
("[GIT PULL] RISC-V devicetrees for v7.3", July 2026; "too late for the 7.2
window" per the clock-driver pull thread). **v7.3-rc1 released 2026-09-01**;
the current tip as of this research is **v7.3-rc5**
(`72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`), with **no stable v7.3 release
yet**. This change pins that commit — see `nix/kernel-mainline-src.nix` for
exactly why (the newest tag that actually has K230 support, not an
unreleased moving `master`).

## What mainline's `k230.dtsi` actually contains today

Fetched directly, `raw.githubusercontent.com/torvalds/linux/master/arch/riscv/boot/dts/canaan/k230.dtsi`:
`cpus` (2× `thead,c908` @ 1.6/0.8 GHz is NOT modeled — mainline's dtsi
describes only ONE `cpu@0`; see "Second C908 core" row), `plic`
(`canaan,k230-plic`+`thead,c900-plic`), `clint` (ditto pattern), a reset
controller (`canaan,k230-rst`), a pinctrl node (`canaan,k230-pinctrl`, no
consumer groups defined anywhere upstream), a clock controller
(`canaan,k230-clk`), and `uart0`–`uart4` (`snps,dw-apb-uart`, all
`status = "disabled"` by default). **Nothing else.** No mmc/sdhci, usb, i2c,
spi, pwm, rtc, adc, watchdog, gpio, crypto, or thermal node exists in this
file. `k230-canmv.dts` and `k230-evb.dts` each enable `uart0` and add a
board memory node; `k230-canmv.dts` additionally wires pinmux groups for
uart2/uart3/uart4, PWM, I2S, I2C0/1/3/4, and an `mmc1` SD slot pin group —
but with no matching controller node in `k230.dtsi` for most of those buses
yet, those pinmux groups currently mux pins for hardware nothing in this
tree can drive.

## Inventory

| Function | Vendor driver (this project, `nix/kernel.nix`) | Mainline status | Porting strategy |
| --- | --- | --- | --- |
| Serial console (UART0) | `snps,dw-apb-uart`, mainline 8250 code already | **Present.** `k230.dtsi`'s `uart0` node is byte-identical in shape to the vendor tree's; `docs/research/board-capability-inventory.md` already confirms our board's console *is* UART0, and neither tree's device tree programs UART0's pinmux (both rely on U-Boot's FPIOA table) — see `nix/dts/k230-tdisplay-mainline.dts`'s header for the full citation chain. | **Use upstream as-is.** No patch needed; only a board `.dts` enabling it (`nix/dts/k230-tdisplay-mainline.dts`, this change). |
| SoC platform (PLIC/CLINT/reset/clock/pinctrl) | Vendor tree's own copies of the same IP blocks | **Present**, merged for v7.3: `PINCTRL_K230` (`drivers/pinctrl/canaan/pinctrl-k230-iomux.c`), `RESET_K230` (`drivers/reset/reset-k230.c`), `COMMON_CLK_K230`. All gate on `ARCH_CANAAN`. | **Use upstream as-is.** `nix/kernel-mainline.nix` turns on all three. |
| Second C908 core | N/A — `system/second-core-readiness`, not attempted | **Not modeled at all.** Mainline's `k230.dtsi` `cpus` node has exactly one `cpu@0`; there is no `cpu@1` upstream to even describe the second hart, independent of whether Linux SMP release would be safe (see that capability's own gating). | **Blocked upstream**, not just on us — a future upstream patch would need to add the second hart's CPU node before this project's own SMP-safety gating even becomes relevant. |
| RM69A10 AMOLED panel (DSI) | `drivers/gpu/drm/panel/panel-canaan-universal.c`, patched | **Missing-driver, no visible upstream work.** `gh api repos/torvalds/linux/contents/drivers/gpu/drm/panel/panel-canaan-universal.c` → 404; no `drivers/gpu/drm/canaan/` directory (`canaan_drv.c`/`canaan_vo.c`/`canaan_dsi.c`/`canaan_phy.c` all 404). No K230 DSI/VO/DRM patch series found in any of this research's mailing-list searches (SDHCI, USB, pinctrl, clk, reset, PCI all turned up multi-revision threads; display did not turn up any). `docs/research/linux-on-t-display-k230.md` (this repo, 2026-09-21) independently found three working Linux-on-this-panel projects, and every one of them is a **fork of the vendor Xuantie tree**, not a mainline submission. | **Forward-port the vendor driver as an out-of-tree module set**, or wait — there is no third option visible today. This is the single largest gap standing between mainline and this handheld's actual shell; nothing in this change attempts it. |
| GT9895 touch | `nix/patches/goodix-berlin/` (v6.12 backport onto the vendor 6.6 tree) | **Present, unusually — already upstream on its own merits.** `gh api .../drivers/input/touchscreen/goodix_berlin_core.c` → 200 (our own backport patch header already says this: "goodix_berlin, backported from v6.12"). But **unusable without an I2C DT node**, and no I2C controller node exists in mainline's `k230.dtsi` at all yet. | **Driver needs no porting; the I2C bus DT plumbing does.** Blocked on an upstream (or our own forward-ported) I2C controller node, not on touch itself. |
| GC2093 camera | Missing-driver (vendor tree too) | **Missing-driver, same as vendor.** No CSI/ISP driver of any kind for this SoC anywhere; not investigated further here since the vendor-tree gap is already the binding constraint. | Out of scope for both trees today. |
| HDMI (Lontium LT9611) | `CONFIG_DRM_LONTIUM_LT9611=y` already, vendor tree | **Bridge driver itself is generic upstream code** (not Canaan-specific), but it is DSI-fed, so it inherits the same "no mainline DSI host" blocker as the panel row above. | Blocked on the same DSI/VO gap as the panel. |
| Wi-Fi (RTL8189FTV, SDIO) | `8189fs.ko`, vendor firmware blob | **Needs SDIO before it can even probe** — see the SD/MMC row. The RTL8189 driver itself is a separate out-of-tree module in both trees (not part of this inventory's mainline-file-presence check), so its own portability is a `radio/wifi` question, not answered here. | Blocked on SD/MMC (below), then a separate driver question. |
| SD card / SDIO (SDHCI) | Vendor board `mmc_sd0`/`mmc_sd1` nodes, generic `dw_mmc`-adjacent path | **In review, not merged into this pin.** The generic controller driver this series reuses, `drivers/mmc/host/sdhci-of-dwcmshc.c`, is already present upstream (`gh api` → 200) — what is missing is the K230-specific DT binding + compatible string + `k230.dtsi` node. Five revisions found (v1 Feb 2026 through v5 March 2026); v5's own cover letter states it was "tested successfully on the CanMV-K230-V1.1 with AP6212 SDIO WiFi module on MMC0 and MicroSD card on MMC1" — a real, working, out-of-tree patch, just not merged as of `v7.3-rc5`. | **Forward-port the v5 series as a local patch** onto `nix/kernel-mainline-src.nix`, the same pattern this project already uses for vendor-tree gaps — not attempted in this change; named as the next concrete task in tasks.md. |
| USB (DWC2 ×2, host/gadget) | `CONFIG_USB_DWC2=y`, vendor tree | **Split state: driver accepted, DT wiring not yet landed in this pin.** The K230 USB-PHY driver and its device-tree *binding* were accepted upstream (`lkml.org/lkml/2026/2/27/1255`, Vinod Koul: "applied", commits `50357e7d79...` for the binding and `8787fa1da6...` for the driver) — but `k230.dtsi`/`k230-canmv.dts` at `v7.3-rc5` still has **no usb/usb-phy/dwc2 node at all** (checked directly, same fetch that found no mmc/i2c/spi/pwm nodes). Driver-ready, DT-not-wired — the same shape as several rows in `board-capability-inventory.md` (e.g. this board's own RTC), just one layer further upstream. | **Forward-port the DT node** once the accepted binding's exact property names are read from the merged commit; the driver code itself needs no porting. Not attempted in this change. |
| I2C (5×, `snps,designware-i2c`) | fully mainline generic driver already, vendor tree | **Driver is fully mainline** (`drivers/i2c/busses/i2c-designware-platform.c` is generic upstream code, unrelated to this SoC), but **no I2C controller DT node exists in `k230.dtsi`** at all. | **DT node porting needed**, driver itself needs none. Blocks touch, and every I2C-bus sensor/PMIC row in `board-capability-inventory.md`. |
| SPI (3×, `canaan,k230-spi`) | `spi-dw-mmio.c` + vendor init hook, vendor tree | **Generic `spi-dw-mmio.c` is mainline**, but no SPI controller node in `k230.dtsi`, and the vendor's small `dw_spi_canaan_k230_init()` hook has no upstream equivalent found. | DT node + a small init-hook port needed; not attempted here. |
| RTC | `drivers/rtc/rtc-k230.c`, patched (mday mask fix) | **Missing-driver.** `gh api .../drivers/rtc/rtc-k230.c` → 404. Nothing to patch; our mday-mask fix has no upstream file to apply to. | Cannot port yet. Would need the driver itself upstreamed or forward-ported first — bigger lift than patching an existing file. |
| Thermal sensor | `drivers/thermal/canaan_thermal.c`, patched (bounded read loop) | **Missing-driver.** `gh api .../drivers/thermal/canaan_thermal.c` → 404. | Cannot port yet, same reasoning as RTC. |
| Power key (PMU INT0) | `drivers/input/misc/k230-pmu-pwrkey.c`, vendored from LILYGO | **Missing-driver, no upstream PMU node/binding of any kind found.** `gh api .../drivers/input/misc/k230-pmu-pwrkey.c` → 404. | Cannot port yet. |
| Audio (I2S / MAX98357A route) | `sound/soc/canaan/canaan_k230_inno.c`, patched (external I2S switch) | **Missing-driver.** `gh api .../sound/soc/canaan/canaan_k230_inno.c` → 404; no `sound/soc/canaan/` directory at all. `sound/soc/codecs/max98357a.c` (the external amp's own codec driver) IS mainline, generic code — but it needs a machine/DAI driver and I2S controller DT node neither of which exist upstream for this SoC. | Cannot port the switch patch (nothing to patch); the codec driver itself needs no porting, but everything around it does. |
| Crypto (AES/hash/RSA/RNG/OTP) | `drivers/crypto/canaan/*`, vendor tree, unpatched | **Missing-driver.** `gh api .../drivers/crypto/canaan/kendryte-aes.c` → 404; no `drivers/crypto/canaan/` directory. | Not attempted; low value per `board-capability-inventory.md`, same conclusion holds here. |
| GPIO | `drivers/gpio/gpio-k230.c`, vendor tree, unpatched | **Missing-driver.** `gh api .../drivers/gpio/gpio-k230.c` → 404. Blocks GPIO-gated peripherals generally (panel reset, touch reset/IRQ, Wi-Fi enable line) even once their own controller/bus support lands. | Not attempted. |
| ADC / PWM | `k230-adc.c` / (PWM controller, unnamed vendor file) | **Missing-driver**, both `gh api` 404. | Not attempted; low value per `board-capability-inventory.md`. |
| NPU/KPU | Closed nncase runtime; thin kernel shim only | **Not investigated for mainline** — the blocking constraint is the closed userspace runtime either way (`docs/blob-inventory.md` B1/B2), so mainline kernel-shim status does not change the conclusion. | Out of scope. |

## Our eleven vendor-kernel patches, and which of them mainline needs

Every patch lives in `nix/kernel.nix`'s `applyPatches`/`postPatch`. Checked
against the table above:

1. `riscv-vector-toolchain-probe.patch` (Kconfig `TOOLCHAIN_HAS_V` missing
   the `m` extension in its `-march` probe string) — **already fixed
   upstream.** Fetched directly,
   `raw.githubusercontent.com/torvalds/linux/master/arch/riscv/Kconfig`:
   current mainline already reads `-march=rv64imv`/`-march=rv32imv`, exactly
   this patch's fix. **Does not need porting; nothing to apply it to.**
2. `canaan-dsi-implement-dcs-read.patch` — targets
   `panel-canaan-universal.c`. **Cannot port**: file does not exist upstream
   (missing-driver row above).
3. `canaan-panel-read-back-id-and-power-mode.patch` — same file. **Cannot
   port**, same reason.
4. `canaan-audio-external-i2s-switch.patch` — targets
   `sound/soc/canaan/canaan_k230_inno.c`. **Cannot port**: no such file or
   directory upstream.
5. `k230-rtc-mday-mask.patch` — targets `drivers/rtc/rtc-k230.c`. **Cannot
   port**: file does not exist upstream.
6. `k230-pmu-pwrkey.c` (a whole vendored driver, not a patch against an
   existing file) — **cannot be ported as a patch** since there is no
   upstream PMU infrastructure to patch; porting it would mean submitting
   the whole driver + DT binding, out of scope here.
7. `goodix-berlin` backport — **moot**: mainline at this pin already has the
   real v6.12+ driver natively; forward-porting our *backport* would be
   backporting mainline onto itself. Nothing to do except add the I2C DT
   plumbing this row is actually blocked on.
8. The `panel-canaan-universal.c`/`canaan_drv.c`/`canaan_vo.c`/
   `canaan_dsi.c`/`canaan_phy.c` postPatch hunks (bounded PHY wait, DSI
   message transport, stage-1 splash handoff, PM-runtime pin, DT-settable
   `hsfreqrange`, DSI backlight, DPMS restore) — **cannot port, any of
   them**: none of these files exist upstream. This is the same conclusion
   as the panel row above, restated patch by patch so no partial-port is
   silently skipped.
9. `canaan_thermal.c`'s bounded-read-loop fix — **cannot port**: file does
   not exist upstream.
10. `fbdev bpp` sed (`drm_fbdev_generic_setup(drm_dev, 32)` → `16`) — targets
    `canaan_drv.c`. **Cannot port**, same reason.

**Net result: zero of our eleven vendor-kernel patches port to mainline as
patches**, because ten of them target a file that plainly does not exist
upstream, and the eleventh (the toolchain probe) turns out to already be
fixed upstream by a different, independent change. This is not a failure of
porting effort; it is the direct, mechanical consequence of mainline having
no display/audio/RTC/power-key/thermal driver for this SoC at all yet — the
same conclusion the proposal states going in, now confirmed patch by patch
rather than asserted.

## Phased plan

Ordered so each milestone is provable before the next is attempted, per
`.skills/k230-spec-change/SKILL.md`'s QEMU-vs-hardware distinction — **every
milestone below whose evidence is board console output is hardware-only**;
none of it is provable under QEMU, because QEMU's `k230` machine in this
project models the vendor board, not a generic mainline-booted K230, and no
upstream QEMU K230 machine model was confirmed working in this research
(a QEMU-side "add SDHCI support for K230" series was found, implying machine
support is itself still incomplete upstream).

1. **Cross-builds exist** (this change): `.#kernelMainline` compiles,
   `.#deviceTreeMainline` compiles and round-trips, `.#kernelMainlineBootFiles`
   collects both under clear names. Host-only, proven by `nix build`.
2. **Reaches the serial console** (next change, hardware-gated): U-Boot
   loads this `Image` + DTB; the CH342 console shows the OpenSBI banner and
   Linux's own early boot log over UART0, whether or not it then panics for
   lack of a root filesystem. This is the first milestone that needs the
   board, and is explicitly NOT performed by this change.
3. **Reaches an interactive shell**: requires either a built-in initramfs
   (no SD/USB dependency, buildable today) or the forward-ported SDHCI v5
   series for a real SD rootfs. Not attempted in this change; the initramfs
   route is the cheaper of the two and does not wait on any upstream
   patch landing.
4. **SD rootfs**: forward-port the SDHCI v5 series onto
   `nix/kernel-mainline-src.nix` as a local patch (the same pattern
   `nix/kernel.nix` already uses for the vendor tree), add the K230-specific
   MMC DT nodes, and prove an SD-backed root mounts.
5. **USB + network**: forward-port the accepted USB-PHY binding's DT node
   (driver itself needs no porting — already accepted upstream) plus a DWC2
   controller node; prove host-mode USB, then a USB-Ethernet or Wi-Fi (SDIO,
   downstream of milestone 4) link.
6. **I2C/SPI DT plumbing**: unblocks touch (driver already present, per the
   inventory row) and any future PMIC/sensor work, independent of display.
7. **Display, audio, RTC, power key, thermal, crypto, GPIO, ADC, PWM**: each
   blocked on a missing upstream driver with no in-progress public series
   found. Each would need either a real upstream submission (this project's
   own vendor-driver forward-ports are a plausible starting point for a
   future submission, but are not drop-in patches against anything that
   exists yet) or continuing to run these functions from the vendor kernel
   indefinitely. Not scheduled; revisit if upstream activity appears.

## Sources

- kernel.org (fetched 2026-09-25 per its own page: 7.2.8 stable, 6.1.188
  longterm).
- `torvalds/linux` `git ls-remote --tags` (v7.2 through v7.3-rc5, this
  research, 2026-09-29).
- `git show v7.2:arch/riscv/boot/dts/canaan/` vs.
  `raw.githubusercontent.com/torvalds/linux/master/arch/riscv/boot/dts/canaan/`
  (file listing diff).
- `raw.githubusercontent.com/torvalds/linux/master/arch/riscv/boot/dts/canaan/k230.dtsi`,
  `k230-evb.dts`, `arch/riscv/Kconfig.socs`, `arch/riscv/Kconfig`,
  `drivers/pinctrl/Kconfig`, `drivers/reset/Kconfig`, `drivers/clk/Kconfig`
  (exact Kconfig stanzas quoted above and in `nix/kernel-mainline.nix`).
- `gh api repos/torvalds/linux/contents/<path>` for every "present"/"missing"
  driver-file claim above (2026-09-29).
- Ratatoskr/lkml.org mailing-list archive links for the SDHCI ("[PATCH v5 0/3]
  Add SDHCI support for Canaan K230 SoC", March 2026) and USB ("[PATCH v5 0/4]
  Add USB support for Canaan K230", lkml.org/lkml/2026/2/27/1255) series.
- `docs/research/board-capability-inventory.md` and
  `docs/research/linux-on-t-display-k230.md` (this repo), for the vendor-side
  baseline this document adds a mainline-status column to.
