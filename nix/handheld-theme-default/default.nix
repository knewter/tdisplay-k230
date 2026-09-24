{ lib, stdenvNoCC, fetchFromGitHub, imagemagick }:

let
  bundledIdentity = (builtins.fromJSON (builtins.readFile ./bundled-report.json)).generation;
  recoveryIdentity = (builtins.fromJSON (builtins.readFile ./default-report.json)).generation;
  # Every member of omacom/omarchy's `themes/` collection at the pinned
  # revision. Verified with `ls themes/` against the fetched source and
  # recorded in SOURCE.md; all 22 have a colors.toml palette. catppuccin and
  # catppuccin-latte are already bundled at full upstream resolution and are
  # the pinned fresh-home default's source, with generation identities in
  # bundled-report.json/default-report.json computed from their exact bytes
  # (see SOURCE.md); leave those two out of the resize step below so those
  # committed identities keep matching without regenerating them.
  fullResolutionThemes = [ "catppuccin" "catppuccin-latte" ];
  boundedBackgroundThemes = [
    "ethereal" "everforest" "flexoki-light" "gruvbox" "hackerman" "kanagawa"
    "last-horizon" "lumon" "lupine" "matte-black" "miasma" "nord"
    "osaka-jade" "retro-82" "ristretto" "rose-pine" "solitude" "tokyo-night"
    "vantablack" "white"
  ];
  themeNames = fullResolutionThemes ++ boundedBackgroundThemes;
  # Upstream backgrounds run up to 7680x3215px (SOURCE.md records the
  # measurement); the panel is a 568x1232 portrait AMOLED and the runtime
  # decoder already crops to exact output size on every decode
  # (background_decode.rs), so shipping full-resolution source pixels in
  # the rootfs buys nothing but closure/storage weight. All 92 upstream
  # background images are landscape or square (verified 2026-09-24), so
  # capping the height keeps the crop-to-portrait cover from ever
  # upscaling; a small margin over the panel's 1232px long edge avoids any
  # visible loss on the panel itself.
  backgroundMaxHeight = 1250;
  backgroundQuality = 82;
in

stdenvNoCC.mkDerivation {
  pname = "handheld-theme-default";
  version = "28ceaae7";
  src = fetchFromGitHub {
    owner = "omacom";
    repo = "omarchy";
    rev = "28ceaae70ebac3a0edcc21f2faa77a90dc6d404c";
    hash = "sha256-wxvTIkTGJCwQI65KxAErhXhTrnpbWgIvNfDLG4pfJKs=";
  };
  nativeBuildInputs = [ imagemagick ];
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/share/omarchy/themes" "$out/generations/${bundledIdentity}" \
      "$out/generations/${recoveryIdentity}"

    # Every built-in theme, unchanged, at its pinned upstream path. cp -R
    # preserves the read-only Nix store source mode; make the copy writable
    # so mogrify can resize backgrounds in place below.
    for name in ${lib.concatStringsSep " " themeNames}; do
      cp -R "$src/themes/$name" "$out/share/omarchy/themes/$name"
    done
    chmod -R u+w "$out/share/omarchy/themes"

    # Replace only background images with a bounded derivative at the same
    # relative path and filename, so theme_catalog.py/theme_activate.py need
    # no change to discover, hash, stage or select them. Palette, icon
    # selector, preview art and every other theme file stay byte-identical
    # to the pinned upstream checkout. catppuccin/catppuccin-latte are
    # excluded (see fullResolutionThemes above).
    find ${lib.concatMapStringsSep " " (name: "\"$out/share/omarchy/themes/${name}\"") boundedBackgroundThemes} \
      -path '*/backgrounds/*' -type f \
      \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) \
      -print0 \
      | xargs -0 --no-run-if-empty \
        magick mogrify -auto-orient -resize 'x${toString backgroundMaxHeight}>' \
          -quality ${toString backgroundQuality} -strip

    # The pinned fresh-home default is a derived Catppuccin generation
    # (full upstream resolution; see fullResolutionThemes above), matching
    # the digest recorded in bundled-report.json.
    cp -R "$out/share/omarchy/themes/catppuccin" "$out/generations/${bundledIdentity}/theme"
    install -Dm644 ${./bundled-report.json} "$out/generations/${bundledIdentity}/report.json"
    install -Dm644 ${./bundled-appearance.json} "$out/generations/${bundledIdentity}/appearance.json"
    install -Dm644 ${./default-report.json} "$out/generations/${recoveryIdentity}/report.json"
    install -Dm644 ${./default-appearance.json} "$out/generations/${recoveryIdentity}/appearance.json"
    for id in ${bundledIdentity} ${recoveryIdentity}; do
      install -Dm644 ${./terminal-foot.ini} "$out/generations/$id/terminal-foot.ini"
      install -Dm644 ${./monitor-foot.ini} "$out/generations/$id/monitor-foot.ini"
      install -Dm644 ${./wvkbd.args} "$out/generations/$id/wvkbd.args"
    done
    install -Dm644 "$src/LICENSE" "$out/share/doc/handheld-theme-default/LICENSE"
    runHook postInstall
  '';
  meta = {
    description = "Every pinned Omarchy built-in theme, with bounded portrait backgrounds and a still wallpaper default";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
