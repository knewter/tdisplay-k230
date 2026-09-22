# Stage 1: the boot chain that runs before our kernel.
#
#   BootROM -> U-Boot SPL (+ DDR PMU training firmware)
#           -> U-Boot 2022.10 -> OpenSBI 1.4 -> our kernel
#
# Built here, from source, by the flake:
#
#   nix/uboot-k230.nix     u-boot.bin and spl/u-boot-spl.bin, compiled
#   nix/opensbi-k230.nix   fw_jump.bin, compiled
#   this file              the packaging that turns those into what the
#                          BootROM and U-Boot load, and the environment
#
# The packaging reproduces the SDK's post-image.sh (buildroot-overlay/board/
# canaan/k230-soc/post-image.sh, functions k230_gzip, bin_gzip_ubootHead_
# firmHead, add_firmHead, gen_env_bin and gen_boot_ext4) step for step:
#
#   fn_ug_u-boot.bin   gzip -n -8 u-boot.bin
#                      -> CM byte 0x08 -> 0x09      (the SPL's hardware-ugzip signal)
#                      -> mkimage -A riscv -C gzip -O u-boot -T firmware -a 0 -e 0 -n uboot
#                      -> firmware_gen_no_securiy.py -n   ("K230" header, SHA-256, no crypto)
#   fn_u-boot-spl.bin  firmware_gen_no_securiy.py -n over u-boot-spl.bin
#   env.env            mkenvimage -s 0x2000 over firmware/stage1/tdisplay.env
#   fw_jump_add_uboot_head.bin
#                      mkimage -A riscv -O linux -T kernel -C none -a 0 -e 0 -n linux over fw_jump.bin
#
# The SDK runs tools/k230_priv_gzip for the first step. It is GNU gzip 1.6
# with the name changed and its output is byte-identical to nixpkgs gzip at
# every level the SDK falls back through -- docs/evidence/gzip-equivalence.txt
# is the measurement -- so nixpkgs gzip runs here and no vendor executable
# does. What "priv" actually meant was the one-byte sed on the next line.
#
# SOURCE_DATE_EPOCH is pinned because mkimage stamps the image header with
# the build time and the K230 firmware header carries a SHA-256 over it:
# without the pin two builds of identical inputs differ, and a real change
# is indistinguishable from a rebuild. 1700000000 is the value
# tools/gen-stage1.sh used, so the packaging over the vendor-compiled
# u-boot.bin reproduces the bytes that were on the card
# (c0fb8d95... for fn_ug_u-boot.bin, 3872df5a... for fn_u-boot-spl.bin).
#
# `src` is what nix/sd-image.nix reads: `built`, the stage 1 this flake
# compiled, which the board booted on 2026-09-22
# (docs/evidence/stage1-from-source.txt). The one override is
# K230_STAGE1_DIR under --impure, pointing at the vendor-compiled binaries
# tools/gen-stage1.sh leaves in firmware/stage1/ -- a bisect tool, never a
# default. Both are named in `source` so an image build says which it
# carried.
{ lib
, runCommand
, gzip
, ubootTools
, python3
, gnused
, k230Sdk
, ubootK230
, opensbiK230
}:

let
  overlay = "${k230Sdk}/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay";
  sdkEnvDir = "${k230Sdk}/buildroot-overlay/board/canaan/k230-soc/env";
  epoch = "1700000000";

  # The SDK's mkenvimage over its own default.env, byte for byte. Recorded
  # in docs/blob-inventory.md §A3 on 2026-09-20 and checked on every build
  # so that a change to the vendor default -- which tdisplay.env was
  # derived from by hand -- cannot go unnoticed.
  defaultEnvSha256 = "f522ba13aa8a2e643e61e4fde9f2babb604e86b2f38a487be37c7bdc0b14c957";

  # gzip -> CM byte -> mkimage -> K230 header, over a directory holding
  # u-boot.bin and spl/u-boot-spl.bin (or u-boot-spl.bin at the top).
  # `cmByte = false` leaves the vendor's sed out; it exists to measure what
  # the sed changes, not to ship.
  packagingOf = { ubootDir, cmByte ? true, name ? "k230-stage1-packaging" }:
    runCommand name {
      nativeBuildInputs = [ gzip ubootTools python3 gnused ];
      SOURCE_DATE_EPOCH = epoch;
    } ''
      mkdir -p $out
      spl=${ubootDir}/spl/u-boot-spl.bin
      [ -f "$spl" ] || spl=${ubootDir}/u-boot-spl.bin
      cp ${ubootDir}/u-boot.bin u-boot.bin
      cp "$spl" u-boot-spl.bin
      chmod u+w u-boot.bin u-boot-spl.bin

      # post-image.sh gen_uboot_bin(): the load/entry address comes from the
      # overlay's sdk_autoconf.h, read the way the script reads it.
      base=$(grep CONFIG_MEM_LINUX_SYS_BASE ${overlay}/board/canaan/common/sdk_autoconf.h | awk '{print $3}')
      echo "CONFIG_MEM_LINUX_SYS_BASE=$base"

      # k230_gzip(): the SDK's k230_priv_gzip -n8 is gzip -n -8.
      gzip -n -8 -f -k u-boot.bin
      ${lib.optionalString cmByte ''
        # post-image.sh line 96: the gzip CM byte, 0x08 (deflate) -> 0x09, which
        # arch/riscv/cpu/k230/unzip.c reads as "use the SoC's ugzip DMA engine".
        sed -i -e "1s/\x08/\x09/" u-boot.bin.gz
        cm=$(od -An -tx1 -j2 -N1 u-boot.bin.gz | tr -d ' ')
        [ "$cm" = "09" ] || { echo "error: CM byte is 0x$cm after the sed, expected 0x09" >&2; exit 1; }
      ''}
      echo "gzip header: $(od -An -tx1 -N4 u-boot.bin.gz)"

      # bin_gzip_ubootHead_firmHead(): the U-Boot legacy header, then the
      # K230 firmware header from the U-Boot tree's own script.
      mkimage -A riscv -C gzip -O u-boot -T firmware -a "$base" -e "$base" -n uboot \
        -d u-boot.bin.gz ug_u-boot.bin
      python3 ${overlay}/tools/firmware_gen_no_securiy.py -i ug_u-boot.bin -o $out/fn_ug_u-boot.bin -n

      # add_firmHead u-boot-spl.bin
      python3 ${overlay}/tools/firmware_gen_no_securiy.py -i u-boot-spl.bin -o $out/fn_u-boot-spl.bin -n

      for f in $out/fn_ug_u-boot.bin $out/fn_u-boot-spl.bin; do
        magic=$(head -c 4 "$f")
        [ "$magic" = "K230" ] || { echo "error: $f does not start with the K230 magic" >&2; exit 1; }
      done
      (cd $out && sha256sum fn_u-boot-spl.bin fn_ug_u-boot.bin | tee SHA256SUMS)
    '';

  packaging = packagingOf { ubootDir = ubootK230; };

  env = runCommand "k230-stage1-env" { nativeBuildInputs = [ ubootTools ]; } ''
    mkdir -p $out
    mkenvimage -s 0x2000 -o default.env.env ${sdkEnvDir}/default.env
    got=$(sha256sum default.env.env | cut -d' ' -f1)
    if [ "$got" != "${defaultEnvSha256}" ]; then
      echo "error: mkenvimage over the SDK's default.env gave $got, expected ${defaultEnvSha256}." >&2
      echo "       Either mkenvimage changed or the vendor default did; re-derive firmware/stage1/tdisplay.env." >&2
      exit 1
    fi
    echo "default.env -> $got (matches)"
    cp ${../firmware/stage1/tdisplay.env} $out/tdisplay.env
    mkenvimage -s 0x2000 -o $out/env.env $out/tdisplay.env
    (cd $out && sha256sum env.env | tee SHA256SUMS)
  '';

  # gen_boot_ext4(): the header U-Boot's blinux expects on fw_jump.
  fwJump = runCommand "k230-fw-jump" {
    nativeBuildInputs = [ ubootTools ];
    SOURCE_DATE_EPOCH = epoch;
  } ''
    mkdir -p $out
    cp ${opensbiK230}/fw_jump.bin $out/
    mkimage -A riscv -O linux -T kernel -C none -a 0 -e 0 -n linux \
      -d $out/fw_jump.bin $out/fw_jump_add_uboot_head.bin
    mkimage -l $out/fw_jump_add_uboot_head.bin
    (cd $out && sha256sum fw_jump.bin fw_jump_add_uboot_head.bin | tee SHA256SUMS)
  '';

  files = [ "fn_u-boot-spl.bin" "fn_ug_u-boot.bin" "env.env" "fw_jump.bin" "fw_jump_add_uboot_head.bin" ];

  built = runCommand "k230-stage1" { } ''
    mkdir -p $out
    cp ${packaging}/fn_u-boot-spl.bin ${packaging}/fn_ug_u-boot.bin \
       ${env}/env.env ${env}/tdisplay.env \
       ${fwJump}/fw_jump.bin ${fwJump}/fw_jump_add_uboot_head.bin $out/
    (cd $out && sha256sum ${lib.concatStringsSep " " files} | tee SHA256SUMS)
  '';

  # Only set under --impure; empty otherwise.
  envDir = builtins.getEnv "K230_STAGE1_DIR";
  localDir = if envDir == "" then null else /. + envDir;
  haveLocal = localDir != null
    && builtins.all (f: builtins.pathExists (localDir + "/${f}")) files;
in
{
  inherit packagingOf packaging env fwJump built;
  uboot = ubootK230;
  opensbi = opensbiK230;
  sdk = k230Sdk;

  src =
    if haveLocal then builtins.path { path = localDir; name = "k230-stage1-local"; }
    else built;
  source =
    if haveLocal then "local directory (K230_STAGE1_DIR=${envDir}), vendor-compiled"
    else "built from source by this flake (nix/stage1.nix)";

  # Raw offsets on the card, from the SDK's genimage_cfg/genimage.cfg.
  layout = {
    spl = { file = "fn_u-boot-spl.bin"; offsets = [ 1048576 1572864 ]; };
    uboot = { file = "fn_ug_u-boot.bin"; offsets = [ 2097152 ]; };
    env = { file = "env.env"; offsets = [ 3145728 3276800 ]; };
  };

  builtFromSource = true;

  provenance = {
    sdk = "kendryte/k230_linux_sdk @ 1104236db4d1e47873bd68924f912747b820228c";
    boardConfig = "k230_canmv_v3_defconfig";
    uboot = "2022.10 upstream + Canaan overlay, nixpkgs riscv64 cross GCC";
    opensbi = "1.4 upstream + Canaan overlay, generic platform, FW_TEXT_START=0";
    env = "firmware/stage1/tdisplay.env, derived from the SDK's default.env";
  };
}
