# k230-life-wayland: optional Wayland continuation of the boot Game of Life
# (the-boot-shows-a-computational-game-of-life task 3.3).  A background-layer
# layer-shell client built on the shared engine and the early-Linux state
# loader; protocol XML comes from the same wlroots source as the compositor
# (see nix/wlfps/default.nix).
{ stdenv, pkg-config, wayland-scanner, wayland, wayland-protocols, wlroots_0_20 }:

stdenv.mkDerivation {
  pname = "k230-life-wayland";
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
    $CC -std=c11 -O2 -Wall -Wextra -Werror -D_POSIX_C_SOURCE=200809L \
      -I ${../../src} -I ${../drm-splash} -I . \
      -o k230-life-wayland life-wayland.c ${../drm-splash/life.c} ${../../src/game_of_life.c} \
      wlr-layer-shell-unstable-v1-protocol.c xdg-shell-protocol.c \
      $($PKG_CONFIG --cflags --libs wayland-client) -lrt
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    install -Dm755 k230-life-wayland $out/bin/k230-life-wayland
    runHook postInstall
  '';

  meta.description = "Optional background-layer Game of Life that continues the boot animation under the shell";
}
