{ stdenv, pkg-config, libdrm
  # libk230_ttfx_boot.a (nix/ttfx-boot/hosted.nix): when given, the engine is linked in and no
  # ttfx child is needed; null builds the child-process player.
, ttfxBootHosted ? null }:

# k230-textfx: plays a live ttfx effect on the panel, in the splash owner's
# manner (nix/drm-splash). openspec change the-boot-plays-terminal-text-effects.
# The glyph renderer is shared with stage 1 (textfx/textfx.c); the font table is
# generated from GNU Unifont by tools/gen-textfx-font.py.
stdenv.mkDerivation {
  pname = "k230-textfx";
  version = "0.1";
  src = ./.;

  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ libdrm ];

  buildPhase = ''
    $CC -std=c11 -O2 -Wall -Wextra -Werror \
      -I ${../../textfx} \
      ${if ttfxBootHosted == null then "" else "-DTEXTFX_ENGINE_LIB -I ${ttfxBootHosted}/include"} \
      -o k230-textfx textfx-play.c ${../../textfx/textfx.c} ${../../textfx/textfx_font.c} ${../../textfx/textfx_record.c} \
      ${if ttfxBootHosted == null then "" else "${ttfxBootHosted}/lib/libk230_ttfx_boot.a -lgcc_s -lutil -lrt -lpthread -lm -ldl"} \
      $($PKG_CONFIG --cflags --libs libdrm)
  '';

  installPhase = ''
    install -Dm755 k230-textfx $out/bin/k230-textfx
  '';

  meta = {
    description = "Live ttfx text effect on the K230 panel, continuing a stage 1 sequence";
    mainProgram = "k230-textfx";
  };
}
