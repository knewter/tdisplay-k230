# OpenSBI v1.9 for the K230, built by this project.
#
# Stage c of openspec/changes/the-board-boots-a-modern-u-boot. Upstream
# v1.9 (2026-07-01) matches canaan,kendryte-k230 in
# platform/generic/thead/thead-generic.c with the T-Head PMU quirk only; the
# one thing Canaan's overlay (nix/opensbi-k230.nix, 1.4) adds that this
# board's kernel depends on is clearing MXSTATUS.MAEE, forward-ported in
# nix/patches/opensbi-modern/. Nothing from the vendor overlay is compiled.
#
# NOT ported: the overlay's PMP "reserved entries" handling
# (sbi_hart_pmp_reserved). It exists to step around the two PMP entries the
# vendor U-Boot locks; the modern U-Boot makes that lock optional
# (CONFIG_K230_PMP_LOCK_OTP) and a v1.9 stage 1 must build it off.
#
# Built as the 1.4 derivation does: PLATFORM=generic, FW_TEXT_START=0, and
# the fixed device-tree location left undefined so fw_jump hands the kernel
# the device tree where bootm put it (docs/evidence/opensbi-fdt-passthrough.txt).
# v1.9 spells the fixed location FW_JUMP_FDT_OFFSET (0x2200000 from
# platform/generic/objects.mk); empty command-line values make `ifdef` false
# for both it and FW_JUMP_FDT_ADDR, so fw_next_arg1 is `add a0, a1, zero`.
{ lib
, stdenv
, fetchFromGitHub
, buildPackages
}:

stdenv.mkDerivation {
  pname = "opensbi-k230-modern";
  version = "1.9";

  src = fetchFromGitHub {
    owner = "riscv-software-src";
    repo = "opensbi";
    tag = "v1.9";
    hash = "sha256-3RXsdo5e494odYtcRMMtAwes2LLniohHlOXEWy6CmrU=";
  };

  patches = lib.filesystem.listFilesRecursive ./patches/opensbi-modern;

  postPatch = ''
    patchShebangs scripts
    # The vendor overlay's defconfig drops semihosting; keep that.
    sed -i '/^CONFIG_SERIAL_SEMIHOSTING=y$/d' platform/generic/configs/defconfig
  '';

  nativeBuildInputs = [ buildPackages.python3 ];

  makeFlags = [
    "PLATFORM=generic"
    "FW_TEXT_START=0"
    "CROSS_COMPILE=${stdenv.cc.targetPrefix}"
    "FW_JUMP_FDT_ADDR="
    "FW_JUMP_FDT_OFFSET="
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
    grep -q 'canaan,kendryte-k230' $out/fw_jump.bin \
      || { echo "error: fw_jump.bin does not carry the canaan,kendryte-k230 compatible" >&2; exit 1; }
    ${stdenv.cc.targetPrefix}nm $out/fw_jump.elf | grep -q ' thead_disable_maee$' \
      || { echo "error: thead_disable_maee is not linked into fw_jump" >&2; exit 1; }
    ! grep -q '^CONFIG_SERIAL_SEMIHOSTING=y' $out/config \
      || { echo "error: semihosting console is on" >&2; exit 1; }
    ${stdenv.cc.targetPrefix}objdump -d --disassemble=fw_next_arg1 $out/fw_jump.elf | grep -q 'lui' \
      && { echo "error: fw_next_arg1 loads a fixed FDT address" >&2; exit 1; }
    echo "opensbi-k230-modern: fw_jump.bin is $(stat -c %s $out/fw_jump.bin) bytes"
    runHook postInstall
  '';

  meta = {
    description = "OpenSBI v1.9 with the K230 MAEE quirk (generic platform, FW_TEXT_START=0)";
    license = lib.licenses.bsd2;
    platforms = [ "riscv64-linux" ];
  };
}
