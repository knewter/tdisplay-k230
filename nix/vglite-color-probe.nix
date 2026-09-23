{ lib, stdenv, pixman, vgliteProbe }:
stdenv.mkDerivation {
  pname = "k230-vglite-color-probe";
  version = "0.1";
  dontUnpack = true;
  buildPhase = ''
    "$CC" -O2 -Wall -Wextra -Werror \
      -I${vgliteProbe}/include -I${lib.getDev pixman}/include/pixman-1 \
      ${./vglite-color-probe.c} \
      -L${vgliteProbe}/lib -lvg_lite -L${lib.getLib pixman}/lib -lpixman-1 \
      -o k230-vglite-color-probe
  '';
  installPhase = ''
    install -Dm755 k230-vglite-color-probe "$out/bin/k230-vglite-color-probe"
  '';
  meta = {
    description = "Off-screen RGBA/RGBX to RGB565 comparison against Pixman";
    license = lib.licenses.mit;
    platforms = [ "riscv64-linux" ];
  };
}
