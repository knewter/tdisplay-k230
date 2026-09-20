# Stage 1 is VENDORED. This project does not build it as part of an image.
#
# The chain before our kernel, from docs/rtsmart-boot-log.txt:
#
#   BootROM -> U-Boot SPL (+ DDR PMU training firmware)
#           -> U-Boot 2022.10 -> OpenSBI -> payload
#
# These binaries came out of kendryte/k230_linux_sdk built with
# k230_canmv_v3_defconfig; firmware/stage1/PROVENANCE.txt records the commit,
# the toolchain and the sha256 of each, and tools/gen-stage1.sh regenerates
# them by reproducing the SDK's own gen_uboot_bin().
#
# They are committed rather than fetched because they were BUILT here, so
# there is no URL for a fixed-output derivation to pull, and at 570 KB the
# cost of carrying them is small against making the repository able to build
# an image with no Docker, no 284 MB SDK checkout and no 1.9 GB toolchain.
{ lib, runCommand }:

let
  src = ../firmware/stage1;

  # Raw offsets on the card, from the SDK's genimage_cfg/genimage.cfg. All
  # outside the MBR partition table.
  layout = {
    spl = { file = "fn_u-boot-spl.bin"; offsets = [ 1048576 1572864 ]; };   # 1M, 1.5M
    uboot = { file = "fn_ug_u-boot.bin"; offsets = [ 2097152 ]; };          # 2M
    env = { file = "env.env"; offsets = [ 3145728 3276800 ]; };             # 3M, 3.5M
  };
in
{
  inherit src layout;

  vendored = true;
  builtFromSource = false;

  provenance = {
    sdk = "kendryte/k230_linux_sdk";
    branch = "dev";
    boardConfig = "k230_canmv_v3_defconfig";
    sha256 = {
      "fn_u-boot-spl.bin" = "3872df5a4e60c53b163a49b31d7b41ee0a407d08d06d18fefe6f8102b3866a94";
      "fn_ug_u-boot.bin" = "0f8feb747ef4437afbe26b9081c19acbd99475086f2b82db64cc3d3195c54579";
      "env.env" = "f522ba13aa8a2e643e61e4fde9f2babb604e86b2f38a487be37c7bdc0b14c957";
    };
  };

  # Fails the build if a committed blob ever stops matching its recorded
  # hash, so a silent swap of vendored firmware cannot pass unnoticed.
  verified = runCommand "k230-stage1-verified" { } ''
    cd ${src}
    echo "3872df5a4e60c53b163a49b31d7b41ee0a407d08d06d18fefe6f8102b3866a94  fn_u-boot-spl.bin
0f8feb747ef4437afbe26b9081c19acbd99475086f2b82db64cc3d3195c54579  fn_ug_u-boot.bin
f522ba13aa8a2e643e61e4fde9f2babb604e86b2f38a487be37c7bdc0b14c957  env.env" \
      | sha256sum -c -
    mkdir -p $out
    cp fn_u-boot-spl.bin fn_ug_u-boot.bin env.env $out/
  '';

  meta.description =
    "Vendored K230 stage 1 (SPL + U-Boot + env), never built from source by "
    + "this project. See firmware/stage1/PROVENANCE.txt.";
}
