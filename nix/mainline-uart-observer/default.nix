{ stdenv, systemd }:
stdenv.mkDerivation {
  pname = "k230-uart-observer";
  version = "1";
  dontUnpack = true;
  buildPhase = ''
    $CC -std=c11 -O2 -Wall -Wextra -Werror \
      '-DUOBS_SYSTEMD="${systemd}/lib/systemd/systemd"' \
      ${./observer.c} -o k230-uart-observer
  '';
  installPhase = ''
    install -Dm755 k230-uart-observer $out/bin/k230-uart-observer
  '';
}
