# The kernel for the T-Display-K230.
#
# Mainline cannot boot this SoC. Linux 6.18 carries pinctrl-k230.c and
# reset-k230.c but ships no K230 device tree -- arch/riscv/boot/dts/canaan/
# is K210-only -- and Kconfig.socs has no SOC_CANAAN_K230, only
# SOC_CANAAN_K210, itself `depends on !MMU`. A stock nixpkgs kernel
# therefore has nothing to boot with. See
# docs/evidence/boot-path-differences.md.
#
# So we take the tree Canaan's own Linux SDK uses, pinned to the revision
# k230_canmv_v3_defconfig names, and build it ourselves from source rather
# than vendoring a kernel binary.
{ lib, buildLinux, fetchFromGitHub, ... }@args:

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

  src = fetchFromGitHub {
    owner = "ruyisdk";
    repo = "linux-xuantie-kernel";
    inherit rev;
    hash = "sha256-ITlci/1nGcE46kglR7i1AG3MZH6RBfpcGLWPakyXMTk=";
  };

  defconfig = "k230_defconfig";

  # arch/riscv/boot/dts/canaan/Makefile lists k230-canmv, k230d-canmv and
  # k230-evb, but NOT the v3 board -- even though k230-canmv-v3.dts and
  # k230-canmv-v3-lcd.dts are both in the tree. Canaan's buildroot sidesteps
  # this by naming the DTBs explicitly
  # (BR2_LINUX_KERNEL_INTREE_DTS_NAME="canaan/k230-canmv-v3-lcd canaan/k230-canmv-v3"),
  # so `make dtbs` alone never produces them. Add them to the Makefile
  # instead, so a plain kernel build emits what this board needs.
  postPatch = ''
    echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-canmv-v3.dtb' >> arch/riscv/boot/dts/canaan/Makefile
    echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-canmv-v3-lcd.dtb' >> arch/riscv/boot/dts/canaan/Makefile
  '';

  # Build what the vendor builds, and little else.
  #
  # nixpkgs defaults autoModules to true, which turns on every module it
  # can on top of the defconfig. Against a vendor tree that is actively
  # harmful: it enables drivers the vendor never compiles, so their bugs
  # have never been hit. The first build died on drivers/rpmsg/th1520_rpmsg.c
  # -- "redefinition of init_module" -- a TH1520 driver, for a different
  # SoC, that CONFIG_RPMSG_TH1520 does not enable in k230_defconfig and
  # that nobody upstream builds as a module. Greybus was compiling too.
  #
  # Turning this off keeps us near the configuration Canaan actually tests,
  # and makes the build dramatically shorter.
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
    DMIID = lib.mkForce (option no);
    TMPFS = yes;
    TMPFS_POSIX_ACL = yes;
    SECCOMP = yes;
    # An initrd that cannot unpack itself looks exactly like a dead board.
    RD_GZIP = yes;
    RD_ZSTD = yes;
    BLK_DEV_INITRD = yes;

    # Belt and braces: never build the TH1520 rpmsg driver. It is for
    # another SoC and does not compile in this tree.
    RPMSG_TH1520 = lib.mkForce no;
  };

  extraMeta = {
    description = "Xuantie kernel with Canaan K230 support, as used by k230_linux_sdk";
    platforms = [ "riscv64-linux" ];
  };
} // (args.argsOverride or { }))
