# Desktop-entry discovery and text rendering reuse the session libraries.
# Generate protocol bindings from
# the pinned Wayland/wlroots sources used by the Sway session.
{ stdenv, pkg-config, wayland-scanner, wayland, wayland-protocols, wlroots_0_20, glib, pango, cairo, librsvg }:
stdenv.mkDerivation {
  pname = "k230-touch-launcher";
  version = "0.1";
  src = ./.;
  nativeBuildInputs = [ pkg-config wayland-scanner ];
  # librsvg is the SVG decoder for the installed Foot/htop/mpv icon assets;
  # direct linking avoids a runtime gdk-pixbuf loader-cache dependency.
  buildInputs = [ wayland glib pango cairo librsvg ];
  buildPhase = ''
    layer=${wlroots_0_20.src}/protocol/wlr-layer-shell-unstable-v1.xml
    xdg=${wayland-protocols}/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml
    wayland-scanner client-header $layer wlr-layer-shell-unstable-v1-client-protocol.h
    wayland-scanner private-code $layer wlr-layer-shell-unstable-v1-protocol.c
    wayland-scanner client-header $xdg xdg-shell-client-protocol.h
    wayland-scanner private-code $xdg xdg-shell-protocol.c
    $CC -std=c11 -O2 -Wall -DK230_CATALOG_LIBRARY -o k230-touch-launcher touch-launcher.c catalog.c icon.c \
      wlr-layer-shell-unstable-v1-protocol.c xdg-shell-protocol.c \
      $($PKG_CONFIG --cflags --libs wayland-client gio-unix-2.0 pangocairo librsvg-2.0) -lm -lrt
    $CC -std=c11 -O2 -Wall -o k230-desktop-catalog catalog.c $($PKG_CONFIG --cflags --libs gio-unix-2.0)
    $STRIP k230-touch-launcher k230-desktop-catalog
  '';
  installPhase = "install -Dm755 k230-touch-launcher $out/bin/k230-touch-launcher
    install -Dm755 k230-desktop-catalog $out/bin/k230-desktop-catalog";
  meta.description = "Small native portrait Apps surface for the K230 Sway shell";
}
