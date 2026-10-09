let
  f = builtins.getFlake "/home/jadams/tmp/k230-hdmi";
  pkgs = f.nixosConfigurations.k230-mainline-drm-shell.pkgs;
  kernel = f.packages.x86_64-linux.kernelMainlineDrm;
in pkgs.stdenv.mkDerivation {
  name = "k230-lt9611-shared-reset-object-check";
  dontUnpack = true;
  nativeBuildInputs = kernel.moduleBuildDependencies;
  buildPhase = ''
    cp ${/home/jadams/tmp/k230-hdmi-continue/nix/patches/mainline/drm/lontium-lt9611-k230.c} lt9611-check.c
    printf 'obj-m += lt9611-check.o\n' > Makefile
    make -C ${kernel.dev}/lib/modules/${kernel.modDirVersion}/build \
      M=$PWD ARCH=riscv CROSS_COMPILE=${pkgs.stdenv.cc.targetPrefix} lt9611-check.o
  '';
  installPhase = ''
    mkdir -p $out
    cp lt9611-check.o $out/
  '';
}
