let
  f = builtins.getFlake "/home/jadams/tmp/k230-hdmi";
  pkgs = f.nixosConfigurations.k230-mainline-drm-shell.pkgs;
  kernel = f.packages.x86_64-linux.kernelMainlineDrm;
in pkgs.stdenv.mkDerivation {
  name = "k230-uinput-live-trial";
  dontUnpack = true;
  nativeBuildInputs = kernel.moduleBuildDependencies;
  buildPhase = ''
    mkdir -p drivers/input/misc
    cp ${kernel.src}/drivers/input/misc/uinput.c drivers/input/misc/
    cp ${kernel.src}/drivers/input/input-compat.h drivers/input/
    printf 'obj-m += uinput.o\n' > drivers/input/misc/Makefile
    make -C ${kernel.dev}/lib/modules/${kernel.modDirVersion}/build \
      M=$PWD/drivers/input/misc ARCH=riscv CROSS_COMPILE=${pkgs.stdenv.cc.targetPrefix} modules
  '';
  installPhase = ''
    mkdir -p $out
    cp drivers/input/misc/uinput.ko $out/
  '';
}
