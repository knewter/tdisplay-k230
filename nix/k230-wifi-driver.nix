# The out-of-tree SDIO module for the T-Display-K230's RTL8189FTV.
#
# The physical board reports SDIO vendor/device 024c:f179. The selected
# source calls that RTL8188F and builds the SDIO module as 8189fs.ko; see
# docs/evidence/wifi-driver-audit.md before changing this pin or module name.
{ lib, stdenv, fetchFromGitHub, kernel, bc }:

stdenv.mkDerivation (finalAttrs: {
  pname = "k230-wifi-driver";
  version = "94cc959d";

  src = fetchFromGitHub {
    owner = "jwrdegoede";
    repo = "rtl8189ES_linux";
    rev = "94cc959d56c1425fbca4f6e49e949cf58ec5dc8d";
    hash = "sha256-qQwUfhr8jpo5H/TTJ7abHQLvc8Wqi5GCPu47dE/WgBM=";
  };

  # The upstream Makefile uses bc to detect GCC >= 4.9 and add its required
  # -Wno-date-time flag. Without it, the kernel's reproducibility warning is
  # promoted to an error before the module can reach its API checks.
  nativeBuildInputs = kernel.moduleBuildDependencies ++ [ bc ];

  # The vendor Makefile uses KSRC only when it invokes the kernel build. Its
  # default platform selection leaves it empty, so pass the exact Xuantie
  # kernel build tree and cross settings explicitly.
  makeFlags = [
    "KSRC=${kernel.dev}/lib/modules/${kernel.modDirVersion}/build"
    "ARCH=riscv"
    "CROSS_COMPILE=${stdenv.cc.targetPrefix}"
  ];

  installPhase = ''
    install -Dm444 8189fs.ko \
      "$out/lib/modules/${kernel.modDirVersion}/extra/8189fs.ko"
  '';

  meta = {
    description = "RTL8189FTV SDIO Wi-Fi driver for the LILYGO T-Display-K230";
    homepage = "https://github.com/jwrdegoede/rtl8189ES_linux";
    license = lib.licenses.gpl2Only;
    platforms = [ "riscv64-linux" ];
  };
})
