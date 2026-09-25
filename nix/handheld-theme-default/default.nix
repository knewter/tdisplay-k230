{ lib, stdenvNoCC, fetchFromGitHub, imagemagick, buildPackages }:

let
  bundledReport = builtins.fromJSON (builtins.readFile ./bundled-report.json);
  bundledIdentity = bundledReport.generation;
  bundledBackground = bundledReport.selected_background;
  recoveryIdentity = (builtins.fromJSON (builtins.readFile ./default-report.json)).generation;
  # A native (build-platform) copy of the same Rust shell binary that is
  # cross-compiled onto the device, used only to precompute the pinned
  # bundled generation's panel-sized wallpaper decode at build time
  # (background_decode.rs's `--write-wallpaper-cache` verb). It never runs
  # on the board and ships nothing into the image; `buildPackages` resolves
  # every one of rust-shell-client's own inputs (rustPlatform, wayland,
  # cairo, pango, glib, librsvg) for the build platform automatically, the
  # same pattern nix/opensbi-k230.nix and nix/uboot-k230.nix already use for
  # a native build-time tool.
  wallpaperCacheTool = buildPackages.callPackage ../rust-shell-client { };
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

    # Build-time thumbnails for every bundled built-in theme: a theme's own
    # preview.* gets the Themes page hero carousel's two cached sizes
    # (`theme_carousel::THEME_GEOMETRY`'s `expanded_w/h`=480x640,
    # `slice_w/h`=68x582, rounded -- same numbers that geometry documents
    # against upstream's own ratios), and every background image gets the
    # Preview page's smaller background carousel's two sizes
    # (`BACKGROUND_GEOMETRY`: 420x260, 59x237). `theme_thumbnails.rs`'s
    # worker checks for these at a fixed mirrored path (a `thumbs/` tree
    # alongside `themes/`, never *inside* a theme's own directory --
    # `tools/theme_sources.py::source_digest` hashes that directory
    # recursively for every generation identity, so a cache file living
    # there would silently change what the theme hashes to; see
    # `theme_thumbnails::builtin_thumbnail_path`'s own doc) before its own
    # runtime disk cache or a full decode, so the very first view of a
    # bundled theme on the board never pays for one. Written after the
    # resize step above so a bounded theme's own thumbnail is decoded from
    # its final (already-downscaled) bytes. Advisory, like the wallpaper
    # cache below: any failure here just means that theme falls through to
    # the same slower, fully correct path every theme used before this
    # optimization existed.
    for name in ${lib.concatStringsSep " " themeNames}; do
      themeDir="$out/share/omarchy/themes/$name"
      for previewName in preview.png preview.jpg preview.jpeg preview.webp preview.gif preview.bmp; do
        if [ -f "$themeDir/$previewName" ]; then
          "${wallpaperCacheTool}/bin/k230-shell-rust" --write-thumbnail-cache \
            "$themeDir/$previewName" expanded 480 640 \
            || echo "handheld-theme-default: theme thumbnail precompute skipped ($name expanded)" >&2
          "${wallpaperCacheTool}/bin/k230-shell-rust" --write-thumbnail-cache \
            "$themeDir/$previewName" slice 68 582 \
            || echo "handheld-theme-default: theme thumbnail precompute skipped ($name slice)" >&2
          break
        fi
      done
      if [ -d "$themeDir/backgrounds" ]; then
        find "$themeDir/backgrounds" -maxdepth 1 -type f \
          \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' -o -iname '*.gif' -o -iname '*.bmp' \) \
          -print0 |
        while IFS= read -r -d "" background; do
          "${wallpaperCacheTool}/bin/k230-shell-rust" --write-thumbnail-cache \
            "$background" expanded 420 260 \
            || echo "handheld-theme-default: background thumbnail precompute skipped ($background expanded)" >&2
          "${wallpaperCacheTool}/bin/k230-shell-rust" --write-thumbnail-cache \
            "$background" slice 59 237 \
            || echo "handheld-theme-default: background thumbnail precompute skipped ($background slice)" >&2
        done
      fi
    done

    # The pinned fresh-home default is a derived Catppuccin generation
    # (full upstream resolution; see fullResolutionThemes above), matching
    # the digest recorded in bundled-report.json.
    cp -R "$out/share/omarchy/themes/catppuccin" "$out/generations/${bundledIdentity}/theme"
    install -Dm644 ${./bundled-report.json} "$out/generations/${bundledIdentity}/report.json"
    install -Dm644 ${./bundled-appearance.json} "$out/generations/${bundledIdentity}/appearance.json"
    ${lib.optionalString (bundledBackground != null) ''
      # Precompute the bundled generation's panel-sized wallpaper decode so
      # the very first paint (before any theme is ever explicitly activated;
      # see appearance.rs's pointerless-default bootstrap) loads a small
      # pre-cropped file instead of decoding catppuccin's full-resolution
      # background on the K230's single in-order core. Advisory: if this
      # ever fails, the generation is exactly as correct and only as slow as
      # it was before this optimization existed.
      "${wallpaperCacheTool}/bin/k230-shell-rust" --write-wallpaper-cache \
        "$out/generations/${bundledIdentity}/theme/${bundledBackground}" \
        "$out/generations/${bundledIdentity}" 568 1232 \
        || echo "handheld-theme-default: wallpaper cache precompute skipped" >&2
    ''}
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
