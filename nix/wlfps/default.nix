# wlfps: a frame-callback cadence probe supporting runtime/shell task 6.1.
# This is not physical presentation timing. See wlfps.c for the limits.
#
# The layer-shell protocol XML is taken from the same wlroots source the
# compositor is built from, so client and compositor cannot disagree about
# the protocol version. xdg-shell is needed only because layer-shell's
# get_popup names xdg_popup.
{ stdenv, pkg-config, wayland-scanner, wayland, wayland-protocols, wlroots_0_20 }:

stdenv.mkDerivation {
  pname = "wlfps";
  version = "0.1";
  src = ./.;

  nativeBuildInputs = [ pkg-config wayland-scanner ];
  buildInputs = [ wayland ];

  buildPhase = ''
    runHook preBuild
    layer=${wlroots_0_20.src}/protocol/wlr-layer-shell-unstable-v1.xml
    xdg=${wayland-protocols}/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml
    wayland-scanner client-header $layer wlr-layer-shell-unstable-v1-client-protocol.h
    wayland-scanner private-code  $layer wlr-layer-shell-unstable-v1-protocol.c
    wayland-scanner client-header $xdg   xdg-shell-client-protocol.h
    wayland-scanner private-code  $xdg   xdg-shell-protocol.c
    $CC -std=c11 -O2 -Wall -o wlfps wlfps.c \
      wlr-layer-shell-unstable-v1-protocol.c xdg-shell-protocol.c \
      $($PKG_CONFIG --cflags --libs wayland-client) -lrt
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    install -Dm755 wlfps $out/bin/wlfps
    runHook postInstall
  '';

  meta.description = "Count a wlroots compositor's frame callbacks from a tiny layer-shell surface";
}
