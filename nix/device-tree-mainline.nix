# The mainline-targeted board device tree, compiled on its own -- parallel
# to nix/device-tree.nix (which compiles nix/dts/k230-tdisplay.dts against
# the pinned VENDOR tree). See that file for why a DTB is built without a
# full kernel build at all: same reasoning, same dtc invocation shape,
# applied to nix/dts/k230-tdisplay-mainline.dts and
# nix/kernel-mainline-src.nix instead.
#
# openspec/changes/the-board-runs-a-mainline-kernel. Not referenced by any
# nixosConfigurations output or by nix/sd-image.nix.
{ runCommandCC
, dtc
, kernelMainlineSrc  # nix/kernel-mainline-src.nix -- for k230.dtsi/k230-pinctrl.h/dt-bindings headers only
, dtbName ? "k230-tdisplay-mainline.dtb"
}:

runCommandCC dtbName
{
  nativeBuildInputs = [ dtc ];

  meta.description = "Mainline-targeted device tree for the LILYGO T-Display-K230 (console-only; see nix/kernel-mainline.nix)";
}
  ''
    dtsDir=${kernelMainlineSrc}/arch/riscv/boot/dts/canaan

    mkdir build
    cd build

    cp --no-preserve=mode "$dtsDir"/*.dtsi "$dtsDir"/*.h .
    cp --no-preserve=mode ${./dts/k230-tdisplay-mainline.dts} k230-tdisplay-mainline.dts

    $CC -E -nostdinc \
      -I ${kernelMainlineSrc}/scripts/dtc/include-prefixes \
      -undef -D__DTS__ \
      -x assembler-with-cpp \
      -o k230-tdisplay-mainline.dts.pre k230-tdisplay-mainline.dts

    mkdir -p $out
    dtc -I dts -O dtb -b 0 -@ \
      -i . -i ${kernelMainlineSrc}/scripts/dtc/include-prefixes \
      -o $out/${dtbName} k230-tdisplay-mainline.dts.pre

    # A DTB that does not round-trip is not a DTB.
    dtc -I dtb -O dts $out/${dtbName} > /dev/null
  ''
