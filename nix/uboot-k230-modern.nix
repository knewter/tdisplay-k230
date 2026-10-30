# Modern (upstream v2026.10) U-Boot for the K230, built by this project.
#
# Stage a of openspec/changes/the-board-boots-a-modern-u-boot: U-Boot PROPER
# only, chained from the existing vendor-derived SPL (nix/uboot-k230.nix),
# which still does DDR training, pin muxing and the SD load, and enters this
# at 0x0 with the hart id in a0.
#
# variant = "upstream"  upstream's own k230_canmv_defconfig, unchanged: the
#                       baseline that proves the toolchain and tree compile
#                       (and that has no MMC, no gadget and no cache enable).
# variant = "tdisplay"  this board: upstream plus the patches in
#                       nix/patches/uboot-modern/ (cache enable and early
#                       hart setup, K230 USB PHY and SDHCI drivers, DWC2
#                       gadget on RISC-V, the board dts and defconfig).
#
# No vendor source is compiled in the tdisplay variant. The vendor pieces
# that were read to write the ports are cited in each file's header and in
# the change's design.md.
{ lib
, buildUBoot
, callPackage
, k230Sdk
, variant ? "tdisplay"
  # RAM trial (stage a0): link at this address instead of 0, so the binary can
  # be loaded beside the running 2022.10 U-Boot and entered with `go` without
  # touching the card. Never packaged into stage1-modern.
, textBase ? null
  # Stage c: an upstream OpenSBI cannot step around the two locked PMP entries
  # (see CONFIG_K230_PMP_LOCK_OTP in the arch Kconfig), so the U-Boot that
  # precedes it is built without the lock.
, lockOtpPmp ? true
  # Opt-in stage-1 Game of Life (the-boot-shows-a-computational-game-of-life)
  # on U-Boot's native cyclic framework; dormant unless the environment sets
  # boot_life=1. The engine and the driver are the files src/ and
  # nix/uboot-k230-life/ already carry for the 2022.10 build.
, bootLife ? false
}:

let
  pin = callPackage ./uboot-k230-modern-src.nix { };
  tdisplay = variant == "tdisplay";
  overlay = "${k230Sdk}/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay";
  splash = import ./boot-splash.nix;
  oldPatches = ./patches/uboot-k230;
in
(buildUBoot {
  inherit (pin) version src;
  defconfig = if tdisplay then "k230_tdisplay_defconfig" else "k230_canmv_defconfig";
  filesToInstall = [ "u-boot.bin" "u-boot" "u-boot.dtb" ".config" ];
  extraMeta.platforms = [ "riscv64-linux" ];
  patches = lib.optionals tdisplay (lib.filesystem.listFilesRecursive ./patches/uboot-modern);
  # One source for the scanout address: the same nix/boot-splash.nix the
  # kernel device tree reads (the defconfig carries the same value as a
  # default; this wins).
  extraConfig = lib.optionalString tdisplay ''
    CONFIG_K230_BARE_DISP_LOGO_FB_ADDR=${splash.framebufferAddress}
  '' + lib.optionalString bootLife ''
    CONFIG_K230_BOOT_LIFE=y
    CONFIG_K230_BOOT_LIFE_RECORD_ADDR=${splash.lifeRecordAddress}
    CONFIG_K230_BOOT_LIFE_WINDOW_BYTES=${splash.lifeRecordWindow}
    CONFIG_K230_BOOT_LIFE_RESERVED_BYTES=${splash.framebufferSize}
    # A full-frame draw takes longer than the 5 ms default, after which
    # cyclic unregisters the callback.
    CONFIG_CYCLIC_MAX_CPU_TIME_US=100000
  '' + lib.optionalString (!lockOtpPmp) ''
    # CONFIG_K230_PMP_LOCK_OTP is not set
  '' + lib.optionalString (textBase != null) ''
    CONFIG_TEXT_BASE=${textBase}
  '';
  # Canaan's RM69A10 splash sources, copied from the pinned SDK and patched
  # with this project's own splash patches (0004 the RM69A10 port, 0005 the
  # readiness flag) exactly as nix/uboot-k230.nix applies them to 2022.10.
  # They are staged in the layout those patches were written against, so the
  # patches stay byte-identical to the ones the shipped stage 1 builds with;
  # only the .c/.h files are taken. Their glue (Makefile, compatibility
  # headers, event hook, Kconfig) is in nix/patches/uboot-modern/.
  #
  # patchShebangs first, with --build: nixpkgs' buildUBoot postPatch does the
  # same, but in a riscv64 cross build the default (host) variant finds no
  # interpreter and leaves scripts/check-local-export on /usr/bin/env, which
  # then fails in the sandbox (first build, 2026-10-30). Setting postPatch
  # here replaces nixpkgs' version, so it is repeated.
  postPatch = ''
    patchShebangs --build tools scripts
  '' + lib.optionalString tdisplay ''
    stage=$(mktemp -d)
    mkdir -p $stage/board/canaan/common $stage/arch/riscv/cpu/k230
    cp -r ${overlay}/board/canaan/common/logo $stage/board/canaan/common/
    cp ${overlay}/arch/riscv/cpu/k230/Kconfig $stage/arch/riscv/cpu/k230/
    cp ${overlay}/board/canaan/common/k230_board_common.c \
       ${overlay}/board/canaan/common/k230_board_common.h $stage/board/canaan/common/
    chmod -R u+w $stage
    (cd $stage && patch -p1 < ${oldPatches}/0004-rm69a10-logo-port.patch \
               && patch -p1 < ${oldPatches}/0005-k230-stage1-splash-readiness.patch)
  '' + lib.optionalString bootLife ''
    (cd $stage && patch -p1 < ${./patches/uboot-modern-life-stage}/0001-boot-life-hook-in-the-logo-sources.patch)
    for f in game_of_life.c game_of_life.h boot_life_stage1.c boot_life_stage1.h boot_frame.c boot_frame.h boot_compat.h; do
      cp ${../src}/$f board/canaan/k230_canmv/life/$f
    done
    cp ${./uboot-k230-life}/k230_boot_life.c board/canaan/k230_canmv/life/k230_boot_life.c
  '' + lib.optionalString tdisplay ''
    cp $stage/board/canaan/common/logo/*.c $stage/board/canaan/common/logo/*.h \
       board/canaan/k230_canmv/logo/
  '';
  # The SPL loads u-boot.bin gzip-compressed from the 2 MiB slot; the next
  # slot (the environment) starts 1 MiB later. nix/stage1.nix compresses it;
  # fail here if even the uncompressed image would not fit.
  postBuild = ''
    size=$(stat -c %s u-boot.bin)
    printf 'u-boot.bin is %d bytes (0x%x); slot is 0x100000\n' "$size" "$size"
    [ "$size" -lt 1048576 ] || { echo "error: u-boot.bin overflows the 1 MiB slot" >&2; exit 1; }
  '';
}).overrideAttrs (old: {
  nativeBuildInputs = old.nativeBuildInputs or [ ];
})
