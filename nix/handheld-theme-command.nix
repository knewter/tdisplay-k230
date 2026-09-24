{ stdenvNoCC, makeWrapper, python3, omarchyThemeTools, themeDefault }:

stdenvNoCC.mkDerivation {
  pname = "handheld-theme-command";
  version = "0.1";
  dontUnpack = true;
  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/libexec/handheld-theme" "$out/bin"
    install -m 0644 ${../tools/theme_activate.py} "$out/libexec/handheld-theme/theme_activate.py"
    install -m 0644 ${../tools/theme_sources.py} "$out/libexec/handheld-theme/theme_sources.py"
    install -m 0644 ${../tools/theme_transaction.py} "$out/libexec/handheld-theme/theme_transaction.py"
    install -m 0644 ${../tools/theme_tokens.py} "$out/libexec/handheld-theme/theme_tokens.py"
    install -m 0644 ${../tools/omarchy-theme-set} "$out/libexec/handheld-theme/omarchy-theme-set"
    makeWrapper ${python3}/bin/python3 "$out/bin/omarchy-theme-set" \
      --add-flags "$out/libexec/handheld-theme/omarchy-theme-set" \
      --add-flags "--tools ${omarchyThemeTools}" \
      --add-flags "--builtins ${themeDefault}/share/omarchy/themes"
    runHook postInstall
  '';
}
