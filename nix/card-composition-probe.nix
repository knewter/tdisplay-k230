{ lib, symlinkJoin, writeShellScriptBin, sway, swayUnwrapped }:

let
  patchedUnwrapped = (swayUnwrapped.override { enableXWayland = false; }).overrideAttrs (old: {
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
card-composition-probe is an opt-in pinned-Sway route checkpoint.
It starts no compositor and opens no DRM node by itself.
`--sway [sway options]` runs the patched Sway with the route marker enabled.
The marker is not evidence of live scaling, two-app composition, touch, focus,
or dismissal; those remain board-only gates.
EOF
        ;;
      --sway)
        shift
        export SWAY_K230_CARD_COMPOSITION_PROBE=1
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
  paths = [ patchedSway probe ];
  meta = {
    description = "Opt-in source-built Sway route checkpoint for card-composition investigation";
    platforms = [ "riscv64-linux" ];
    license = lib.licenses.mit;
  };
}
