# Public Pixman API pixel/copy diagnostic, outside the normal image closure.
{ stdenv, pkg-config, pixman }:
stdenv.mkDerivation {
  pname = "k230-pixman-quarter-turn-probe";
  version = "0.1";
  dontUnpack = true;
  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ pixman ];
  buildPhase = ''
    $CC -O2 -Wall -Wextra -Werror -march=rv64gc -mabi=lp64d \
      -I${./card-shell} $($PKG_CONFIG --cflags pixman-1) \
      ${../tests/pixman_quarter_turn.c} $($PKG_CONFIG --libs pixman-1) -lm \
      -o k230-pixman-quarter-turn-probe
  '';
  installPhase = ''
    install -Dm755 k230-pixman-quarter-turn-probe $out/bin/k230-pixman-quarter-turn-probe
  '';
}
