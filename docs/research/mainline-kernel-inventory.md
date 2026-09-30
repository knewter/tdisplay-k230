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
| RM69A10 AMOLED panel (DSI) | `drivers/gpu/drm/panel/panel-canaan-universal.c`, patched | **Upstream driver still missing; local opt-in candidate host-builds.** The pinned upstream source has no `drivers/gpu/drm/panel/panel-canaan-universal.c` and no `drivers/gpu/drm/canaan/` directory (`canaan_drv.c`/`canaan_vo.c`/`canaan_dsi.c`/`canaan_phy.c` all absent). No K230 DSI/VO/DRM patch series was found in this research's mailing-list searches. `docs/research/linux-on-t-display-k230.md` (2026-09-21) found three working Linux-on-this-panel projects, all forks of the vendor Xuantie tree. A separate local candidate in `nix/kernel-mainline-drm.nix` and `nix/patches/mainline/drm/` has a successful complete kernel, matching DTB, and Image+DTB boot-files build; see `docs/evidence/mainline-display-nix-build.md`. No board boot, panel illumination, or touch behavior is proven. | **Candidate remains hardware-unverified.** The pinned mainline source has no display power-domain provider; the opt-in DTS leaves that phandle out. The built profile does not change console-only or vendor defaults. |
| GT9895 touch | `nix/patches/goodix-berlin/` (v6.12 backport onto the vendor 6.6 tree) | **Present, unusually — already upstream on its own merits.** `gh api .../drivers/input/touchscreen/goodix_berlin_core.c` → 200 (our own backport patch header already says this: "goodix_berlin, backported from v6.12"). But **unusable without an I2C DT node**, and no I2C controller node exists in mainline's `k230.dtsi` at all yet. | **Driver needs no porting; the I2C bus DT plumbing does.** Blocked on an upstream (or our own forward-ported) I2C controller node, not on touch itself. |
| GC2093 camera | Missing-driver (vendor tree too) | **Missing-driver, same as vendor.** No CSI/ISP driver of any kind for this SoC anywhere; not investigated further here since the vendor-tree gap is already the binding constraint. | Out of scope for both trees today. |
| HDMI (Lontium LT9611) | `CONFIG_DRM_LONTIUM_LT9611=y` already, vendor tree | **Bridge driver itself is generic upstream code** (not Canaan-specific), but it is DSI-fed, so it inherits the same "no mainline DSI host" blocker as the panel row above. | Blocked on the same DSI/VO gap as the panel. |
| Wi-Fi (RTL8189FTV, SDIO) | `8189fs.ko`, vendor firmware blob | **Needs SDIO before it can even probe** — see the SD/MMC row. The RTL8189 driver itself is a separate out-of-tree module in both trees (not part of this inventory's mainline-file-presence check), so its own portability is a `radio/wifi` question, not answered here. | Blocked on SD/MMC (below), then a separate driver question. |
| SD card / SDIO (SDHCI) | Vendor board `mmc_sd0`/`mmc_sd1` nodes, generic `dw_mmc`-adjacent path | **PORTED** (2026-09-29, milestone 1). Not the in-review v5 upstream series (still unmerged at `v7.3-rc5`) — the coordinator explicitly allowed either path, and the vendor's own `drivers/mmc/host/sdhci-of-kendryte.c` (already a real, self-contained, `sdhci-pltfm.c`-layered driver matching our exact DT compatible string) was the lower-risk choice: one file, no new DT binding shape to invent. Forward-ported to `nix/patches/mainline/sdhci-of-kendryte.c`; needed one real API fix, `sdhci_pltfm_free()` (removed upstream entirely after this file's 6.6-era origin — confirmed against mainline's own `sdhci-of-dwcmshc.c`, whose probe/`.remove` call no equivalent). `nix build .#kernelMainline` confirms `CONFIG_MMC_SDHCI_OF_DWCMSHC_KENDRYTE=y`; `&mmc_sd1` (the physical TF/SD card) is `status = "okay"` in `nix/dts/k230-tdisplay-mainline.dts` with real `&sysclk`/`&rst` phandles (UNVERIFIED clock-gate/reset-ID choice — see design.md). `&mmc_sd0` (Wi-Fi SDIO) stays disabled; no Wi-Fi driver forward-ported in this pass. | Ported; board-unverified. |
| USB (DWC2 ×2, host/gadget) | `CONFIG_USB_DWC2=y`, vendor tree | **PORTED** (2026-09-29, milestone 1), via the vendor's own `dwc2_set_k230_params()`/`ctl-reg` mechanism — deliberately NOT the separately-accepted `phy-k230-usb.c`/`canaan,k230-usb-phy` generic-PHY-framework driver already present upstream (design.md decision 7: the two are non-interoperating ways of driving the same HiSysConfig registers, and only the vendor's mechanism has ever run on this board). Three small hunks ported into `drivers/usb/dwc2/{params.c,core.h,core.c}` via `nix/kernel-mainline.nix`'s postPatch (a `usb_ctl` field on `struct dwc2_core_params`, its HiSysConfig-register init in `dwc2_phy_init()`, and the `"canaan,k230-otg"` `of_match_table` entry that lets `platform.c`'s driver actually bind). No API migration needed here — confirmed by a clean build on the first attempt. `usb0`/`usb1` are `status = "okay"` in the board DTS. | Ported; board-unverified. |
| I2C (5×, `snps,designware-i2c`) | fully mainline generic driver already, vendor tree | **Driver is fully mainline** (`drivers/i2c/busses/i2c-designware-platform.c` is generic upstream code, unrelated to this SoC), but **no I2C controller DT node exists in `k230.dtsi`** at all. Not attempted in milestone 1 (scoped to boot-critical SD/GPIO/USB only). | **DT node porting needed**, driver itself needs none. Blocks touch, and every I2C-bus sensor/PMIC row in `board-capability-inventory.md`. |
| SPI (3×, `canaan,k230-spi`) | `spi-dw-mmio.c` + vendor init hook, vendor tree | **Generic `spi-dw-mmio.c` is mainline**, but no SPI controller node in `k230.dtsi`, and the vendor's small `dw_spi_canaan_k230_init()` hook has no upstream equivalent found. | DT node + a small init-hook port needed; not attempted here. |
| RTC | `drivers/rtc/rtc-k230.c`, patched (mday mask fix) | **PORTED** (2026-09-29, after milestone 1). `gh api .../drivers/rtc/rtc-k230.c` → 404 upstream; forward-ported whole file to `nix/patches/mainline/rtc-k230.c`, carrying our own already-board-proven mday-mask fix forward (0xf → 0x1f) rather than reintroducing the bug freshly. One trivial fix needed: `.remove_new` (a transitional platform_driver field from the file's 6.6-era origin) doesn't exist at `v7.3-rc5` — renamed to `.remove` (the function's signature already matched). Built cleanly on the first attempt otherwise. `rtc@91000c00` added to `nix/dts/k230-tdisplay-mainline.dts` (`status = "okay"`, no clocks/resets — the driver calls neither `devm_clk_get()` nor `devm_reset_control_get()`). | Ported; board-unverified. |
| Thermal sensor | `drivers/thermal/canaan_thermal.c`, patched (bounded read loop) | **Missing-driver.** `gh api .../drivers/thermal/canaan_thermal.c` → 404. | Cannot port yet, same reasoning as RTC. |
| Power key (PMU INT0) | `drivers/input/misc/k230-pmu-pwrkey.c`, vendored from LILYGO | **Missing-driver, no upstream PMU node/binding of any kind found.** `gh api .../drivers/input/misc/k230-pmu-pwrkey.c` → 404. | Cannot port yet. |
| Audio (I2S / MAX98357A route) | `sound/soc/canaan/canaan_k230_inno.c`, patched (external I2S switch) | **Missing-driver.** `gh api .../sound/soc/canaan/canaan_k230_inno.c` → 404; no `sound/soc/canaan/` directory at all. `sound/soc/codecs/max98357a.c` (the external amp's own codec driver) IS mainline, generic code — but it needs a machine/DAI driver and I2S controller DT node neither of which exist upstream for this SoC. | Cannot port the switch patch (nothing to patch); the codec driver itself needs no porting, but everything around it does. |
| Crypto (AES/hash/RSA/RNG/OTP) | `drivers/crypto/canaan/*`, vendor tree, unpatched | **Missing-driver.** `gh api .../drivers/crypto/canaan/kendryte-aes.c` → 404; no `drivers/crypto/canaan/` directory. | Not attempted; low value per `board-capability-inventory.md`, same conclusion holds here. |
| GPIO | `drivers/gpio/gpio-k230.c`, vendor tree, unpatched | **PORTED** (2026-09-29, milestone 1). `gh api .../drivers/gpio/gpio-k230.c` → 404 upstream; forward-ported to `nix/patches/mainline/gpio-k230.c`. Needed a real, substantial API migration, found by a failed build (`error: 'struct gpio_chip' has no member named 'bgpio_lock'`): `bgpio_init()`/`.read_reg`/`.write_reg`/`.bgpio_lock` were replaced upstream by `struct gpio_generic_chip` (`include/linux/gpio/generic.h`) sometime after this file's 6.6-era origin. Fixed against mainline's own already-migrated `gpio-dwapb.c` (this file's own stated template, "based on gpio-dwapb.c") as the reference pattern — the port struct's embedded `struct gpio_chip gc` became `struct gpio_generic_chip chip`, direct `gc->bgpio_lock`/`.read_reg`/`.write_reg` became `to_gpio_generic_chip(gc)->lock`/`.read_reg`/`.write_reg`, and `bgpio_init()` became `gpio_generic_chip_init()` against the same four MMIO addresses. `gpio0`/`gpio1` are `status = "okay"` in `nix/dts/k230-tdisplay-mainline.dts`, still gating panel reset/touch reset-IRQ/Wi-Fi-enable functionally on their own controller/bus support landing first (unaffected by this row). | Ported; board-unverified. |
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
5. `k230-rtc-mday-mask.patch` — targets `drivers/rtc/rtc-k230.c`. **Update,
   2026-09-29**: no longer "cannot port" — `drivers/rtc/rtc-k230.c` itself
   was forward-ported whole onto the mainline pin (see the RTC row above),
   carrying this exact fix forward directly in the copied file rather than
   as a separate patch against it (there being no separate upstream file
   this patch could apply to in the usual sense — the whole file is ours
   to place). Superseded, not stale: the original "cannot port" finding was
   correct at the time it was written (nothing existed to port a patch
   against); porting the driver itself is what changed.
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

**Net result at the time this section was first written: zero of our eleven
vendor-kernel patches port to mainline as patches**, because ten of them
target a file that plainly does not exist upstream, and the eleventh (the
toolchain probe) turns out to already be fixed upstream by a different,
independent change. This was not a failure of porting effort; it was the
direct, mechanical consequence of mainline having no display/audio/RTC/
power-key/thermal driver for this SoC at all yet.

**Updated, 2026-09-29, after milestone 1**: one of the ten — the RTC
mday-mask fix — has since been ported, not as a patch against an upstream
file (none existed), but by forward-porting `drivers/rtc/rtc-k230.c` itself
onto the mainline pin and carrying the fix forward in the copied file (see
the RTC row above and item 5's updated entry). The other nine (display,
audio, power-key, thermal) are unaffected — no upstream driver exists for
any of them to patch or forward-port a fix against yet. This is exactly the
pattern milestone 1's GPIO/SD-MMC/USB forward-ports also followed: porting
the whole driver, not just a patch, is what "porting" means once nothing
upstream exists to patch.

## Phased plan

Ordered so each milestone is provable before the next is attempted, per
`.skills/k230-spec-change/SKILL.md`'s QEMU-vs-hardware distinction — **every
milestone below whose evidence is board console output is hardware-only**;
none of it is provable under QEMU, because QEMU's `k230` machine in this
project models the vendor board, not a generic mainline-booted K230, and no
upstream QEMU K230 machine model was confirmed working in this research
(a QEMU-side "add SDHCI support for K230" series was found, implying machine
support is itself still incomplete upstream).

1. **Cross-builds exist** (DONE, this change): `.#kernelMainline` compiles,
   `.#deviceTreeMainline` compiles and round-trips, `.#kernelMainlineBootFiles`
   collects both under clear names. Host-only, proven by `nix build`.
2. **Reaches the serial console** (hardware-gated, not performed): U-Boot
   loads this `Image` + DTB; the CH342 console shows the OpenSBI banner and
   Linux's own early boot log over UART0, whether or not it then panics for
   lack of a root filesystem. This is the first milestone that needs the
   board, and is explicitly NOT performed by this change.
3. **Boot-critical GPIO/SD-MMC/USB forward-ported, and a matching full
   NixOS system variant** (DONE, this change's milestone-1 continuation):
   `drivers/gpio/gpio-k230.c` and `drivers/mmc/host/sdhci-of-kendryte.c`
   forward-ported from the vendor tree (one real API migration each found
   and fixed, see the GPIO and SD card/SDIO rows above); `drivers/usb/
   dwc2/{params.c,core.h,core.c}` hunks ported cleanly (no migration
   needed). `nixosConfigurations.k230-mainline-console` is configured to boot this
   kernel; `.#kernelMainlineConsoleBootFiles` bakes its real bootargs and
   wraps its initrd. This remains host-proven (`nix build`); an actual
   SD-backed boot to a login prompt remains milestone 4's hardware gate.
4. **Reaches an interactive shell over SD** (hardware-gated, not
   performed): the milestone-3 candidate's own pass condition — does
   `k230-mainline-console`'s boot files actually reach a login prompt over
   the physical card's `NIXOS_SD`-labeled root partition. Genuinely open:
   whether `&mmc_sd1` probes at all with this change's best-effort
   clock/reset IDs, whether by-label root resolution works the same way
   under mainline as it does under the vendor kernel, and whether this
   system's own closure/profile is even staged on that card (this change
   does not stage it). See tasks.md's "Remaining evidence gate".
5. **Wi-Fi (SDIO) + wider USB (network)**: `&mmc_sd0` stays disabled and no
   RTL8189FTV driver was forward-ported in this pass (out-of-tree, and not
   expected to compile against this kernel unmodified — see design.md
   decision 9); a USB-Ethernet dongle or a forward-ported Wi-Fi driver
   would follow milestone 4, not before it.
6. **I2C/SPI DT plumbing**: unblocks touch (driver already present, per the
   inventory row) and any future PMIC/sensor work, independent of display.
   Not attempted in milestone 1 (scoped to boot-critical SD/GPIO/USB only).
7. **RTC — PORTED** (2026-09-29, first item of what was originally
   milestone 7): `drivers/rtc/rtc-k230.c` forward-ported whole, one trivial
   `.remove_new`→`.remove` fix, `rtc@91000c00` added to the board DTS. Built
   cleanly on the first attempt — no API migration needed, unlike GPIO/
   SD-MMC. Board-unverified, same as every row in this document.
8. **Display, audio, power key, thermal, crypto, ADC, PWM**: each missing
   upstream drivers, with no in-progress public series found. The local
   DRM candidate is tracked separately from upstream mainline. Display was
   initially scoped without a port, then resumed in task group 5b of the
   OpenSpec change. The historical scratch trial copied the vendor's
   `canaan_drv.c`/`canaan_vo.c`/`canaan_dsi.c`/`canaan_phy.c`/
   `canaan_plane.c` plus `panel-canaan-universal.c` (about 3,900 lines,
   before project-specific patches) and exposed structural DRM API changes:
   `drm_panel_init()` had been replaced by `devm_drm_panel_alloc()`, along
   with Kconfig dependency and removed-symbol adjustments. That trial was
   discarded, then the coordinator authorized a separate opt-in derivation.
   The resumed source adapts the panel allocation, fbdev/client setup,
   atomic helper signatures, and platform remove callbacks. The prepared-header
   API check is an external-module build; it emits expected modpost warnings
   and is not an in-tree link proof
   (`docs/evidence/mainline-display-api-compile.md`).
   The first full kernel attempt reached the vmlinux link and exposed missing
   `DRM_DISPLAY_HELPER`/`DRM_BRIDGE_CONNECTOR` Kconfig selections; after
   adding them, the corrected object/config check and full Nix derivations
   succeeded (`docs/evidence/mainline-display-nix-build.md`).
   The separate opt-in DRM display/touch DT source and Image+DTB bundle now
   exist; host DTS, complete kernel/DTB/boot-files builds, and the Kconfig
   correction are recorded in `docs/evidence/mainline-display-dtb.md` and
   `docs/evidence/mainline-display-nix-build.md`.
   Physical probe remains open. The candidate omits the vendor display power
   domain because the pinned mainline tree has no provider for it. The other six
   (audio, power key, thermal, crypto, ADC, PWM) are individually much
   closer in size/shape to RTC (single small self-contained files) and are
   plausible next candidates for the same methodology. Not scheduled
   further in this pass; continue the RTC-style pattern for the smaller
   remaining drivers.

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
