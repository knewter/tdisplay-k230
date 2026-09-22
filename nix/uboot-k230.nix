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
  # USB device mode for `ums`, with the host controller restored by the
  # K230-specific compatible and gadget bind guard in patches 0002/0003.
  # The fragment records the historical host-off A1 and current A2 intent.
  # buildUBoot appends this after `make defconfig`;
  # Kconfig's syncconfig then takes the later value for a symbol set twice.
  extraConfig = builtins.readFile ./uboot-k230-ums.config;
  # Turning USB_GADGET on makes a dozen previously-hidden symbols visible
  # (USB_FUNCTION_FASTBOOT, USB_GADGET_MANUFACTURER, ...), and a non-
  # interactive `make` then dies in syncconfig with "Error in reading or
  # end of file" asking about them. olddefconfig answers each with its
  # default, which is what a defconfig would have done. Observed on the
  # first build with the fragment, 2026-09-22.
  postConfigure = ''
    make olddefconfig
  '';
  filesToInstall = [ "u-boot.bin" "spl/u-boot-spl.bin" ];
  # The one place the vendor tree fights GCC 15, and it is in code the ums
  # configuration newly compiles: Canaan's addition to
  # drivers/usb/gadget/dwc2_udc_otg.c (dwc2_udc_otg_probe, "// kendryte")
  # passes the USB PHY test-control register addresses to readl()/writel()
  # as bare u32 constants (0x9158507cU / 0x9158509cU). GCC 13 warned; GCC 14
  # made -Wint-conversion an error, and the build died there on 2026-09-22.
  # The conversion is well defined on rv64 (a 32-bit unsigned address,
  # zero-extended), so demote that one diagnostic back to a warning rather
  # than pin the whole tree to GCC 13: the SPL and U-Boot the board booted
  # were compiled by GCC 15, and this keeps everything but the new driver
  # byte-for-byte the same compiler's output. Recorded in
  # docs/evidence/uboot-ums-build.txt.
  extraMakeFlags = [ "KCFLAGS=-Wno-error=int-conversion" ];
  extraMeta.platforms = [ "riscv64-linux" ];

  # The overlay, applied the way the SDK applies it: every file in the
  # overlay replaces or adds to the vanilla tree. Then the vendor's own
  # scripts need their interpreters resolved -- ddr.sh is `#!/bin/bash` and
  # is run directly from board/canaan/k230_canmv/Makefile.
  postPatch = ''
    cp -r ${overlay}/. .
    chmod -R u+w .
    patchShebangs tools scripts arch/riscv/cpu/k230
    # This project's own changes to the vendor tree, as patch files so they
    # are reviewable and so nothing here is a hand edit. Applied after the
    # overlay, which is what they are written against.
    for p in ${./patches/uboot-k230}/*.patch; do
      echo "applying $p"
      patch -p1 < "$p"
    done
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
    # The device tree U-Boot embeds (CONFIG_OF_EMBED), so a node's status
    # can be checked with fdtget without disassembling u-boot.bin.
    cp arch/riscv/dts/k230_canmv_v3.dtb $out/
    # Say what ISA the compiler emitted, next to the binaries, so the
    # "no vendor toolchain needed" claim is checkable from the output.
    ${stdenv'.cc.targetPrefix}readelf -A u-boot spl/u-boot-spl > $out/readelf-A.txt
    runHook postInstall
  '';
}).overrideAttrs (old: {
  # ddr.sh: gawk (asorti, strtonum) and xxd -r -p.
  nativeBuildInputs = old.nativeBuildInputs ++ [ buildPackages.gawk buildPackages.xxd ];
})
