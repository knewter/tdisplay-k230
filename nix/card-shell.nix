{ lib, symlinkJoin, writeShellScriptBin, sway, swayUnwrapped, dbus, coreutils, bash, librsvg, wlroots_0_20, pixman, quarterTurnTrial ? false }:
let
  # Only the compositor composites whole surfaces every frame, so only it
  # gets the exact OVER shortcuts; the rest of the closure keeps the shared
  # Pixman and is not rebuilt. sway names libpixman directly, so its own
  # RUNPATH copy is the one loaded and cairo's request reuses it by soname.
  compositorPixman = pixman.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ./patches/pixman-rvv-over-0565-exact-shortcuts.patch ];
  });
  roundedWlroots = (wlroots_0_20.override { pixman = compositorPixman; }).overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ./patches/wlroots-k230-rounded-clip.patch ./patches/wlroots-k230-opaque-interior.patch ]
      ++ lib.optionals quarterTurnTrial [
        ./patches/wlroots-k230-quarter-turn.patch
        ./patches/wlroots-k230-output-turn.patch
        ./patches/wlroots-k230-draw-formats.patch
        ./patches/wlroots-k230-retained-output.patch
      ];
    postPatch = (old.postPatch or "") + ''
      cp ${./card-shell/rounded-clip.h} include/render/k230_rounded_clip.h
      cp ${./card-shell/rgb565-blit.h} include/render/rgb565-blit.h
      cp ${./card-shell/rgb565-pixels.h} include/render/rgb565-pixels.h
    '' + lib.optionalString quarterTurnTrial ''
      cp ${./card-shell/quarter-turn.h} include/render/k230_quarter_turn.h
      cp ${./card-shell/output-cache.h} include/render/k230_output_cache.h
    '';
  });
  unwrapped = (swayUnwrapped.override {
    enableXWayland = false;
    wlroots_0_20 = roundedWlroots;
  }).overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ./patches/sway-k230-card-shell.patch ./patches/sway-k230-trackpad-ipc.patch ./patches/sway-k230-text-input-late-enter.patch ];
    # Card-header icon resolution (nix/card-shell/icon.c) decodes SVG icons
    # via librsvg directly, the same real-icon path the Rust drawer already
    # uses (nix/rust-shell-client/default.nix's own librsvg buildInput) --
    # a real installed theme resolves most app icons to SVG, not PNG, per
    # board evidence (docs/evidence/card-shell/webos-fan-switcher/).
    # compositorPixman first: it must precede cairo's propagated Pixman in
    # sway's RUNPATH, which is what resolves sway's own libpixman request.
    buildInputs = [ compositorPixman ] ++ (old.buildInputs or [ ]) ++ [ librsvg ];
    postPatch = (old.postPatch or "") + ''
      cp ${./card-shell/adapter.c} sway/card_shell.c
      cp ${./card-shell/appearance.c} sway/card_shell_appearance.c
      cp ${./card-shell/appearance.h} include/sway/card_shell_appearance.h
      cp ${./card-shell/test-input.c} sway/card_shell_test_input.c
      cp ${./card-shell/test-input.h} include/sway/card_shell_test_input.h
      cp ${./card-shell/card-shell.h} include/sway/card_shell.h
      cp ${./card-shell/route.c} sway/card_shell_route.c
      cp ${./card-shell/route.h} include/sway/card_shell_route.h
      cp ${./card-shell/telemetry.c} sway/card_shell_telemetry.c
      cp ${./card-shell/telemetry.h} include/sway/card_shell_telemetry.h
      cp ${./card-shell/wake-gate.h} include/sway/card_shell_wake_gate.h
      cp ${./card-shell/render.c} sway/card_shell_render.c
      cp ${./card-shell/render.h} include/sway/card_shell_render.h
      cp ${./card-shell/icon.c} sway/card_shell_icon.c
      cp ${./card-shell/icon.h} include/sway/card_shell_icon.h
      cp ${./card-shell/scaled-cache.c} sway/card_shell_scaled_cache.c
      cp ${./card-shell/scaled-cache.h} include/sway/card_shell_scaled_cache.h
      cp ${./card-shell/opaque-interior.h} include/sway/card_shell_opaque_interior.h
      cp ${./card-shell/label-ink.h} include/sway/card_shell_label_ink.h
      cp ${./card-shell/rgb565-pixels.h} include/sway/rgb565-pixels.h
      cp ${./card-shell-policy/card-shell-policy.c} sway/card-shell-policy.c
      cp ${./card-shell-policy/card-shell-policy.h} include/sway/card-shell-policy.h
      cp ${./card-keyboard-policy/keyboard-gesture.c} sway/card-keyboard-gesture.c
      cp ${./card-keyboard-policy/keyboard-gesture.h} include/sway/card-keyboard-gesture.h
      substituteInPlace sway/card-shell-policy.c \
        --replace-fail '#include "card-shell-policy.h"' '#include "sway/card-shell-policy.h"'
      substituteInPlace sway/card-keyboard-gesture.c \
        --replace-fail '#include "keyboard-gesture.h"' '#include "sway/card-keyboard-gesture.h"'
      # An application inhibitor (mpv's) counts while Sway thinks its view
      # is visible; the card shell hides cards at Home without telling Sway.
      substituteInPlace sway/desktop/idle_inhibit_v1.c \
        --replace-fail '#include "sway/desktop/idle_inhibit_v1.h"' '#include "sway/desktop/idle_inhibit_v1.h"
#include "sway/card_shell.h"' \
        --replace-fail 'return view && view->container && view_is_visible(view);' \
          'return view && view->container && view_is_visible(view) && !card_shell_view_hidden(view);'
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
  name = if quarterTurnTrial then "k230-card-shell-hdmi-trial" else "k230-card-shell";
  paths = [ compositor wrapper ];
  meta = { description = "Opt-in Sway adapter for live application cards";
    platforms = [ "riscv64-linux" ]; license = lib.licenses.mit; };
}
