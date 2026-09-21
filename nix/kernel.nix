# The kernel for the T-Display-K230.
#
# Mainline cannot boot this SoC. Linux 6.18 carries pinctrl-k230.c and
# reset-k230.c but ships no K230 device tree -- arch/riscv/boot/dts/canaan/
# is K210-only -- and Kconfig.socs has no SOC_CANAAN_K230, only
# SOC_CANAAN_K210, itself `depends on !MMU`. See
# docs/evidence/why-xuantie-kernel.txt.
#
# So we take the tree Canaan's own Linux SDK pins, and build it from source
# rather than vendoring a kernel binary.
{ lib, buildLinux, fetchFromGitHub, applyPatches, ... }@args:

let
  # Pinned by kendryte/k230_linux_sdk @ dev, buildroot-overlay/configs/
  # k230_canmv_v3_defconfig:
  #   BR2_LINUX_KERNEL_CUSTOM_REPO_URL="https://github.com/ruyisdk/linux-xuantie-kernel.git"
  #   BR2_LINUX_KERNEL_CUSTOM_REPO_VERSION="7d4e1f444f461dbe3833bd99a4640e7b6c2cd529"
  #   BR2_LINUX_KERNEL_DEFCONFIG="k230"
  rev = "7d4e1f444f461dbe3833bd99a4640e7b6c2cd529";
in
buildLinux (args // {
  version = "6.6.36-xuantie";
  modDirVersion = "6.6.36";

  # arch/riscv/boot/dts/canaan/Makefile lists k230-canmv, k230d-canmv and
  # k230-evb but NOT the v3 board, even though k230-canmv-v3.dts and
  # k230-canmv-v3-lcd.dts are both in the tree. Canaan's buildroot sidesteps
  # that by naming DTBs explicitly in BR2_LINUX_KERNEL_INTREE_DTS_NAME, so
  # `make dtbs` alone never produces them.
  #
  # Patched into the SOURCE, not via postPatch: buildLinux does not forward
  # postPatch to the kernel derivation, so setting it there is a silent
  # no-op -- the build returns the same store path and the DTB is still
  # missing. Found by the derivation hash not changing.
  src = applyPatches {
    name = "linux-xuantie-k230-src";
    src = fetchFromGitHub {
      owner = "ruyisdk";
      repo = "linux-xuantie-kernel";
      inherit rev;
      hash = "sha256-ITlci/1nGcE46kglR7i1AG3MZH6RBfpcGLWPakyXMTk=";
    };
    postPatch = ''
      echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-canmv-v3.dtb' >> arch/riscv/boot/dts/canaan/Makefile
      echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-canmv-v3-lcd.dtb' >> arch/riscv/boot/dts/canaan/Makefile

      # This board's own device tree and panel.
      cp ${../nix/dts/display-rm69a10-568x1232.dtsi} \
         arch/riscv/boot/dts/canaan/display-rm69a10-568x1232.dtsi
      cp ${../nix/dts/k230-tdisplay.dts} \
         arch/riscv/boot/dts/canaan/k230-tdisplay.dts
      echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-tdisplay.dtb' >> arch/riscv/boot/dts/canaan/Makefile

      # goodix_berlin, backported from v6.12. The pinned 6.6 tree has only
      # the older GT9xx goodix.c. See docs/evidence/gt9895-touch.md -- note
      # this driver does NOT match the GT9895 upstream, so whether it can
      # drive this panel's controller is an open experiment.
      cp ${../nix/patches/goodix-berlin}/goodix_berlin*.{c,h} \
         drivers/input/touchscreen/
      # 6.12 moved asm/unaligned.h to linux/unaligned.h; 6.6 predates that.
      sed -i 's|#include <linux/unaligned.h>|#include <asm/unaligned.h>|' \
        drivers/input/touchscreen/goodix_berlin_core.c \
        drivers/input/touchscreen/goodix_berlin_i2c.c \
        drivers/input/touchscreen/goodix_berlin_spi.c
      cat >> drivers/input/touchscreen/Kconfig <<'EOK'

config TOUCHSCREEN_GOODIX_BERLIN_CORE
	tristate
	select REGMAP

config TOUCHSCREEN_GOODIX_BERLIN_I2C
	tristate "Goodix Berlin I2C touchscreen"
	depends on I2C
	select REGMAP_I2C
	select TOUCHSCREEN_GOODIX_BERLIN_CORE
	help
	  Backported from v6.12 for the T-Display-K230's GT9895.
EOK
      cat >> drivers/input/touchscreen/Makefile <<'EOM'
obj-$(CONFIG_TOUCHSCREEN_GOODIX_BERLIN_CORE) += goodix_berlin_core.o
obj-$(CONFIG_TOUCHSCREEN_GOODIX_BERLIN_I2C)  += goodix_berlin_i2c.o
EOM
    '';
  };

  defconfig = "k230_defconfig";

  # Build what the vendor builds, and little else.
  #
  # nixpkgs defaults autoModules to true, enabling every module it can on
  # top of the defconfig. Against a vendor tree that is actively harmful: it
  # turns on drivers the vendor never compiles, so their bugs have never
  # been hit. The first build died in drivers/rpmsg/th1520_rpmsg.c with
  # "redefinition of init_module" -- a driver for the TH1520, a different
  # SoC, that k230_defconfig does not enable and nobody builds as a module.
  # Greybus was compiling too.
  autoModules = false;

  # NixOS needs things a vendor defconfig does not bother with. systemd
  # refuses to boot without most of these, and the board would stop at an
  # initrd panic that says nothing about the real cause.
  structuredExtraConfig = with lib.kernel; {
    DEVTMPFS = yes;
    DEVTMPFS_MOUNT = yes;
    CGROUPS = yes;
    INOTIFY_USER = yes;
    SIGNALFD = yes;
    TIMERFD = yes;
    EPOLL = yes;
    NET = yes;
    SYSFS = yes;
    PROC_FS = yes;
    FHANDLE = yes;
    CRYPTO_USER_API_HASH = yes;
    CRYPTO_HMAC = yes;
    CRYPTO_SHA256 = yes;
    TMPFS = yes;
    TMPFS_POSIX_ACL = yes;
    SECCOMP = yes;
    # An initrd that cannot unpack itself looks exactly like a dead board.
    BLK_DEV_INITRD = yes;
    RD_GZIP = yes;
    RD_ZSTD = yes;
    # For another SoC, and does not compile in this tree.
    RPMSG_TH1520 = lib.mkForce no;

    # The backported Berlin touch driver. Built in, not a module, so a
    # failure to probe shows up in the boot log rather than in whether
    # something got modprobed.
    TOUCHSCREEN_GOODIX_BERLIN_CORE = yes;
    TOUCHSCREEN_GOODIX_BERLIN_I2C = yes;
  };

  extraMeta = {
    description = "Xuantie kernel with Canaan K230 support, as used by k230_linux_sdk";
    platforms = [ "riscv64-linux" ];
  };
} // (args.argsOverride or { }))
