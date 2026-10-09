# Object/API check against the prepared 7.3.0-rc5 headers used by the
# accepted HDMI trial. This does not build a full kernel or prove hardware.
{ repo
, kernelDev ? "/nix/store/5psfka6qdgy7pqhxja1vicibs3gpccl0-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev"
}:
let
  f = builtins.getFlake repo;
  pkgs = f.nixosConfigurations.k230-mainline-drm-shell.pkgs;
  kernel = f.packages.x86_64-linux.kernelMainline;
  sources = builtins.path {
    path = repo + "/nix/patches/mainline/drm";
    name = "k230-fast-hpd-sources";
  };
  prepared = builtins.storePath kernelDev;
in pkgs.stdenv.mkDerivation {
  name = "k230-fast-hpd-object-check";
  dontUnpack = true;
  nativeBuildInputs = kernel.moduleBuildDependencies;
  buildPhase = ''
    cp --no-preserve=mode ${sources}/canaan_*.h .
    cp ${sources}/canaan_dsi.c canaan_dsi.c
    cp ${sources}/lontium-lt9611-k230.c lt9611-check.c
    printf 'obj-m += canaan_dsi.o lt9611-check.o\n' > Makefile
    make -C ${prepared}/lib/modules/7.3.0-rc5/build \
      M=$PWD ARCH=riscv CROSS_COMPILE=${pkgs.stdenv.cc.targetPrefix} \
      -j2 canaan_dsi.o lt9611-check.o
  '';
  installPhase = ''
    mkdir -p $out
    cp canaan_dsi.o lt9611-check.o $out/
  '';
}
