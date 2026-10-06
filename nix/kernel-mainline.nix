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
#             k230-pmu-pwrkey.c, drivers/crypto/canaan/. None of our
#             display/audio/RTC/power-key/thermal patches have anything to
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
#   - sound/soc/canaan/{canaan_k230_audio,canaan_k230_inno}.c and
#     sound/soc/codecs/inno_k230{,_reg}.c (task 5.1, openspec/changes/
#     the-mainline-shell-reaches-parity): the SAI mux, Inno codec and
#     "canaan,k230-audio-inno" machine driver, forward-ported with this
#     project's own external-I2S-switch control folded in and explicit
#     claims added for K230_LS_AUDIO_APB_GATE/K230_LS_CODEC_APB_GATE (see
#     each file's own header comment). Reuses mainline's OWN, already-
#     present sound/soc/dwc/dwc-i2s.c (Synopsys DesignWare I2S) unmodified
#     as the CPU/platform DAI -- no canaan-specific I2S controller driver
#     needed. BLOCKED short of real PCM data movement: this board's only
#     known i2s DT node (k230.dtsi) carries no `interrupts` property, so
#     dw_i2s_probe() takes the dmaengine_pcm path, which needs a DMA
#     provider for `compatible = "canaan,k230-pdma"` that does not exist in
#     mainline (drivers/dma/k230_peridma.c is a from-scratch ~1400-line
#     register interface, not a dw-axi-dmac/dw_dmac variant). See
#     docs/research/mainline-audio-port.md for the full analysis and what
#     would unblock it.
#
# What is NOT ported (unchanged from the "absent" list above): display,
# thermal, PMU/power key, crypto, ADC, PWM. RTC is ported (see the RTC
# section above). Audio is forward-ported but cannot move PCM data yet (see
# above). See docs/research/mainline-kernel-inventory.md.
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

    postPatch = ''
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

    # --- Audio (task 5.1) ------------------------------------------------
    # SND_SOC_GENERIC_DMAENGINE_PCM is pulled in by SND_DESIGNWARE_I2S's own
    # `select`; not asked for directly. SND_DESIGNWARE_PCM (the PIO PCM
    # extension) is NOT enabled: this board's i2s DT node carries no
    # `interrupts` property (matching the only vendor DT reference for this
    # IP -- see nix/dts/k230-tdisplay-mainline.dts), so dw_i2s_probe()
    # always takes the dmaengine_pcm branch regardless of this symbol; see
    # docs/research/mainline-audio-port.md for why forcing the PIO branch
    # would mean fabricating an unverified PLIC IRQ number.
    SOUND = yes;
    SND = yes;
    SND_SOC = yes;
    SND_DESIGNWARE_I2S = yes;
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
  };

  extraMeta = {
    description = "Plain mainline console kernel with Canaan K230 SoC support and this project's forward-ported GPIO/SD-MMC/USB/RTC/audio drivers (audio card registers but cannot move PCM data yet -- see docs/research/mainline-audio-port.md; no DRM/display, touch, power-key, thermal, ADC, PWM or crypto driver)";
    platforms = [ "riscv64-linux" ];
  };
} // (args.argsOverride or { }))
