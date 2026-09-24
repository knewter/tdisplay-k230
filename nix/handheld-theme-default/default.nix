{ lib, stdenvNoCC, fetchFromGitHub }:

let
  bundledIdentity = (builtins.fromJSON (builtins.readFile ./bundled-report.json)).generation;
  recoveryIdentity = (builtins.fromJSON (builtins.readFile ./default-report.json)).generation;
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
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/share/omarchy/themes" "$out/generations/${bundledIdentity}" \
      "$out/generations/${recoveryIdentity}"
    cp -R "$src/themes/catppuccin" "$src/themes/catppuccin-latte" \
      "$out/share/omarchy/themes/"
    cp -R "$src/themes/catppuccin" "$out/generations/${bundledIdentity}/theme"
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
    description = "Pinned unchanged Omarchy Catppuccin and Latte themes with a still wallpaper default";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
