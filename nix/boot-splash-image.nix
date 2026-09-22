# The stage-1 logo path takes a raw 568x1232 XRGB8888 framebuffer.  On this
# little-endian board its bytes are B, G, R, X.  Keep the source PNG in the
# tree for future first-frame users; this derivation makes the stage-1 form.
{ lib
, runCommand
, imagemagick
, python3
}:

let
  width = 568;
  height = 1232;
  bytes = width * height * 4;
  source = ../assets/boot-splash.png;
in
runCommand "k230-boot-splash-image" {
  nativeBuildInputs = [ imagemagick python3 ];
  passthru = { inherit width height bytes source; };
} ''
  set -euo pipefail
  mkdir -p $out

  dimensions="$(${imagemagick}/bin/magick identify -format '%w %h %[channels]' ${source})"
  test "$dimensions" = '${toString width} ${toString height} srgb'

  # ImageMagick writes RGB reliably.  Add X and reorder explicitly so the
  # stage-1 bytes are B,G,R,X regardless of ImageMagick raw-coder aliases.
  ${imagemagick}/bin/magick ${source} -alpha off -depth 8 RGB:$out/logo.rgb
  ${python3}/bin/python3 - <<'PY'
  import os
  from pathlib import Path

  out = Path(os.environ["out"])
  rgb = (out / "logo.rgb").read_bytes()
  expected = 568 * 1232 * 3
  if len(rgb) != expected:
      raise SystemExit(f"RGB conversion is {len(rgb)} bytes, expected {expected}")
  xrgb = bytearray(568 * 1232 * 4)
  for pixel in range(568 * 1232):
      red, green, blue = rgb[pixel * 3:pixel * 3 + 3]
      xrgb[pixel * 4:pixel * 4 + 4] = bytes((blue, green, red, 255))
  (out / "logo.xrgb").write_bytes(xrgb)
  PY
  rm $out/logo.rgb
  test "$(stat -c %s $out/logo.xrgb)" -eq ${toString bytes}

  # Top-left is the declared RGB(10,16,32) dark field, so the first framebuffer
  # word is B,G,R,X = 32,16,10,255.  This catches an apparently valid RGBX
  # conversion with red and blue swapped.
  test "$(od -An -v -tu1 -N4 $out/logo.xrgb | tr -d '[:space:]')" = 321610255

  cat > $out/README <<'EOF'
  logo.xrgb is 568x1232 XRGB8888, stored B,G,R,X for the little-endian K230.
  It is derived from assets/boot-splash.png by nix/boot-splash.nix.
  EOF
''
