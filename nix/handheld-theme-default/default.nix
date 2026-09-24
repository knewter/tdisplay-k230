{ lib, stdenvNoCC }:

stdenvNoCC.mkDerivation {
  pname = "handheld-theme-default";
  version = "28ceaae7";
  src = ./.;
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    install -Dm644 catppuccin/colors.toml "$out/share/omarchy/themes/catppuccin/colors.toml"
    install -Dm644 catppuccin/icons.theme "$out/share/omarchy/themes/catppuccin/icons.theme"
    install -Dm644 default-report.json "$out/generations/ab1e1a1426b700555c85c3b9/report.json"
    install -Dm644 default-appearance.json "$out/generations/ab1e1a1426b700555c85c3b9/appearance.json"
    install -Dm644 LICENSE "$out/share/doc/handheld-theme-default/LICENSE"
    runHook postInstall
  '';
  meta = {
    description = "Pinned palette and icon selector subset of Omarchy Catppuccin";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
