{ lib, symlinkJoin, writeShellScriptBin, sway, swayUnwrapped, dbus, coreutils, bash }:
let
  unwrapped = (swayUnwrapped.override { enableXWayland = false; }).overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ./patches/sway-k230-card-shell.patch ];
    postPatch = (old.postPatch or "") + ''
      cp ${./card-shell/adapter.c} sway/card_shell.c
      cp ${./card-shell/test-input.c} sway/card_shell_test_input.c
      cp ${./card-shell/test-input.h} include/sway/card_shell_test_input.h
      cp ${./card-shell/card-shell.h} include/sway/card_shell.h
      cp ${./card-shell/route.c} sway/card_shell_route.c
      cp ${./card-shell/route.h} include/sway/card_shell_route.h
      cp ${./card-shell/telemetry.c} sway/card_shell_telemetry.c
      cp ${./card-shell/telemetry.h} include/sway/card_shell_telemetry.h
      cp ${./card-shell/render.c} sway/card_shell_render.c
      cp ${./card-shell/render.h} include/sway/card_shell_render.h
      cp ${./card-shell/scaled-cache.c} sway/card_shell_scaled_cache.c
      cp ${./card-shell/scaled-cache.h} include/sway/card_shell_scaled_cache.h
      cp ${./card-shell-policy/card-shell-policy.c} sway/card-shell-policy.c
      cp ${./card-shell-policy/card-shell-policy.h} include/sway/card-shell-policy.h
      substituteInPlace sway/card-shell-policy.c \
        --replace-fail '#include "card-shell-policy.h"' '#include "sway/card-shell-policy.h"'
    '';
  });
  compositor = sway.override { enableXWayland = false; sway-unwrapped = unwrapped; };
  wrapper = writeShellScriptBin "card-shell" ''
    export PATH=${lib.makeBinPath [ dbus coreutils bash ]}:"$PATH"
    case "''${1:-}" in
      --sway)
        shift
        export SWAY_K230_CARD_SHELL=1 WLR_RENDERER=pixman
        exec ${compositor}/bin/sway "$@"
        ;;
      --enter) exec ${compositor}/bin/swaymsg card_shell enter ;;
      --back) exec ${compositor}/bin/swaymsg card_shell back ;;
      --describe)
        cat <<'DESCRIPTION'
Opt-in source-built Sway live app cards; default shell is unchanged.
Run --sway with the normal Sway config in a reserved, single-owner session.
Swipe upward from the lower content edge, or use the persistent Cards button.
Previous/Next, tap to expand, Close and Back have visible button routes.
Private marks or session-excluded app IDs receive non-live placeholders.
Physical acceptance and default-image integration remain separate gates.
DESCRIPTION
        ;;
      *) echo 'usage: card-shell --sway [options] | --enter | --back | --describe' >&2; exit 2 ;;
    esac
  '';
in symlinkJoin {
  name = "k230-card-shell";
  paths = [ compositor wrapper ];
  meta = { description = "Opt-in Sway adapter for live application cards";
    platforms = [ "riscv64-linux" ]; license = lib.licenses.mit; };
}
