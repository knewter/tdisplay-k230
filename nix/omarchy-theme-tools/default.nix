{ lib, stdenvNoCC, makeWrapper, bash, coreutils, gawk, gnused, gnugrep, findutils }:

stdenvNoCC.mkDerivation {
  pname = "omarchy-theme-tools";
  version = "28ceaae7";
  src = ./upstream;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/libexec/omarchy-theme-tools" "$out/share/omarchy/default" "$out/share/doc/omarchy-theme-tools" "$out/bin"
    cp -R bin/. "$out/libexec/omarchy-theme-tools/"
    cp -R default/themed "$out/share/omarchy/default/"
    cp LICENSE "$out/share/doc/omarchy-theme-tools/LICENSE"
    for name in omarchy-theme-color omarchy-theme-set-templates omarchy-theme-colors-from-alacritty omarchy-theme-osc; do
      makeWrapper ${bash}/bin/bash "$out/bin/$name" \
        --add-flags "$out/libexec/omarchy-theme-tools/$name" \
        --set OMARCHY_PATH "$out/share/omarchy" \
        --prefix PATH : "$out/bin:${coreutils}/bin:${gawk}/bin:${gnused}/bin:${gnugrep}/bin:${findutils}/bin"
    done
    runHook postInstall
  '';

  meta = {
    description = "Pinned Omarchy Quattro palette and template helpers for the K230 shell";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
