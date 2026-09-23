{ lib, stdenv }:

stdenv.mkDerivation {
  pname = "mvx-ioctl-trace";
  version = "1";
  src = ../tools/mvx-ioctl-trace.c;
  dontUnpack = true;

  buildPhase = ''
    "$CC" -shared -fPIC -O2 -Wall -Wextra -Werror "$src" -ldl \
      -o libmvx-ioctl-trace.so
  '';

  installPhase = ''
    install -Dm755 libmvx-ioctl-trace.so "$out/lib/libmvx-ioctl-trace.so"
  '';

  meta = {
    description = "Read-only V4L2 QBUF/DQBUF timestamp observer for MVX diagnostics";
    license = lib.licenses.mit;
    platforms = [ "riscv64-linux" ];
  };
}
