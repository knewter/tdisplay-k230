# OpenSBI 1.4 with Canaan's overlay, built by this project.
#
# NOT nixpkgs' opensbi (1.8.1 at the flake's pin), and the reason is one
# quirk bit. Upstream does match `canaan,kendryte-k230` in
# platform/generic/thead/thead-generic.c -- but with `thead_pmu_quirks`
# only. Canaan's overlay matches the same compatible with
# `THEAD_QUIRK_DISABLE_MAEE` and calls thead_disable_maee(), which clears
# MXSTATUS.MAEE so that the standard RISC-V page-table attribute bits mean
# what the kernel thinks they mean. Upstream's c9xx_errata.h has no such
# quirk. MAEE left on is the kind of fault that boots and corrupts memory
# later. So: the version the vendor ships, plus the nine files the vendor
# changes, all readable:
#
#   include/sbi/sbi_hart.h                          lib/sbi/sbi_init.c
#   lib/sbi/sbi_hart.c                              platform/generic/configs/defconfig
#   platform/generic/thead/thead-generic.c          platform/generic/thead/objects.mk
#   platform/generic/thead/thead_c9xx_disable_maee.c
#   platform/generic/include/thead/c9xx_errata.h    platform/generic/include/thead/c9xx_encoding.h
#
# Built as the SDK builds it (buildroot-overlay/boot/opensbi/opensbi.mk plus
# k230_canmv_v3_defconfig): PLATFORM=generic, FW_TEXT_START=0. The SDK also
# passes FW_PAYLOAD_PATH to make a fw_payload the card never uses; only
# fw_jump.bin goes on the card, wrapped by nix/stage1.nix.
#
# With FW_TEXT_START=0, platform/generic/objects.mk derives
# FW_JUMP_ADDR=0x200000, which this build keeps, and FW_JUMP_FDT_ADDR=
# 0x2200000, which it deliberately does not -- the one place this stage 1
# departs from the vendor's. See the makeFlags below.
{ lib
, stdenv
, fetchFromGitHub
, buildPackages
, overrideCC
, k230Sdk
  # OpenSBI 1.4 does not build under GCC 15. GCC 15 defaults to C23, in
  # which `bool` is a keyword, and include/sbi/sbi_types.h:47 says
  # `typedef int bool;`; with the tree's -Werror that is fatal
  # ("'bool' cannot be defined via 'typedef'"). Observed 2026-09-22 on the
  # first build. GCC 13 defaults to gnu17 and compiles it unchanged. A
  # compiler pin rather than a patch, as the design says: one legible,
  # reversible line, and the vendor tree stays the vendor tree.
, useGcc13 ? true
}:

let
  stdenv' = if useGcc13 then overrideCC stdenv buildPackages.gcc13 else stdenv;
in
stdenv'.mkDerivation {
  pname = "opensbi-k230";
  version = "1.4";

  src = fetchFromGitHub {
    owner = "riscv-software-src";
    repo = "opensbi";
    tag = "v1.4";
    hash = "sha256-T8ZeAzjM9aeTXitjE7s+m+jjGGtDo2jK1qO5EuKiVLU=";
  };

  postPatch = ''
    cp -r ${k230Sdk}/buildroot-overlay/boot/opensbi/opensbi-1.4-overlay/. .
    chmod -R u+w .
    patchShebangs scripts
  '';

  nativeBuildInputs = [ buildPackages.python3 ];

  makeFlags = [
    "PLATFORM=generic"
    "FW_TEXT_START=0"
    "CROSS_COMPILE=${stdenv'.cc.targetPrefix}"
    # Leave FW_JUMP_FDT_ADDR undefined, so fw_jump hands the kernel the
    # device tree where bootm put it instead of copying it to a fixed
    # address. The vendor's build defines it as FW_TEXT_START + 0x2200000
    # (platform/generic/objects.mk:35); fw_jump.S:46-52 then makes
    # fw_next_arg1 return that constant and fw_base.S:391-396 copies the
    # FDT there. 0x2200000 is Image + 0x2000000, which on this kernel is
    # inside .BTF (__start_BTF Image+0x1fc78a4 .. __stop_BTF Image+0x30fef04):
    # docs/evidence/opensbi-fdt-lands-in-kernel-image.md reads the FDT
    # header back out of /sys/kernel/btf/vmlinux on the board, which is also
    # why every boot printed "Kernel module BTF mismatch detected". The
    # mechanism: firmware/objects.mk:44 guards the -D with `ifdef
    # FW_JUMP_FDT_ADDR`, and GNU make's ifdef is false for a variable whose
    # value is empty, so an empty assignment on the command line -- which
    # overrides the makefile's -- takes fw_jump.S's #else branch
    # (`add a0, a1, zero`). No source is patched.
    # docs/evidence/opensbi-fdt-passthrough.txt is the disassembly, before
    # and after.
    "FW_JUMP_FDT_ADDR="
    # ...and do not build fw_payload at all. The card never carries it (the
    # SDK builds one because buildroot passes FW_PAYLOAD_PATH; blinux loads
    # fw_jump), and it cannot be built alongside the line above:
    # platform/generic/objects.mk:44 says `FW_PAYLOAD_FDT_ADDR=$(FW_JUMP_FDT_ADDR)`,
    # a recursively expanded variable whose *unexpanded* text is non-empty,
    # so `ifdef FW_PAYLOAD_FDT_ADDR` at firmware/objects.mk:62 stays true
    # while its value expands to nothing, and fw_payload.S:48 becomes
    # `li a0,` -- "illegal operands", observed 2026-09-22 on the first try.
    "FW_PAYLOAD=n"
  ];

  enableParallelBuilding = true;
  dontStrip = true;
  dontPatchELF = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out
    cp build/platform/generic/firmware/fw_jump.bin build/platform/generic/firmware/fw_jump.elf $out/
    cp build/platform/generic/kconfig/.config $out/config

    # Two things the overlay is for, checked in the output rather than
    # assumed: the match-table entry for this SoC, and the MAEE quirk
    # actually linked in.
    grep -q 'canaan,kendryte-k230' $out/fw_jump.bin \
      || { echo "error: fw_jump.bin does not carry the canaan,kendryte-k230 compatible" >&2; exit 1; }
    ${stdenv'.cc.targetPrefix}nm $out/fw_jump.elf | grep -q ' thead_disable_maee$' \
      || { echo "error: thead_disable_maee is not linked into fw_jump" >&2; exit 1; }
    echo "opensbi-k230: fw_jump.bin is $(stat -c %s $out/fw_jump.bin) bytes; carries canaan,kendryte-k230 and thead_disable_maee"
    runHook postInstall
  '';

  meta = {
    description = "OpenSBI 1.4 with Canaan's K230 overlay (generic platform, FW_TEXT_START=0)";
    license = lib.licenses.bsd2;
    platforms = [ "riscv64-linux" ];
  };
}
