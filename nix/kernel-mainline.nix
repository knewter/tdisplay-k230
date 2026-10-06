# A parallel, opt-in mainline kernel build for the T-Display-K230.
#
# openspec/changes/the-board-runs-a-mainline-kernel. This is NOT the kernel
# any DEFAULT nixosConfigurations output boots -- see nix/kernel.nix for
# that. `nixosConfigurations.k230-mainline-console` (flake.nix) is the one
# opt-in system that does boot this kernel.
#
# WHAT MAINLINE (v7.3-rc5, nix/kernel-mainline-src.nix) HAD BEFORE this
# file's forward ports, checked directly against that pinned tree and
# against `gh api repos/torvalds/linux/contents/<path>` on 2026-09-29
# (200 = present, 404 = absent):
#
#   present : ARCH_CANAAN, PINCTRL_K230 (pinctrl-k230-iomux.c), RESET_K230
#             (reset-k230.c), COMMON_CLK_K230, arch/riscv/boot/dts/canaan/
#             k230.dtsi + k230-canmv.dts + k230-evb.dts (UART0 console only
#             -- no mmc/usb/i2c/spi/pwm/adc/rtc/watchdog/gpio/crypto/thermal
#             node). goodix_berlin touchscreen is present (mainline code we
#             ourselves backported onto the vendor tree), but still unusable
#             here without an I2C DT node, which does not exist upstream for
#             this SoC yet either. drivers/phy/canaan/phy-k230-usb.c and its
#             DT binding (Documentation/devicetree/bindings/phy/
#             canaan,k230-usb-phy.yaml) are present too, but this change
#             does NOT use them -- see the USB section below.
#   absent  : drivers/gpu/drm/canaan/, drivers/gpu/drm/panel/
#             panel-canaan-universal.c, sound/soc/canaan/, drivers/rtc/
#             rtc-k230.c, drivers/thermal/canaan_thermal.c, drivers/iio/adc/
#             k230-adc.c, drivers/pwm/pwm-k230.c, drivers/input/misc/
#             k230-pmu-pwrkey.c, drivers/crypto/canaan/. RTC, power-key and
#             thermal are now forward-ported BY this file (see below); our
#             display/audio/ADC/PWM/crypto patches still have nothing to
#             patch here -- unchanged by this file.
#
# THIS FILE'S OWN FORWARD PORTS (milestone 1: boot-critical SD/GPIO/USB),
# every one of them copied or ported from the pinned VENDOR tree
# (ruyisdk/linux-xuantie-kernel @ 7d4e1f444f461dbe3833bd99a4640e7b6c2cd529),
# not invented:
#
#   - drivers/mmc/host/sdhci-of-kendryte.c (nix/patches/mainline/): a real,
#     dedicated driver already in the vendor tree for `compatible =
#     "canaan,k230-dw-mshc"`, layered on the generic, already-mainline
#     sdhci-pltfm.c. Copied verbatim except one signature fix:
#     `.remove` changed from `int (*)(struct platform_device *)` to
#     `void (*)(...)`, matching v7.3-rc5's struct platform_driver (that
#     signature changed upstream around v6.11, after this file's 6.6-era
#     vendor origin). Confirmed directly against
#     include/linux/platform_device.h at this exact pinned commit.
#   - drivers/gpio/gpio-k230.c (nix/patches/mainline/): likewise a real,
#     dedicated driver for `compatible = "canaan,k230-apb-gpio"` (NOT
#     handled by mainline's generic gpio-dwapb.c, whose own of_match_table
#     only lists "snps,dw-apb-gpio"/"apm,xgene-gpio-v2" -- checked
#     directly). NOT a verbatim copy: this file's `bgpio_init()` and
#     `struct gpio_chip`'s `.read_reg`/`.write_reg`/`.bgpio_lock` were
#     replaced upstream, after this file's 6.6-era vendor origin, by
#     `struct gpio_generic_chip` (include/linux/gpio/generic.h) --
#     `to_gpio_generic_chip()`, `gpio_generic_chip_init()`, and a `.lock`
#     field replacing `.bgpio_lock`. Found the hard way, by a failed build
#     (`error: 'struct gpio_chip' has no member named 'bgpio_lock'`), then
#     fixed against mainline's own already-migrated gpio-dwapb.c as the
#     reference pattern (same struct shape, same "based on gpio-dwapb.c"
#     lineage this file's own header comment claims). The port struct's
#     embedded `struct gpio_chip gc` became `struct gpio_generic_chip
#     chip` (with `.gc` still reachable as `chip.gc`), every direct
#     `gc->bgpio_lock`/`.read_reg`/`.write_reg` became
#     `to_gpio_generic_chip(gc)->lock`/`.read_reg`/`.write_reg`, and the
#     `bgpio_init()` call became `gpio_generic_chip_init()` against a
#     `struct gpio_generic_chip_config` built from the exact same four MMIO
#     addresses and register width the vendor call already used -- no new
#     hardware behavior invented, only the calling convention changed.
#   - drivers/usb/dwc2/{params.c,core.h,core.c}: three small sed hunks (see
#     postPatch below) porting the vendor tree's OWN addition of a
#     `dwc2_set_k230_params()` parameter profile and its `usb_ctl` register
#     read -- NOT the newer, separately-accepted phy-k230-usb.c/
#     canaan,k230-usb-phy driver. Both mechanisms exist in mainline's
#     drivers/phy/canaan/ now, but they are two different, non-interoperating
#     ways of driving the same HiSysConfig USB control registers, and only
#     the vendor's ctl-reg mechanism is what nix/dts/k230-tdisplay.dts's
#     sibling board file (k230-tdisplay-mainline.dts) actually wires up --
#     reusing the vendor's own proven mechanism, rather than inventing a
#     phy-framework-based binding nobody has run on this board, is the
#     lower-risk choice for a first forward-port. A later change could
#     replace this with the phy-framework driver if it proves more correct.
#   - drivers/input/misc/k230-pmu-pwrkey.c (nix/patches/mainline/,
#     openspec/changes/the-mainline-shell-reaches-parity task 4.1): this
#     project's own VENDOR-kernel power-key driver
#     (nix/patches/k230-pmu-pwrkey.c), unchanged in register behavior.
#     `.remove` gets the same int -> void signature fix as the other
#     drivers above, and probe now claims the PMU APB gate
#     (K230_PMU_APB_GATE) as an optional "pclk" clock -- the same gate
#     rtc-k230.c below already had to claim, since the power key lives in
#     the same PMU block and mainline's unused-clock cleanup would
#     otherwise gate it.
#   - drivers/thermal/canaan_thermal.c (nix/patches/mainline/,
#     openspec/changes/the-mainline-shell-reaches-parity task 7.1): ported
#     from the pinned VENDOR tree's own drivers/thermal/canaan_thermal.c.
#     Three changes: the same bounded-read-loop fix nix/kernel.nix already
#     applies by sed to the vendor build (bounded iteration count +
#     usleep_range instead of an unbounded busy-poll that has soft-locked
#     this board before), devm_ioremap_resource(dev, res) ->
#     devm_platform_ioremap_resource(pdev, 0) (the two-argument form no
#     longer exists in v7.3-rc5), and a void `.remove`. Probe claims the
#     temperature sensor's own rate clock (K230_SYSCTL_TEMP_SENSOR_RATE)
#     as an optional "ts" clock, for the same unused-clock-cleanup reason.
#   - sound/soc/canaan/{canaan_k230_audio,canaan_k230_inno}.c and
#     sound/soc/codecs/inno_k230{,_reg}.c (task 5.1, openspec/changes/
#     the-mainline-shell-reaches-parity): the SAI mux, Inno codec and
#     "canaan,k230-audio-inno" machine driver, forward-ported with this
#     project's own external-I2S-switch control folded in and explicit
#     claims added for K230_LS_AUDIO_APB_GATE/K230_LS_CODEC_APB_GATE (see
#     each file's own header comment). This board's only known i2s DT
#     node (k230.dtsi) carries no `interrupts` property, so dw_i2s_probe()
#     takes the dmaengine_pcm path, which needs a DMA provider for
#     `compatible = "canaan,k230-pdma"` -- see the PDMA entry directly
#     below, which resolves this.
#   - drivers/dma/k230-peridma.c (nix/patches/mainline/, task 5.1 follow-up):
#     the vendor's drivers/dma/k230_peridma.c (~1400-line register-level
#     descriptor-chain DMA engine, not a dw-axi-dmac/dw_dmac variant),
#     forward-ported essentially unchanged (register programming has no
#     kernel-version dependency) except for v7.3-rc5 dmaengine/platform_driver
#     API currency: void-returning `.remove`, and the probe's clock claim
#     changed to `devm_clk_get_enabled()` (K230_SHRM_PDMA_AXI_GATE,
#     drivers/clk/clk-k230.c, confirmed register-offset/bit-identical to the
#     vendor DT's own `pdma_aclk_gate` node). See that file's own header
#     comment for the full API-delta list. Unblocks the audio dmaengine_pcm
#     path above.
#   - sound/soc/dwc_canaan/{canaan-dwc-i2s,canaan-dwc-pcm,canaan-local}
#     (nix/patches/mainline/dwc_canaan/, task 5.x): BOARD-PROVEN this
#     project's earlier plan -- reusing mainline's own, already-present
#     sound/soc/dwc/dwc-i2s.c (compatible "snps,designware-i2s") unmodified
#     as the i2s node's driver -- was wrong: starting ALSA playback
#     (`speaker-test -D plughw:0,0`) freezes the whole SoC on a real board,
#     even with clk_ignore_unused/pd_ignore_unused. The vendor kernel does
#     NOT use the generic driver either; it has its own fork (compatible
#     "canaan,snps,designware-i2s") that differs in K230-critical register
#     programming, not just API currency -- see
#     docs/research/mainline-audio-port.md and
#     nix/patches/mainline/dwc_canaan/canaan-dwc-i2s.c's own header comment
#     for the full finding and API-delta list. The `i2s` DT node's
#     compatible string (nix/dts/k230-tdisplay-mainline.dts) now matches
#     this driver instead. `aplay -l` listing the card, and a non-frozen
#     `speaker-test` run, remain this task's own open host/board proofs --
#     not yet captured (no board access from this worktree).
#
# What is NOT ported (unchanged from the "absent" list above): display,
# crypto, ADC, PWM. See docs/research/mainline-kernel-inventory.md.
{ lib, buildLinux, fetchFromGitHub, applyPatches, ... }@args:

let
  kernelSrc = import ./kernel-mainline-src.nix { inherit fetchFromGitHub; };
in
buildLinux (args // {
  # Not a real upstream release number -- an -rc, named honestly as one.
  # Re-pin and rename once a stable v7.3.x exists.
  version = "7.3.0-rc5";
  modDirVersion = "7.3.0-rc5";

  src = applyPatches {
    name = "linux-mainline-k230-src";
    src = kernelSrc;
    # Clocks physical bisection showed must never be gated as unused; every
    # mainline variant needs them, not only the DRM kernel.
    patches = [
      ./patches/mainline/k230-clk-spi2axi-critical.patch
      ./patches/mainline/k230-clk-vpu-ddrcp2-dphy.patch
      # Restart handler in the reset controller; without it `reboot` stops
      # at "Restarting system".
      ./patches/mainline/k230-restart.patch
    ];

    postPatch = ''
      # Seed the vendor kernel's netfilter set (nix/kernel-firewall.config)
      # before oldconfig: NFT_COMPAT/NFT_CT prerequisites come later in
      # Kconfig, and answering them through structuredExtraConfig loops on
      # NFT_COMPAT=y while NETFILTER_XTABLES is still m.
      cat ${./kernel-firewall.config} >> arch/riscv/configs/defconfig
      # --- GPIO: drivers/gpio/gpio-k230.c ------------------------------
      cp ${./patches/mainline/gpio-k230.c} drivers/gpio/gpio-k230.c
      grep -q '^config GPIO_EIC_SPRD$' drivers/gpio/Kconfig
      sed -i '/^config GPIO_EIC_SPRD$/i\
config GPIO_K230\
\ttristate "GPIO driver for k230"\
\tdefault ARCH_CANAAN\
\tselect GPIO_GENERIC\
\tselect GPIOLIB_IRQCHIP\
\thelp\
\t  Say Y or M here to build support for the k230 GPIO block.\
\t  This driver provides basic support (configure as input or\
\t  output, read and write pin state) for GPIO.\
' drivers/gpio/Kconfig
      grep -q '^config GPIO_K230$' drivers/gpio/Kconfig
      echo 'obj-$(CONFIG_GPIO_K230)			+= gpio-k230.o' >> drivers/gpio/Makefile
      grep -q 'CONFIG_GPIO_K230.*gpio-k230.o' drivers/gpio/Makefile

      # --- SD/MMC: drivers/mmc/host/sdhci-of-kendryte.c ----------------
      cp ${./patches/mainline/sdhci-of-kendryte.c} drivers/mmc/host/sdhci-of-kendryte.c
      # Every mainline variant: SD hosts own all five gates (the SD1 restart
      # fix), so unused-clock cleanup cannot gate a live SD/SDIO controller.
      patch -p1 < ${./patches/mainline/k230-sdhci-clocks.patch}
      grep -q '^config MMC_SDHCI_OF_SPARX5$' drivers/mmc/host/Kconfig
      sed -i '/^config MMC_SDHCI_OF_SPARX5$/i\
config MMC_SDHCI_OF_DWCMSHC_KENDRYTE\
\ttristate "SDHCI OF support for the Kendryte K230 Synopsys DWC MSHC"\
\tdepends on MMC_SDHCI_PLTFM\
\tdepends on OF\
\tdepends on COMMON_CLK\
\thelp\
\t  This selects Kendryte K230 Synopsys DesignWare Cores Mobile\
\t  Storage Host Controller support.\
\t  If you have a controller with this interface, say Y or M here.\
\t  If unsure, say N.\
' drivers/mmc/host/Kconfig
      grep -q '^config MMC_SDHCI_OF_DWCMSHC_KENDRYTE$' drivers/mmc/host/Kconfig
      echo 'obj-$(CONFIG_MMC_SDHCI_OF_DWCMSHC_KENDRYTE) += sdhci-of-kendryte.o' >> drivers/mmc/host/Makefile
      grep -q 'CONFIG_MMC_SDHCI_OF_DWCMSHC_KENDRYTE.*sdhci-of-kendryte.o' drivers/mmc/host/Makefile

      # --- USB: drivers/usb/dwc2/{params.c,core.h,core.c} --------------
      #
      # Ported from the pinned vendor tree's own hunk against these same
      # files (same function names and bodies); see the file header above
      # for why this mechanism, not the separately-accepted
      # phy-k230-usb.c, is what nix/dts/k230-tdisplay-mainline.dts wires up.
      grep -q '^static void dwc2_set_rk_params(struct dwc2_hsotg \*hsotg)$' drivers/usb/dwc2/params.c
      sed -i 's|^static void dwc2_set_rk_params(struct dwc2_hsotg \*hsotg)|static void dwc2_set_k230_params(struct dwc2_hsotg *hsotg)\n{\n\tstruct dwc2_core_params *p = \&hsotg->params;\n\tu64 addr;\n\tstruct resource r;\n\n\tif (device_property_read_u64(hsotg->dev, "ctl-reg", \&addr) < 0)\n\t\treturn;\n\n\tr.start = addr;\n\tr.end = addr + 4;\n\tr.name = "usb-ctl-reg";\n\tr.flags = IORESOURCE_MEM;\n\tp->usb_ctl = devm_ioremap_resource(hsotg->dev, \&r);\n}\n\nstatic void dwc2_set_rk_params(struct dwc2_hsotg *hsotg)|' \
        drivers/usb/dwc2/params.c
      grep -q 'dwc2_set_k230_params' drivers/usb/dwc2/params.c

      # Two-line address match: the "intel,socfpga-agilex-hsotg" entry
      # wraps its .data= onto the following line in this file, so the
      # insertion anchors on that pair rather than a single line.
      grep -q '"intel,socfpga-agilex-hsotg",' drivers/usb/dwc2/params.c
      sed -i '/"intel,socfpga-agilex-hsotg",/{
        n
        s|\(.*dwc2_set_socfpga_agilex_params },\)|\1\n\t{ .compatible = "canaan,k230-otg", .data = dwc2_set_k230_params },|
      }' drivers/usb/dwc2/params.c
      grep -q '"canaan,k230-otg"' drivers/usb/dwc2/params.c

      grep -qF 'bool change_speed_quirk;' drivers/usb/dwc2/core.h
      sed -i 's|\tbool change_speed_quirk;|\tbool change_speed_quirk;\n\n\tvoid __iomem *usb_ctl;|' \
        drivers/usb/dwc2/core.h
      grep -q 'void __iomem \*usb_ctl;' drivers/usb/dwc2/core.h

      # Range-address append: from the function signature down to its
      # "int retval = 0;" declaration line, append the usb_ctl block right
      # after that line -- matching the vendor hunk's own placement
      # (before the FS/LS PHY branch), confirmed identical in mainline's
      # current copy of this function.
      grep -q '^int dwc2_phy_init(struct dwc2_hsotg \*hsotg, bool select_phy)$' drivers/usb/dwc2/core.c
      sed -i '/^int dwc2_phy_init(struct dwc2_hsotg \*hsotg, bool select_phy)$/,/^\tint retval = 0;$/{
        /^\tint retval = 0;$/a\
\
\tif (hsotg->params.usb_ctl) {\
\t\tu32 otgctl2 = readl(hsotg->params.usb_ctl);\
\
\t\totgctl2 |= BIT(4);\
\t\tif (dwc2_is_host_mode(hsotg))\
\t\t\totgctl2 |= (BIT(8) | BIT(9));\
\t\telse\
\t\t\totgctl2 \&= ~(BIT(8) | BIT(9));\
\t\twritel(otgctl2, hsotg->params.usb_ctl);\
\t}
      }' drivers/usb/dwc2/core.c
      grep -q 'hsotg->params.usb_ctl' drivers/usb/dwc2/core.c

      # --- RTC: drivers/rtc/rtc-k230.c ---------------------------------
      cp ${./patches/mainline/rtc-k230.c} drivers/rtc/rtc-k230.c
      grep -q '^config RTC_DRV_SUN6I$' drivers/rtc/Kconfig
      sed -i '/^config RTC_DRV_SUN6I$/i\
config RTC_DRV_K230\
\ttristate "Canaan K230 RTC driver"\
\tdefault n\
\tdepends on ARCH_CANAAN\
\thelp\
\t  If you say yes here you will get support for the built-in RTC\
\t  on Canaan K230 SoC.\
\
\t  This driver can also be built as a module, if so, the module\
\t  will be called "rtc-k230".\
' drivers/rtc/Kconfig
      grep -q '^config RTC_DRV_K230$' drivers/rtc/Kconfig
      echo 'obj-$(CONFIG_RTC_DRV_K230)	+= rtc-k230.o' >> drivers/rtc/Makefile
      grep -q 'CONFIG_RTC_DRV_K230.*rtc-k230.o' drivers/rtc/Makefile

      # --- Power key: drivers/input/misc/k230-pmu-pwrkey.c -------------
      #
      # Forward-ported from this project's own VENDOR-kernel driver
      # (nix/patches/k230-pmu-pwrkey.c); see
      # nix/patches/mainline/k230-pmu-pwrkey.c's header for the two API
      # changes (.remove signature, "pclk" clock claim).
      cp ${./patches/mainline/k230-pmu-pwrkey.c} drivers/input/misc/k230-pmu-pwrkey.c
      grep -q '^config INPUT_STPMIC1_ONKEY$' drivers/input/misc/Kconfig
      sed -i '/^config INPUT_STPMIC1_ONKEY$/i\
config INPUT_K230_PMU_PWRKEY\
\ttristate "Kendryte K230 PMU power key"\
\tdepends on OF\
\tdepends on ARCH_CANAAN || COMPILE_TEST\
\thelp\
\t  Report PMU INT0 power key edges through the Linux input subsystem.\
' drivers/input/misc/Kconfig
      grep -q '^config INPUT_K230_PMU_PWRKEY$' drivers/input/misc/Kconfig
      echo 'obj-$(CONFIG_INPUT_K230_PMU_PWRKEY) += k230-pmu-pwrkey.o' >> drivers/input/misc/Makefile
      grep -q 'CONFIG_INPUT_K230_PMU_PWRKEY.*k230-pmu-pwrkey.o' drivers/input/misc/Makefile

      # --- Thermal: drivers/thermal/canaan_thermal.c --------------------
      #
      # Forward-ported from the pinned VENDOR tree's own
      # drivers/thermal/canaan_thermal.c; see
      # nix/patches/mainline/canaan_thermal.c's header for the four API/
      # robustness changes (bounded read loop, devm_platform_ioremap_
      # resource, void remove, "ts" clock claim).
      cp ${./patches/mainline/canaan_thermal.c} drivers/thermal/canaan_thermal.c
      grep -q '^config LOONGSON2_THERMAL$' drivers/thermal/Kconfig
      sed -i '/^config LOONGSON2_THERMAL$/i\
config CANAAN_K230_THERMAL\
\ttristate "Canaan K230 thermal driver"\
\tdepends on OF\
\tdepends on ARCH_CANAAN || COMPILE_TEST\
\thelp\
\t  Support for the temperature sensor on the Canaan K230 SoC.\
' drivers/thermal/Kconfig
      grep -q '^config CANAAN_K230_THERMAL$' drivers/thermal/Kconfig
      echo 'obj-$(CONFIG_CANAAN_K230_THERMAL)	+= canaan_thermal.o' >> drivers/thermal/Makefile
      grep -q 'CONFIG_CANAAN_K230_THERMAL.*canaan_thermal.o' drivers/thermal/Makefile

      # --- PDMA: drivers/dma/k230-peridma.c ----------------------------
      #
      # openspec/changes/the-mainline-shell-reaches-parity task 5.1
      # follow-up: forward-ported from the pinned VENDOR tree's own
      # drivers/dma/k230_peridma.c (which that tree already Kconfig-gates
      # as `K230_PERIDMA`, `depends on ARCH_RV64I` -- too broad for this
      # project's narrower-than-vendor Kconfig choices elsewhere, so this
      # entry depends on ARCH_CANAAN instead, same pattern as
      # CANAAN_K230_THERMAL/INPUT_K230_PMU_PWRKEY above). See
      # nix/patches/mainline/k230-peridma.c's own header comment for the
      # API deltas (void remove, devm_clk_get_enabled for
      # K230_SHRM_PDMA_AXI_GATE). Unblocks the audio dmaengine_pcm path
      # above (the i2s node's `dmas = <&pdma ...>` phandle in
      # nix/dts/k230-tdisplay-mainline.dts now resolves to a registered
      # DMA controller) -- see docs/research/mainline-audio-port.md.
      cp ${./patches/mainline/k230-peridma.c} drivers/dma/k230-peridma.c
      grep -q '^config DW_AXI_DMAC$' drivers/dma/Kconfig
      sed -i '/^config DW_AXI_DMAC$/i\
config K230_PERIDMA\
\ttristate "Canaan K230 Peripheral DMA support"\
\tdepends on OF\
\tdepends on ARCH_CANAAN || COMPILE_TEST\
\tselect DMA_ENGINE\
\tselect DMA_VIRTUAL_CHANNELS\
\thelp\
\t  Enable support for the Peripheral DMA controller on the Canaan K230\
\t  SoC, used by UART/I2C/the on-die I2S audio block/JAMLINK/ADC/PDM\
\t  peripherals to move data to and from system memory without CPU\
\t  involvement.\
' drivers/dma/Kconfig
      grep -q '^config K230_PERIDMA$' drivers/dma/Kconfig
      echo 'obj-$(CONFIG_K230_PERIDMA) += k230-peridma.o' >> drivers/dma/Makefile
      grep -q 'CONFIG_K230_PERIDMA.*k230-peridma.o' drivers/dma/Makefile

      # --- Audio: sound/soc/canaan (new dir) + sound/soc/codecs/inno_k230 -
      #
      # openspec/changes/the-mainline-shell-reaches-parity, task 5.1.
      # Forward-ported from the pinned vendor tree's sound/soc/canaan/ and
      # sound/soc/codecs/inno_k230{,_reg}.{c,h}, folding in this project's
      # own nix/patches/canaan-audio-external-i2s-switch.patch directly
      # (see nix/patches/mainline/canaan_k230_inno.c's own header) and
      # adding the clock claims docs/research/mainline-audio-port.md
      # records as missing from the vendor source. Reuses mainline's own,
      # already-present sound/soc/dwc/dwc-i2s.c (Synopsys DesignWare I2S)
      # as the CPU/platform DAI unmodified -- see that research doc for why
      # no canaan-specific I2S controller driver or compatible string is
      # needed here, and for the one thing this task could NOT forward-port
      # (DMA).
      mkdir -p sound/soc/canaan
      cp ${./patches/mainline/canaan_k230_audio.c} sound/soc/canaan/canaan_k230_audio.c
      cp ${./patches/mainline/canaan_k230_audio.h} sound/soc/canaan/canaan_k230_audio.h
      cp ${./patches/mainline/canaan_k230_inno.c} sound/soc/canaan/canaan_k230_inno.c
      cat > sound/soc/canaan/Kconfig <<'EOF'
config SND_SOC_CANAAN_K230_AUDIO
	tristate "CANAAN K230 AUDIO interface support"
	help
	  Say Y or M here if you want to enable k230 audio for canaan soc. This
	  option provides the necessary interface support for audio functionalities
	  on CANAAN K230 SoC, enabling audio input and output capabilities. If
	  unsure, select M.

config SND_SOC_CANAAN_K230_INNO
	tristate "ASoC support for CANAAN boards using a inno codec"
	select SND_SOC_K230_INNO
	help
	  Say Y or M here if you want to add support for SoC audio on CANAAN K230
	  boards using the INNO codec. This option enables the ASoC audio driver
	  for CANAAN K230 boards, allowing audio playback and recording through
	  the INNO codec. If unsure, select M.
EOF
      cat > sound/soc/canaan/Makefile <<'EOF'
snd-soc-canaan-k230-audio-objs := canaan_k230_audio.o
obj-$(CONFIG_SND_SOC_CANAAN_K230_AUDIO) += snd-soc-canaan-k230-audio.o

snd-soc-canaan-k230-inno-objs := canaan_k230_inno.o
obj-$(CONFIG_SND_SOC_CANAAN_K230_INNO) += snd-soc-canaan-k230-inno.o
EOF
      grep -q '^source "sound/soc/dwc/Kconfig"$' sound/soc/Kconfig
      sed -i '/^source "sound\/soc\/dwc\/Kconfig"$/a source "sound/soc/canaan/Kconfig"' sound/soc/Kconfig
      grep -q '^source "sound/soc/canaan/Kconfig"$' sound/soc/Kconfig
      echo 'obj-$(CONFIG_SND_SOC)	+= canaan/' >> sound/soc/Makefile
      grep -q 'CONFIG_SND_SOC.*+= canaan/' sound/soc/Makefile

      # Inno codec: sound/soc/codecs/inno_k230{,_reg}.{c,h}. inno_rk3036.c
      # (a DIFFERENT, unrelated Rockchip part sharing only an "inno" name
      # prefix) is already present in this tree -- not touched.
      cp ${./patches/mainline/inno_k230.c} sound/soc/codecs/inno_k230.c
      cp ${./patches/mainline/inno_k230_reg.c} sound/soc/codecs/inno_k230_reg.c
      cp ${./patches/mainline/inno_k230_reg.h} sound/soc/codecs/inno_k230_reg.h
      grep -q '^endmenu$' sound/soc/codecs/Kconfig
      sed -i '$ i\
config SND_SOC_K230_INNO\
\ttristate "K230 INNO Codec"\
\tdepends on ARCH_CANAAN || COMPILE_TEST\
\thelp\
\t  Enable support for the K230 INNO audio codec. This codec provides\
\t  audio playback and recording support for Canaan K230 SoC boards.\
\t  If built as a module, the module will be called snd-soc-k230-inno.\
' sound/soc/codecs/Kconfig
      grep -q '^config SND_SOC_K230_INNO$' sound/soc/codecs/Kconfig
      echo 'snd-soc-k230-inno-objs := inno_k230_reg.o inno_k230.o' >> sound/soc/codecs/Makefile
      echo 'obj-$(CONFIG_SND_SOC_K230_INNO) += snd-soc-k230-inno.o' >> sound/soc/codecs/Makefile
      grep -q 'CONFIG_SND_SOC_K230_INNO.*snd-soc-k230-inno.o' sound/soc/codecs/Makefile

      # --- I2S controller: sound/soc/dwc_canaan (new dir) --------------
      #
      # openspec/changes/the-mainline-shell-reaches-parity, task 5.x.
      # docs/research/mainline-audio-port.md originally reused mainline's
      # OWN sound/soc/dwc/dwc-i2s.c (compatible "snps,designware-i2s")
      # unmodified for this board's i2s node, reasoning the vendor file
      # was API-currency-only drift from that same driver. Board-proven
      # wrong: starting ALSA playback against that generic driver
      # (`speaker-test -D plughw:0,0`) freezes the whole SoC, even with
      # clk_ignore_unused/pd_ignore_unused -- see that doc's updated
      # findings. The vendor's own fork,
      # sound/soc/dwc_canaan/{canaan-dwc-i2s.c,canaan-dwc-pcm.c,
      # canaan-local.h} (compatible "canaan,snps,designware-i2s"),
      # forward-ported here as nix/patches/mainline/dwc_canaan/*, differs
      # from the generic driver in real register-programming ways, not
      # just API currency: always data_width 32/ccr 0x10 regardless of
      # PCM format, CCR |= (1<<5)|(3<<8) ("standard i2s format and
      # dma_tx_en/dma_rx_en"), per-format DMA addr_width, DMA maxburst 4
      # (mainline's generic driver uses 16), and -- the most likely cause
      # of the observed freeze -- i2s_start() enables DMA XOR IRQs
      # strictly (PIO/JH7110 get IRQs, everyone else gets DMA only), where
      # mainline's generic dwc-i2s.c now enables IRQs unconditionally in
      # addition to DMA. This board's i2s DT node has no `interrupts`
      # property, so mainline's generic driver unmasks an IMR interrupt
      # source with no handler ever installed. See
      # nix/patches/mainline/dwc_canaan/canaan-dwc-i2s.c's own header
      # comment for the full API-delta list (void .remove,
      # snd_soc_substream_to_rtd, RUNTIME_PM_OPS/pm_ptr,
      # devm_clk_get_enabled, -EPROBE_DEFER irq handling, .pcm_new rename)
      # and docs/research/mainline-audio-port.md for the rest of this
      # finding. Namespaced under its own CANAAN_SND_DESIGNWARE_I2S/_PCM
      # Kconfig symbols -- distinct from mainline's own
      # SND_DESIGNWARE_I2S/_PCM -- so both drivers can coexist in-tree;
      # only the `i2s` DT node's compatible string (changed below in
      # nix/dts/k230-tdisplay-mainline.dts) decides which one binds.
      # SND_DESIGNWARE_I2S is deliberately left enabled, not disabled:
      # with no device tree node left using "snps,designware-i2s", it
      # never binds anything on this board, so there is no conflict to
      # resolve by turning it off.
      mkdir -p sound/soc/dwc_canaan
      cp ${./patches/mainline/dwc_canaan/canaan-dwc-i2s.c} sound/soc/dwc_canaan/canaan-dwc-i2s.c
      cp ${./patches/mainline/dwc_canaan/canaan-dwc-pcm.c} sound/soc/dwc_canaan/canaan-dwc-pcm.c
      cp ${./patches/mainline/dwc_canaan/canaan-local.h} sound/soc/dwc_canaan/canaan-local.h
      cp ${./patches/mainline/dwc_canaan/Kconfig} sound/soc/dwc_canaan/Kconfig
      cp ${./patches/mainline/dwc_canaan/Makefile} sound/soc/dwc_canaan/Makefile
      grep -q '^source "sound/soc/canaan/Kconfig"$' sound/soc/Kconfig
      sed -i '/^source "sound\/soc\/canaan\/Kconfig"$/a source "sound/soc/dwc_canaan/Kconfig"' sound/soc/Kconfig
      grep -q '^source "sound/soc/dwc_canaan/Kconfig"$' sound/soc/Kconfig
      echo 'obj-$(CONFIG_SND_SOC)	+= dwc_canaan/' >> sound/soc/Makefile
      grep -q 'CONFIG_SND_SOC.*+= dwc_canaan/' sound/soc/Makefile
    '';
  };

  # Mainline's own generic RISC-V defconfig, not a K230-specific one --
  # nothing named "k230_defconfig" exists upstream. This defconfig already
  # builds a broadly distro-usable kernel (many platforms, modules mostly
  # on), unlike the vendor's narrow k230_defconfig.
  defconfig = "defconfig";

  # Same reasoning as nix/kernel.nix: build what we ask for, not everything
  # nixpkgs' autoModules can find. Faster, and this build's whole point is a
  # narrow, understood configuration, not maximum driver coverage of SoCs
  # this board is not.
  autoModules = false;

  structuredExtraConfig = with lib.kernel; {
    # The three merged K230-specific SoC-platform drivers. RESET_K230 is
    # `default ARCH_CANAAN` already (checked directly against
    # drivers/reset/Kconfig), so this line is redundant but explicit;
    # PINCTRL_K230 and COMMON_CLK_K230 default to `bool` off and need
    # asking for.
    ARCH_CANAAN = yes;
    PINCTRL_K230 = yes;
    RESET_K230 = yes;
    COMMON_CLK_K230 = yes;

    # This change's own forward-ports.
    GPIO_K230 = yes;
    RTC_DRV_K230 = yes;
    MMC = yes;
    MMC_BLOCK = yes;
    MMC_SDHCI = yes;
    MMC_SDHCI_PLTFM = yes;
    MMC_SDHCI_OF_DWCMSHC_KENDRYTE = yes;
    USB_SUPPORT = yes;
    USB = yes;
    USB_DWC2 = yes;

    # Power key (task 4.1): INPUT_MISC is "# CONFIG_INPUT_MISC is not set"
    # in the base defconfig (checked directly against the built .config),
    # so it needs asking for to even reach the input/misc submenu.
    INPUT_MISC = yes;
    INPUT_K230_PMU_PWRKEY = yes;

    # Thermal (task 7.1): THERMAL/THERMAL_OF are already on in the base
    # defconfig; named explicitly anyway, same as RESET_K230 above.
    THERMAL = yes;
    THERMAL_OF = yes;
    CANAAN_K230_THERMAL = yes;

    # PDMA (task 5.1 follow-up): DMADEVICES/DMA_ENGINE/DMA_VIRTUAL_CHANNELS/
    # DMA_OF are already `y` in the base riscv defconfig (checked directly
    # against the built .config -- not asked for here, same
    # already-satisfied-dependency reasoning as THERMAL/THERMAL_OF above);
    # only this driver's own symbol needs asking for.
    K230_PERIDMA = yes;

    # --- Audio (task 5.1) ------------------------------------------------
    # SND_SOC_GENERIC_DMAENGINE_PCM is pulled in by both SND_DESIGNWARE_I2S's
    # and CANAAN_SND_DESIGNWARE_I2S's own `select`; not asked for directly.
    # Neither _PCM PIO extension (SND_DESIGNWARE_PCM, CANAAN_SND_DESIGNWARE_
    # PCM) is enabled: this board's i2s DT node carries no `interrupts`
    # property (matching the only vendor DT reference for this IP -- see
    # nix/dts/k230-tdisplay-mainline.dts), so dw_i2s_probe() always takes the
    # dmaengine_pcm branch regardless of either symbol -- which now has a
    # real DMA provider to resolve against (K230_PERIDMA above). See
    # docs/research/mainline-audio-port.md for the full history, including
    # the board-proven freeze that moved this board's i2s node (below) from
    # mainline's own SND_DESIGNWARE_I2S driver to the vendor's
    # CANAAN_SND_DESIGNWARE_I2S fork. SND_DESIGNWARE_I2S itself is left
    # enabled, not disabled: with no DT node using "snps,designware-i2s"
    # left on this board, it never binds anything, so there is nothing for
    # it to conflict with.
    SOUND = yes;
    SND = yes;
    SND_SOC = yes;
    SND_DESIGNWARE_I2S = yes;
    CANAAN_SND_DESIGNWARE_I2S = yes;
    SND_SOC_K230_INNO = yes;
    SND_SOC_CANAAN_K230_AUDIO = yes;
    SND_SOC_CANAAN_K230_INNO = yes;

    # An initrd remains part of the boot path even with SD/MMC now
    # available: NixOS's own stage-1 initrd is what actually mounts and
    # switches root onto the SD card's ext4 partition (see
    # nixosConfigurations.k230-mainline-console, flake.nix), not a bare
    # kernel root= alone.
    BLK_DEV_INITRD = yes;
    RD_GZIP = yes;
    RD_ZSTD = yes;

    # --- Wi-Fi (task the-mainline-shell-reaches-parity 6.1) --------------
    # The RTL8189FTV out-of-tree module (nix/k230-wifi-driver.nix) needs
    # struct net_device's ieee80211_ptr member, which mainline's own
    # include/linux/netdevice.h guards with `#if IS_ENABLED(CONFIG_CFG80211)`
    # -- confirmed directly against that header at this pin -- and calls
    # into net/cfg80211.h's cfg80211_ops/cfg80211_* API, so the module
    # cannot even type-check against this dev tree's base defconfig, which
    # has `# CONFIG_CFG80211 is not set`. CFG80211's own Kconfig (pinned
    # research source's net/wireless/Kconfig) only needs FW_LOADER, CRC32
    # and CRYPTO_SHA256 -- all three already `y` in the built .config
    # (checked directly), so asking for this one symbol does not loop
    # through any unsatisfied dependency. `module`, not `yes`: this is the
    # wireless configuration API, not a board-specific driver, and every
    # upstream board that uses it ships it as a module. MAC80211 is
    # deliberately NOT requested: the pinned RTL8189FTV source
    # (jwrdegoede/rtl8189ES_linux) implements its own softmac stack against
    # cfg80211 directly (grep of core/*.c and os_dep/linux/ioctl_cfg80211.c
    # confirms no net/mac80211.h include or mac80211 symbol use anywhere).
    # This alone does NOT make the module build succeed -- see
    # docs/research/mainline-wifi-port.md for the remaining cfg80211_ops
    # struct (net_device* -> wireless_dev*) signature rework the driver
    # still needs, which is deeper than a Kconfig gap and UNVERIFIED against
    # this symbol actually being on (no kernel has been rebuilt with it).
    CFG80211 = module;
  };

  extraMeta = {
    description = "Plain mainline console kernel with Canaan K230 SoC support and this project's forward-ported GPIO/SD-MMC/USB/RTC/power-key/thermal/PDMA/audio drivers (i2s node now uses the forward-ported canaan,snps,designware-i2s driver, not mainline's generic one, after a board-proven freeze starting ALSA playback against the generic driver -- see docs/research/mainline-audio-port.md; board `aplay -l`/non-frozen-playback proof still pending; no DRM/display, touch, ADC, PWM or crypto driver)";
    platforms = [ "riscv64-linux" ];
  };
} // (args.argsOverride or { }))
