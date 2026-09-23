{ stdenv, corrupt ? false }:
stdenv.mkDerivation {
  pname = "k230-rvv-context-probe" + (if corrupt then "-corrupt" else "");
  version = "0.1";
  dontUnpack = true;
  buildPhase = ''
    $CC -O2 -Wall -Wextra -Werror -march=rv64gc -mabi=lp64d \
      -c ${./rvv-context-probe.c} -o probe.o
    $CC -march=rv64gcv -mabi=lp64d ${if corrupt then "-DK230_RVV_TEST_CORRUPT" else ""} \
      -c ${./rvv-context-probe.S} -o vector.o
    $CC probe.o vector.o -o k230-rvv-context-probe
  '';
  installPhase = ''
    install -Dm755 k230-rvv-context-probe $out/bin/k230-rvv-context-probe
  '';
}
