# The board device tree, compiled on its own.
#
# WHY THIS IS NOT IN THE KERNEL DERIVATION
#
# It used to be: nix/kernel.nix copied nix/dts/*.dts{,i} into
# arch/riscv/boot/dts/canaan/ from applyPatches' postPatch and added
# k230-tdisplay.dtb to that directory's Makefile. That works, but it makes
# the kernel's `src` depend on our device tree, so editing a single byte of
# panel-init-sequence invalidated the whole kernel and cost a ~20 minute
# cross-compile. The panel's DCS init sequence is exactly the thing being
# iterated on right now (docs/evidence/rm69a10-init-sequence.md), so that
# was the slowest possible place to put it.
#
# A DTB does not need a built kernel, only the kernel's HEADERS: k230.dtsi
# for the SoC and include/dt-bindings for the GPIO/IRQ/reset constants. So
# the DTS is preprocessed and compiled here, against the pinned source tree
# from nix/kernel-src.nix, and the image takes the DTB from this derivation
# instead of from ${kernel}/dtbs. Rebuild is now seconds.
#
# HOW THIS MATCHES WHAT THE KERNEL WOULD HAVE PRODUCED
#
# The commands below are scripts/Makefile.lib's cmd_dtc, spelled out:
#
#   cmd_dtc = $(HOSTCC) -E $(dtc_cpp_flags) -x assembler-with-cpp -o tmp $< ; \
#             $(DTC) -o $@ -b 0 $(addprefix -i,$(dir $<) $(DTC_INCLUDE)) ...
#   dtc_cpp_flags = -nostdinc $(addprefix -I,$(DTC_INCLUDE)) -undef -D__DTS__
#   DTC_INCLUDE   = $(srctree)/scripts/dtc/include-prefixes
#
# scripts/dtc/include-prefixes/dt-bindings is a symlink to include/dt-bindings,
# so that one -I is what resolves <dt-bindings/...>. The remaining DTC_FLAGS
# in Makefile.lib are all -W warning switches and do not affect the bytes.
#
# -@ is the one flag that does NOT come from the kernel: nixpkgs' kernel
# builder appends it to every `make dtbs`
# (pkgs/os-specific/linux/kernel/build.nix, "DTC_FLAGS=-@"). It emits the
# __symbols__ node and a phandle on every labelled node, for DT overlays.
# Linux ignores both, but without it this DTB differs from the one the
# board is currently running by ~16 KiB of metadata, and changing what the
# hardware sees was not the point of this change. With it, the output is
# byte-identical to ${kernel}/dtbs/canaan/k230-tdisplay.dtb.
#
# $out is a DIRECTORY holding the .dtb, so consumers can copy it by the
# name U-Boot loads it as.
{ runCommandCC
, dtc
, kernelSrc      # nix/kernel-src.nix -- the pinned tree, for headers only
, dtbName ? "k230-tdisplay.dtb"
, bootSplashConfig ? import ./boot-splash.nix
}:

runCommandCC dtbName
{
  nativeBuildInputs = [ dtc ];

  meta.description = "Device tree for the LILYGO T-Display-K230";
}
  ''
    dtsDir=${kernelSrc}/arch/riscv/boot/dts/canaan

    mkdir build
    cd build

    # k230.dtsi and the files it pulls in (k230_clock_provider.dtsi) come
    # from the pinned tree; ours are laid alongside them so that the
    # #include "k230.dtsi" in k230-tdisplay.dts resolves exactly as it did
    # when the file lived in that directory. Copied rather than -I'd at the
    # source so the two sets cannot shadow each other by accident.
    cp --no-preserve=mode "$dtsDir"/*.dtsi .
    cp --no-preserve=mode ${./dts/k230-tdisplay.dts} k230-tdisplay.dts
    cp --no-preserve=mode ${./dts/display-rm69a10-568x1232.dtsi} \
       display-rm69a10-568x1232.dtsi

    # $CC -E, not a separate gcc: the C compiler is already in this
    # derivation's stdenv, and the kernel preprocesses device trees with
    # $(HOSTCC) -E too.
    $CC -E -nostdinc \
      -I ${kernelSrc}/scripts/dtc/include-prefixes \
      -undef -D__DTS__ \
      -DK230_SPLASH_FRAMEBUFFER_ADDRESS=${bootSplashConfig.framebufferAddress} \
      -DK230_SPLASH_FRAMEBUFFER_SIZE=${bootSplashConfig.framebufferSize} \
      -DK230_SPLASH_FRAMEBUFFER_UNIT_ADDRESS=${bootSplashConfig.framebufferUnitAddress} \
      -x assembler-with-cpp \
      -o k230-tdisplay.dts.pre k230-tdisplay.dts

    mkdir -p $out
    dtc -I dts -O dtb -b 0 -@ \
      -i . -i ${kernelSrc}/scripts/dtc/include-prefixes \
      -o $out/${dtbName} k230-tdisplay.dts.pre

    # A DTB that does not round-trip is not a DTB. Cheap here, and the
    # alternative is finding out on the board.
    dtc -I dtb -O dts $out/${dtbName} > /dev/null
  ''
