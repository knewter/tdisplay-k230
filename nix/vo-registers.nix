# Narrow read-only display-state diagnostic; not installed in the daily image.
{ stdenv }:
stdenv.mkDerivation {
  pname = "k230-vo-registers";
  version = "0.1";
  src = ../tools/vo-registers.c;
  dontUnpack = true;
  buildPhase = "$CC -O2 -Wall -Wextra -Werror -o vo-registers $src";
  installPhase = "mkdir -p $out/bin; cp vo-registers $out/bin/";
}
