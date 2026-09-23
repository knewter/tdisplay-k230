{ lib, symlinkJoin, writeShellScriptBin, sway, swayUnwrapped, callPackage, dbus }:

let
  client = callPackage ./card-composition-probe-client { };
  patchedUnwrapped = (swayUnwrapped.override { enableXWayland = false; }).overrideAttrs (old: {
    postPatch = (old.postPatch or "") + ''
      cp ${./card-composition-probe/card.c} sway/k230_card.c
      cp ${./card-composition-probe/card.h} include/sway/k230_card.h
      cp ${./card-composition-probe/model.h} include/sway/k230_card_model.h
    '';
    patches = (old.patches or [ ]) ++ [ ./patches/sway-k230-card-composition-probe.patch ];
  });
  patchedSway = sway.override {
    enableXWayland = false;
    sway-unwrapped = patchedUnwrapped;
  };
  probe = writeShellScriptBin "card-composition-probe" ''
    case "''${1:-}" in
      --describe)
        cat <<'EOF'
card-composition-probe is an opt-in pinned-Sway live-surface experiment.
It starts no compositor and opens no DRM node by itself.
`--sway [sway options]` runs the patched Sway with the two-app experiment enabled.
Allowlisted apps: k230.card.one and k230.card.two, on one active workspace.
Touch the bottom 48 logical pixels to enter; tap a card to expand.
Drag a card upward by 120 pixels to request close; a still-mapped app after
1500ms is classified close-refused, not successful dismissal.
Physical touch, panel presentation and normal-shell restoration remain
board-only evidence gates.
EOF
        ;;
      --sway)
        shift
        # Transient board sessions do not inherit shell.service's package PATH.
        # The wrapped Sway invokes dbus-run-session, which finds its daemon here.
        export PATH=${lib.makeBinPath [ dbus ]}:"$PATH"
        export SWAY_K230_CARD_COMPOSITION_PROBE=1
        export WLR_RENDERER=pixman
        exec ${patchedSway}/bin/sway "$@"
        ;;
      *)
        echo "usage: card-composition-probe --describe | --sway [sway options]" >&2
        exit 2
        ;;
    esac
  '';
in
symlinkJoin {
  name = "k230-card-composition-probe";
  paths = [ patchedSway probe client ];
  meta = {
    description = "Opt-in source-built Sway route checkpoint for card-composition investigation";
    platforms = [ "riscv64-linux" ];
    license = lib.licenses.mit;
  };
}
