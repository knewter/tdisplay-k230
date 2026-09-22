# Four fixed actions need no widget toolkit.  Generate protocol bindings from
# the pinned Wayland/wlroots sources used by the Sway session.
{ stdenv, pkg-config, wayland-scanner, wayland, wayland-protocols, wlroots_0_20 }:
stdenv.mkDerivation {
  pname = "k230-touch-launcher";
  version = "0.1";
  src = ./.;
  nativeBuildInputs = [ pkg-config wayland-scanner ];
  buildInputs = [ wayland ];
  buildPhase = ''
    layer=${wlroots_0_20.src}/protocol/wlr-layer-shell-unstable-v1.xml
    xdg=${wayland-protocols}/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml
    wayland-scanner client-header $layer wlr-layer-shell-unstable-v1-client-protocol.h
    wayland-scanner private-code $layer wlr-layer-shell-unstable-v1-protocol.c
    wayland-scanner client-header $xdg xdg-shell-client-protocol.h
    wayland-scanner private-code $xdg xdg-shell-protocol.c
    $CC -std=c11 -O2 -Wall -Wextra -Werror -o k230-touch-launcher touch-launcher.c \
      wlr-layer-shell-unstable-v1-protocol.c xdg-shell-protocol.c \
      $($PKG_CONFIG --cflags --libs wayland-client) -lrt
  '';
  installPhase = "install -Dm755 k230-touch-launcher $out/bin/k230-touch-launcher";
  meta.description = "Small native portrait Apps surface for the K230 Sway shell";
}
