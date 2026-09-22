{ stdenv, pkg-config, libdrm, bootSplashImage }:

stdenv.mkDerivation {
  pname = "k230-drm-splash";
  version = "0.1";
  src = ./.;

  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ libdrm ];

  buildPhase = ''
    $CC -std=c11 -O2 -Wall -Wextra -Werror -D_POSIX_C_SOURCE=200809L \
      -DDEFAULT_ASSET='"${bootSplashImage}/logo.xrgb"' \
      -o k230-drm-splash drm-splash.c $($PKG_CONFIG --cflags --libs libdrm)
  '';

  installPhase = ''
    install -Dm755 k230-drm-splash $out/bin/k230-drm-splash
  '';

  meta = {
    description = "Static K230 DRM splash owner for the stage-1 handoff";
    mainProgram = "k230-drm-splash";
  };
}
