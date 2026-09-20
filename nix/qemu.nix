# The T-Display-K230 under QEMU's `k230` machine.
#
# Two constraints from that machine drive everything here:
#
#   1. It models no block device and no network -- only UARTs, SSI flash,
#      system DMA and a GZIP engine. So the whole system has to arrive in an
#      initrd; there is nothing to mount a root filesystem from.
#   2. It does not implement the T-HEAD C9xx MAEE page-table extensions that
#      Canaan's SDK kernels use, so only a kernel built with standard RISC-V
#      PTE bits will run. The stock nixpkgs riscv64 kernel qualifies; the
#      Xuantie kernel `the-screen-comes-up-under-linux` needs does not.
#
# The consequence worth stating plainly: a successful boot here is evidence
# that the closure builds and starts. It is NOT evidence about the board, and
# it never exercises the vendored boot chain.
{ modulesPath, ... }:

{
  imports = [ "${modulesPath}/installer/netboot/netboot-minimal.nix" ];

  # netboot-minimal turns the whole system into a ramdisk, which is the only
  # root available on this machine.
  boot.loader.grub.enable = false;
}
