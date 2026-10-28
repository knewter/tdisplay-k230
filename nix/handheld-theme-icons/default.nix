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
  # Viewnior's toolbar names object-rotate-left/right (and the Image menu the
  # flips) as plain icon names. Adwaita, the theme GTK3 apps fall back to when
  # no settings.ini is active, has no such icons, and the Yaru copies are in
  # themes that fallback never reaches, so the two rotate buttons drew blank.
  # hicolor is the last stop of every theme's chain: give it the same Yaru
  # legacy artwork as scalable icons.
  # Yaru's hicolor is a tree of symlinks into other store paths; copy it
  # through them so it can be written.
  rm -rf $out/share/icons/hicolor
  cp -rL --no-preserve=mode ${buildPackages.yaru-theme}/share/icons/hicolor $out/share/icons/hicolor
  chmod -R u+w $out/share/icons/hicolor
  mkdir -p $out/share/icons/hicolor/scalable/actions
  for name in object-rotate-left object-rotate-right object-flip-horizontal object-flip-vertical; do
    install -m644 ${buildPackages.yaru-theme}/share/icons/Yaru/16x16/legacy/$name.svg \
      $out/share/icons/hicolor/scalable/actions/$name.svg
  done
''
