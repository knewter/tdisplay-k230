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
  };

  extraMeta = {
    description = "Xuantie kernel with Canaan K230 support, as used by k230_linux_sdk";
    platforms = [ "riscv64-linux" ];
  };
} // (args.argsOverride or { }))
