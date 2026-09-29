# A parallel, opt-in mainline kernel build for the T-Display-K230.
#
# openspec/changes/the-board-runs-a-mainline-kernel. This is NOT the kernel
# any nixosConfigurations output boots -- see nix/kernel.nix for that. This
# derivation exists so the board has a cross-built mainline Image the
# coordinator can try loading from U-Boot once a board slot is free, and so
# this project's patches that fix generic-Linux (not Canaan-driver) bugs
# have a forward-ported home.
#
# WHAT MAINLINE (v7.3-rc5, nix/kernel-mainline-src.nix) ACTUALLY HAS for this
# SoC, checked directly against that pinned tree and against
# `gh api repos/torvalds/linux/contents/<path>` on 2026-09-29 (200 = present,
# 404 = absent):
#
#   present : ARCH_CANAAN, PINCTRL_K230 (pinctrl-k230-iomux.c), RESET_K230
#             (reset-k230.c), COMMON_CLK_K230, arch/riscv/boot/dts/canaan/
#             k230.dtsi + k230-canmv.dts + k230-evb.dts (UART0 console only;
#             no mmc/usb/i2c/spi/pwm/adc/rtc/watchdog/gpio/crypto/thermal
#             node in k230.dtsi itself yet). goodix_berlin touchscreen is
#             present (mainline code we ourselves backported onto the
#             vendor tree), but unusable here without an I2C DT node, which
#             does not exist upstream for this SoC yet either.
#   absent  : drivers/gpu/drm/canaan/, drivers/gpu/drm/panel/
#             panel-canaan-universal.c, sound/soc/canaan/, drivers/rtc/
#             rtc-k230.c, drivers/thermal/canaan_thermal.c, drivers/iio/adc/
#             k230-adc.c, drivers/pwm/pwm-k230.c, drivers/gpio/gpio-k230.c,
#             drivers/input/misc/k230-pmu-pwrkey.c, drivers/crypto/canaan/.
#             None of our display/audio/RTC/power-key/thermal patches have
#             anything to patch here.
#   in review, not merged into this pin : SDHCI (sdhci-of-dwcmshc.c reuse,
#             v5 series, March 2026) -- so no SD/MMC rootfs path yet.
#             The USB-PHY *driver* and its DT *binding* were separately
#             accepted (lkml.org/lkml/2026/2/27/1255), but the *DT node*
#             wiring it into k230.dtsi/k230-canmv.dts has not landed in this
#             pin -- so USB is also not usable from this device tree today.
#
# So this kernel's only provable hardware ceiling right now is: it can be
# built, and if it boots at all, its console is the only thing it can talk
# to (no block device, no USB, no display). See
# docs/research/mainline-kernel-inventory.md for the full inventory this
# derivation's scope was decided from.
{ lib, buildLinux, fetchFromGitHub, ... }@args:

let
  kernelSrc = import ./kernel-mainline-src.nix { inherit fetchFromGitHub; };
in
buildLinux (args // {
  # Not a real upstream release number -- an -rc, named honestly as one.
  # Re-pin and rename once a stable v7.3.x exists.
  version = "7.3.0-rc5";
  modDirVersion = "7.3.0-rc5";

  src = kernelSrc;

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
    # The three merged K230-specific drivers. RESET_K230 is `default
    # ARCH_CANAAN` already (checked directly against
    # drivers/reset/Kconfig), so this line is redundant but explicit;
    # PINCTRL_K230 and COMMON_CLK_K230 default to `bool` off and need
    # asking for.
    ARCH_CANAAN = yes;
    PINCTRL_K230 = yes;
    RESET_K230 = yes;
    COMMON_CLK_K230 = yes;

    # An initrd is the only rootfs path available at all until SD/MMC or
    # USB storage lands in this pin's device tree (see the file header).
    BLK_DEV_INITRD = yes;
    RD_GZIP = yes;
    RD_ZSTD = yes;

    # Console over the SoC's UART0 -- the only peripheral k230.dtsi wires
    # up today. 8250-family is already mainline/generic; nothing K230-
    # specific to enable beyond the standard 8250 serial config mainline's
    # own defconfig already carries.
  };

  extraMeta = {
    description = "Mainline Linux with Canaan K230 SoC support (pinctrl/reset/clk/basic DT only -- no display, touch, audio, storage or USB device-tree wiring yet)";
    platforms = [ "riscv64-linux" ];
  };
} // (args.argsOverride or { }))
