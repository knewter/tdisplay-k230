{ lib, stdenv, pkg-config, wayland-scanner, wayland, wayland-protocols }:
stdenv.mkDerivation {
  pname = "card-composition-probe-client";
  version = "0.1";
  src = ./.;
  strictDeps = true;
  nativeBuildInputs = [ pkg-config wayland-scanner ];
  buildInputs = [ wayland ];
  buildPhase = ''
    runHook preBuild
    xdg=${wayland-protocols}/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml
    wayland-scanner client-header "$xdg" xdg-shell-client-protocol.h
    wayland-scanner private-code "$xdg" xdg-shell-protocol.c
    $CC -std=c11 -O2 -Wall -Wextra -Werror -o card-composition-probe-client \
      card-composition-probe-client.c xdg-shell-protocol.c \
      $($PKG_CONFIG --cflags --libs wayland-client)
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm755 card-composition-probe-client $out/bin/card-composition-probe-client
    runHook postInstall
  '';
  meta = {
    description = "Synthetic animated XDG/SHM clients for the opt-in K230 card probe";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
