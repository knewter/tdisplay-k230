{ lib, runCommand, buildPackages }:

# Icons are architecture-independent data. Reuse the pinned native package
# instead of cross-compiling Yaru's GTK build dependencies for the handheld.
runCommand "handheld-theme-icons-${buildPackages.yaru-theme.version}" {
  meta = {
    description = "Yaru icons and inheritance for the bundled Omarchy themes";
    inherit (buildPackages.yaru-theme.meta) license;
    platforms = lib.platforms.all;
  };
} ''
  mkdir -p $out/share/icons
  for theme in Yaru Yaru-purple Yaru-blue Humanity hicolor; do
    cp -a ${buildPackages.yaru-theme}/share/icons/$theme $out/share/icons/
  done
''
