{ lib, stdenv, pkg-config, wayland-scanner, wayland, wayland-protocols }:
stdenv.mkDerivation {
  pname = "qtquick-shm-baseline";
  version = "0.1";
  src = ./.;
  strictDeps = true;
  nativeBuildInputs = [ pkg-config wayland-scanner ];
  buildInputs = [ wayland ];
  dontConfigure = true;
  buildPhase = ''
    runHook preBuild
    xdg=${wayland-protocols}/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml
    ti=${wayland-protocols}/share/wayland-protocols/unstable/text-input/text-input-unstable-v3.xml
    wayland-scanner client-header "$xdg" xdg-shell-client-protocol.h
    wayland-scanner private-code "$xdg" xdg-shell-protocol.c
    wayland-scanner client-header "$ti" text-input-unstable-v3-client-protocol.h
    wayland-scanner private-code "$ti" text-input-unstable-v3-protocol.c
    $CC -std=gnu11 -O2 -Wall -Wextra -Werror -o qtquick-shm-baseline \
      baseline.c xdg-shell-protocol.c text-input-unstable-v3-protocol.c \
      $($PKG_CONFIG --cflags --libs wayland-client)
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm755 qtquick-shm-baseline $out/bin/qtquick-shm-baseline
    runHook postInstall
  '';
  meta = {
    description = "Opt-in wl_shm baseline client matching the Qt Quick software probe scene";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
