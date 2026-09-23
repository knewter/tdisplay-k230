# Diagnostic only: link the real opt-in library, use its pinned private test API
# to count executed RVV callbacks. Never use this instrumented process for costs.
{ stdenv, pkg-config, buildPackages, pixman }:
stdenv.mkDerivation {
  pname = "k230-pixman-rvv-pixel-probe";
  version = "0.1";
  src = pixman.src;
  nativeBuildInputs = [ pkg-config buildPackages.python3 ];
  buildInputs = [ pixman ];
  buildPhase = ''
    python3 - <<'PY'
    with open('rvv-wrappers.h', 'w') as out:
        for i in range(256):
            out.write(f'WRAP_SLOT({i})\n')
        out.write('static pixman_composite_func_t wrappers[] = {\n')
        for i in range(256):
            out.write(f'wrap_{i},\n')
        out.write('};\n')
    PY
    $CC -O2 -Wall -Wextra -Werror -march=rv64gc -mabi=lp64d \
      -DPACKAGE=\"pixman\" -DTLS=__thread -I. -Ipixman $($PKG_CONFIG --cflags pixman-1) \
      ${./pixman-rvv-pixel-probe.c} $($PKG_CONFIG --libs pixman-1) \
      -o k230-pixman-rvv-pixel-probe
  '';
  installPhase = ''
    install -Dm755 k230-pixman-rvv-pixel-probe $out/bin/k230-pixman-rvv-pixel-probe
  '';
}
