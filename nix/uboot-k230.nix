# U-Boot 2022.10 for the K230, built by this project.
#
# Two inputs, both pinned by the hash of their source:
#
#   u-boot-2022.10.tar.bz2      upstream, from ftp.denx.de
#   k230_linux_sdk @ 1104236    Canaan's overlay directory, copied over the
#                               tree exactly as the SDK's uboot.mk does with
#                               `rsync -a` (nix/k230-sdk-src.nix)
#
# Then `k230_canmv_v3_defconfig` -- the board configuration LilyGO ships
# RT-Smart under, and the one firmware/stage1/PROVENANCE.txt records for
# the Docker build this replaces -- compiled with nixpkgs' riscv64 cross
# toolchain rather than the 1.9 GB Xuantie GCC the SDK downloads. The ISA
# evidence that the vendor compiler is unnecessary is in
# docs/blob-inventory.md §A7: `readelf -A` on the vendor SPL reports plain
# rv64imac plus zicsr/zifencei, and the T-Head cache ops are hand-encoded
# `.long` words.
#
# What this does NOT make transparent: the DDR PHY training firmware. It
# arrives as C -- board/canaan/k230_canmv_01studio/lpddr4_init_32_swap_2667.c,
# 16 384 reg_write() calls that arch/riscv/cpu/k230/ddr.sh turns back into an
# array at build time -- and compiling it ourselves changes nothing about
# what it is. docs/blob-inventory.md §A5-A6 name, size and hash it.
#
# Outputs: u-boot.bin, spl/u-boot-spl.bin, the two ELFs for `readelf`, and
# the .config the build used.
{ lib
, stdenv
, buildUBoot
, fetchurl
, buildPackages
, overrideCC
, k230Sdk
  # U-Boot 2022.10 against GCC 15 is a three-year gap. If the tree fights,
  # pin GCC 13 here rather than patching Canaan's overlay: a compiler pin is
  # one legible, reversible line.
, useGcc13 ? false
}:

let
  overlay = "${k230Sdk}/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay";
  stdenv' = if useGcc13 then overrideCC stdenv buildPackages.gcc13 else stdenv;
in
(buildUBoot {
  stdenv = stdenv';
  version = "2022.10";
  src = fetchurl {
    url = "https://ftp.denx.de/pub/u-boot/u-boot-2022.10.tar.bz2";
    # 50b4482a505bc281ba8470c399a3c26e145e29b23500bc35c50debd7fa46bdf8,
    # the hash docs/blob-inventory.md §A1-A2 records for the tarball the
    # SDK's dl/ directory holds.
    hash = "sha256-ULRIKlBbwoG6hHDDmaPCbhReKbI1ALw1xQ3r1/pGvfg=";
  };
  defconfig = "k230_canmv_v3_defconfig";
  filesToInstall = [ "u-boot.bin" "spl/u-boot-spl.bin" ];
  extraMeta.platforms = [ "riscv64-linux" ];

  # The overlay, applied the way the SDK applies it: every file in the
  # overlay replaces or adds to the vanilla tree. Then the vendor's own
  # scripts need their interpreters resolved -- ddr.sh is `#!/bin/bash` and
  # is run directly from board/canaan/k230_canmv/Makefile.
  postPatch = ''
    cp -r ${overlay}/. .
    chmod -R u+w .
    patchShebangs tools scripts arch/riscv/cpu/k230
  '';

  # The SPL must fit the slot the BootROM loads it from. U-Boot's own build
  # checks CONFIG_SPL_SIZE_LIMIT too, but silently; this says the number.
  postBuild = ''
    limit=$(sed -n 's/^CONFIG_SPL_SIZE_LIMIT=//p' .config)
    size=$(stat -c %s spl/u-boot-spl.bin)
    printf 'SPL size check: spl/u-boot-spl.bin is %d bytes (0x%x) against CONFIG_SPL_SIZE_LIMIT=%s (%d bytes)\n' \
      "$size" "$size" "$limit" "$((limit))"
    if [ "$size" -gt "$((limit))" ]; then
      echo "error: the SPL exceeds CONFIG_SPL_SIZE_LIMIT; the BootROM would load a truncated image" >&2
      exit 1
    fi
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/spl
    cp u-boot.bin u-boot .config $out/
    cp spl/u-boot-spl.bin spl/u-boot-spl $out/spl/
    # Say what ISA the compiler emitted, next to the binaries, so the
    # "no vendor toolchain needed" claim is checkable from the output.
    ${stdenv'.cc.targetPrefix}readelf -A u-boot spl/u-boot-spl > $out/readelf-A.txt
    runHook postInstall
  '';
}).overrideAttrs (old: {
  # ddr.sh: gawk (asorti, strtonum) and xxd -r -p.
  nativeBuildInputs = old.nativeBuildInputs ++ [ buildPackages.gawk buildPackages.xxd ];
})
