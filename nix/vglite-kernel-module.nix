# The VeriSilicon VG-Lite (GC8000UL) kernel driver for the MAINLINE 7.3 kernel,
# built out of tree against the exact kernel the board boots (same pattern as
# nix/k230-wifi-driver.nix), so the kernel Image is untouched.
#
# openspec/changes/the-mainline-kernel-drives-the-vglite-gpu.
#
# Source: drivers/gpu/vglite in ruyisdk/linux-xuantie-kernel @
# 7d4e1f444f461dbe3833bd99a4640e7b6c2cd529, copied to
# nix/patches/mainline/vglite/ and adapted to the 7.3 API; the differences are
# listed in docs/evidence/vglite-mainline-kernel/port-notes.md.
#
# Two modules come out:
#   vglite.ko          the driver; binds compatible "verisilicon,gc8000ul"
#   vglite_overlay.ko  trial helper: applies the same gpu node as a runtime
#                      device-tree overlay so the driver can be tried without
#                      changing /boot. Never loaded at boot.
{ lib, stdenv, kernel, dtc, xxd, kernelMainlineSrc }:

stdenv.mkDerivation {
  pname = "k230-vglite-module";
  version = "7.3-port";

  src = ./patches/mainline/vglite;

  nativeBuildInputs = kernel.moduleBuildDependencies ++ [ dtc xxd ];

  postUnpack = ''
    cp ${./dts/k230-vglite-gpu-overlay.dts} $sourceRoot/overlay.dts
  '';

  # Preprocess like nix/device-tree-mainline-drm.nix, compile the overlay with
  # symbols resolved by label (-@ fixups against the base tree's __symbols__),
  # and embed it as a byte array.
  preBuild = ''
    $CC -E -nostdinc \
      -I ${./patches/mainline/include} \
      -I ${kernelMainlineSrc}/scripts/dtc/include-prefixes \
      -undef -D__DTS__ -x assembler-with-cpp \
      -o overlay.dts.pre overlay.dts
    dtc -I dts -O dtb -@ -o overlay.dtbo overlay.dts.pre
    {
      echo '#include <linux/types.h>'
      echo 'const unsigned char vglite_overlay_dtbo[] __aligned(8) = {'
      xxd -i < overlay.dtbo
      echo '};'
      echo "const unsigned int vglite_overlay_dtbo_len = $(stat -c %s overlay.dtbo);"
    } > vglite_overlay_blob.c

    cat > Kbuild <<'EOF'
    obj-m += vglite.o vglite_overlay.o
    vglite-objs := vg_lite_hal.o vg_lite_kernel.o
    vglite_overlay-objs := vglite_overlay_main.o vglite_overlay_blob.o
    ccflags-y += -I$(src)
    EOF
    mv vglite_overlay.c vglite_overlay_main.c
  '';

  makeFlags = [
    "-C" "${kernel.dev}/lib/modules/${kernel.modDirVersion}/build"
    "M=$(PWD)"
    "ARCH=riscv"
    "CROSS_COMPILE=${stdenv.cc.targetPrefix}"
  ];
  buildFlags = [ "modules" ];

  installPhase = ''
    install -Dm444 vglite.ko "$out/lib/modules/${kernel.modDirVersion}/extra/vglite.ko"
    install -Dm444 vglite_overlay.ko "$out/lib/modules/${kernel.modDirVersion}/extra/vglite_overlay.ko"
    install -Dm444 overlay.dtbo "$out/share/vglite/vglite-gpu-overlay.dtbo"
  '';

  meta = {
    description = "VG-Lite GPU driver and trial overlay for the T-Display-K230 mainline kernel";
    license = lib.licenses.gpl2Only;
    platforms = [ "riscv64-linux" ];
  };
}
