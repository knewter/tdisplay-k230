# Display/touch DTB for the separate mainline DRM candidate. Kept apart from
# deviceTreeMainline so the existing console-only test artifact is unchanged.
{ runCommandCC
, dtc
, kernelMainlineSrc
, dtbName ? "k230-tdisplay-mainline-drm.dtb"
, dtsFile ? ./dts/k230-tdisplay-mainline-drm.dts
}:

runCommandCC dtbName
{
  nativeBuildInputs = [ dtc ];
  meta.description = "Opt-in mainline VO/DSI/RM69A10/Goodix DTB for T-Display-K230";
}
  ''
    dtsDir=${kernelMainlineSrc}/arch/riscv/boot/dts/canaan

    mkdir build
    cd build

    cp --no-preserve=mode "$dtsDir"/*.dtsi "$dtsDir"/*.h .
    cp --no-preserve=mode ${./dts/k230-tdisplay-mainline.dts} k230-tdisplay-mainline.dts
    cp --no-preserve=mode ${dtsFile} k230-tdisplay-mainline-drm.dts
    cp --no-preserve=mode ${./dts/k230-tdisplay-mainline-drm-common.dtsi} k230-tdisplay-mainline-drm-common.dtsi
    cp --no-preserve=mode ${./dts/display-rm69a10-568x1232.dtsi} display-rm69a10-568x1232.dtsi

    $CC -E -nostdinc \
      -I ${./patches/mainline/include} \
      -I ${kernelMainlineSrc}/scripts/dtc/include-prefixes \
      -undef -D__DTS__ \
      -x assembler-with-cpp \
      -o k230-tdisplay-mainline-drm.dts.pre k230-tdisplay-mainline-drm.dts

    mkdir -p $out
    dtc -I dts -O dtb -b 0 -@ \
      -i . -i ${kernelMainlineSrc}/scripts/dtc/include-prefixes \
      -o $out/${dtbName} k230-tdisplay-mainline-drm.dts.pre
    dtc -I dtb -O dts $out/${dtbName} > /dev/null
  ''
