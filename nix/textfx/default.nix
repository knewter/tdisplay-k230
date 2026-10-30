{ stdenv, pkg-config, libdrm }:

# k230-textfx: plays a live ttfx effect on the panel, in the splash owner's
# manner (nix/drm-splash). openspec change the-boot-plays-terminal-text-effects.
# The glyph renderer is shared with stage 1 (src/textfx.c); the font table is
# generated from GNU Unifont by tools/gen-textfx-font.py.
stdenv.mkDerivation {
  pname = "k230-textfx";
  version = "0.1";
  src = ./.;

  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ libdrm ];

  buildPhase = ''
    $CC -std=c11 -O2 -Wall -Wextra -Werror \
      -I ${../../src} \
      -o k230-textfx textfx-play.c ${../../src/textfx.c} ${../../src/textfx_font.c} ${../../src/textfx_record.c} \
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
