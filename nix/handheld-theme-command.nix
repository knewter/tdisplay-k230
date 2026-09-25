{ stdenvNoCC, makeWrapper, python3, omarchyThemeTools, themeDefault, lib, procps
, coherentShell ? false, rustShellTool ? null }:

let
  # Precomputing a prepared generation's panel-sized wallpaper decode only
  # matters where the Rust shell's receiver decodes one at all
  # (background_decode.rs); the non-coherent-shell session has no such
  # receiver to benefit. Guarded exactly like the --rust-socket/--deck-socket
  # flags below, which the same feature flag gates for the same reason.
  wallpaperCacheFlag =
    lib.optionalString (coherentShell && rustShellTool != null)
      ''--add-flags "--wallpaper-cache-tool ${rustShellTool}/bin/k230-shell-rust"'';
in

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
    install -m 0644 ${../tools/theme_preferences.py} "$out/libexec/handheld-theme/theme_preferences.py"
    install -m 0644 ${../tools/theme_tokens.py} "$out/libexec/handheld-theme/theme_tokens.py"
    install -m 0644 ${../tools/theme_catalog.py} "$out/libexec/handheld-theme/theme_catalog.py"
    install -m 0644 ${../tools/theme_client.py} "$out/libexec/handheld-theme/theme_client.py"
    install -m 0644 ${../tools/theme_helperd.py} "$out/libexec/handheld-theme/theme_helperd.py"
    install -m 0644 ${../tools/app_appearance.py} "$out/libexec/handheld-theme/app_appearance.py"
    install -m 0644 ${../tools/keyboard_appearance.py} "$out/libexec/handheld-theme/keyboard_appearance.py"
    install -m 0644 ${../tools/foot_color_session.py} "$out/libexec/handheld-theme/foot_color_session.py"
    install -m 0644 ${../tools/omarchy-theme-set} "$out/libexec/handheld-theme/omarchy-theme-set"
    makeWrapper ${python3}/bin/python3 "$out/bin/omarchy-theme-set" \
      --add-flags "$out/libexec/handheld-theme/omarchy-theme-set" \
      --add-flags "--tools ${omarchyThemeTools}" \
      --add-flags "--builtins ${themeDefault}/share/omarchy/themes" \
      --add-flags "--pkill ${procps}/bin/pkill" ${lib.optionalString coherentShell ''--add-flags "--rust-socket /run/shell/k230-shell-rust-appearance.sock --deck-socket /run/shell/k230-card-appearance.sock"''} \
      ${wallpaperCacheFlag}
    # `theme_client.py` is argv-compatible with `theme_catalog.py` and only
    # ever takes the fast path when `theme-helper.service` (nix/shell.nix,
    # `tools/theme_helperd.py`) is actually up; a missing/refused/slow
    # socket falls straight back to the exact behaviour `theme_catalog.py`
    # had before this daemon existed. See
    # docs/evidence/omarchy-themes/theme-swap-jank/README.md.
    makeWrapper ${python3}/bin/python3 "$out/bin/k230-theme" \
      --add-flags "$out/libexec/handheld-theme/theme_client.py" \
      --add-flags "--tools ${omarchyThemeTools}" \
      --add-flags "--builtins ${themeDefault}/share/omarchy/themes" \
      --add-flags "--pkill ${procps}/bin/pkill" ${lib.optionalString coherentShell ''--add-flags "--rust-socket /run/shell/k230-shell-rust-appearance.sock --deck-socket /run/shell/k230-card-appearance.sock"''} \
      ${wallpaperCacheFlag}
    # `theme-helper.service` (nix/shell.nix) is the only intended caller.
    # Its own fixed flags (state-root, sockets, wallpaper-cache-tool) are
    # supplied there, not baked in here, because it needs the *shell*
    # user's home for `--state-root`/`--keyboard-runtime-dir`, which this
    # derivation (built once, for any user) cannot know.
    makeWrapper ${python3}/bin/python3 "$out/bin/k230-theme-helperd" \
      --add-flags "$out/libexec/handheld-theme/theme_helperd.py" \
      --add-flags "--tools ${omarchyThemeTools}" \
      --add-flags "--builtins ${themeDefault}/share/omarchy/themes" \
      --add-flags "--pkill ${procps}/bin/pkill" ${lib.optionalString coherentShell ''--add-flags "--rust-socket /run/shell/k230-shell-rust-appearance.sock --deck-socket /run/shell/k230-card-appearance.sock"''} \
      ${wallpaperCacheFlag}
    makeWrapper ${python3}/bin/python3 "$out/bin/k230-app-appearance" \
      --add-flags "$out/libexec/handheld-theme/app_appearance.py"
    makeWrapper ${python3}/bin/python3 "$out/bin/k230-foot-session" \
      --add-flags "$out/libexec/handheld-theme/foot_color_session.py"
    runHook postInstall
  '';
}
