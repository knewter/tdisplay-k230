# Stage 1 is VENDORED. This project does not build it.
#
# The chain before our kernel on this board is, from docs/rtsmart-boot-log.txt:
#
#   BootROM -> U-Boot SPL 2022.10 (+ DDR PMU training firmware)
#           -> U-Boot 2022.10 -> OpenSBI v0.9 -> payload
#
# Canaan wraps these in a custom header with compression
# ("image: uboot load to 20000000 compress =1"), and SPL carries a binary DDR
# PHY training blob. Reproducing that packaging in Nix is a project in itself
# and is deliberately out of scope — see openspec/specs/image/boot-chain.
#
# This file exists so the boundary is a named, structural thing rather than
# something implied by what happens not to be built. Nothing in this flake may
# compile U-Boot or OpenSBI; `the-board-boots-what-we-built` fills this in with
# a fixed-output derivation pinned by hash.
{ lib }:

{
  # Declared, not yet fetched. Under QEMU nothing occupies this seam: the
  # kernel is loaded directly and no bootloader runs at all.
  vendored = true;
  builtFromSource = false;

  provenance = {
    sdk = "kendryte/k230_linux_sdk";
    boardConfig = "k230_canmv_v3_defconfig";
    # Filled by the-board-boots-what-we-built, task 1.1.
    artifactSha256 = null;
  };

  meta.description =
    "Vendored K230 stage 1 (SPL + DDR training blob + U-Boot + OpenSBI). "
    + "Never built from source by this project.";
}
