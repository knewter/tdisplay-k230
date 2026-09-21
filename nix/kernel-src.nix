# The pinned Xuantie kernel SOURCE, unpatched.
#
# Split out of nix/kernel.nix so that two things can share one pin: the
# kernel itself, and nix/device-tree.nix, which needs this tree's
# arch/riscv/boot/dts/canaan/k230.dtsi and include/dt-bindings to compile
# our board DTB without compiling a kernel.
#
# Pinned by kendryte/k230_linux_sdk @ dev, buildroot-overlay/configs/
# k230_canmv_v3_defconfig:
#   BR2_LINUX_KERNEL_CUSTOM_REPO_URL="https://github.com/ruyisdk/linux-xuantie-kernel.git"
#   BR2_LINUX_KERNEL_CUSTOM_REPO_VERSION="7d4e1f444f461dbe3833bd99a4640e7b6c2cd529"
#   BR2_LINUX_KERNEL_DEFCONFIG="k230"
{ fetchFromGitHub }:

fetchFromGitHub {
  owner = "ruyisdk";
  repo = "linux-xuantie-kernel";
  rev = "7d4e1f444f461dbe3833bd99a4640e7b6c2cd529";
  hash = "sha256-ITlci/1nGcE46kglR7i1AG3MZH6RBfpcGLWPakyXMTk=";
}
