#!/usr/bin/env bash
set -euo pipefail
# Source paths are explicit so this test always uses the pinned API, never the
# host distribution's unrelated wlroots version. No hardware or Nix build.
: "${WLROOTS_SOURCE:?set to pinned wlroots 0.20.2 source}"
: "${VGLITE_SOURCE:?set to pinned SDK buildroot-overlay/package/vg_lite}"
repo=$(cd "$(dirname "$0")/.." && pwd)
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
cc -DWLR_USE_UNSTABLE -Wall -Wextra -Werror -g -fsanitize=address,undefined -ffunction-sections -fdata-sections -Wl,--gc-sections \
  $(pkg-config --cflags pixman-1 wayland-server libdrm) \
  -I"$repo/nix/vglite-access" -I"$WLROOTS_SOURCE/include" -I"$VGLITE_SOURCE/inc" -I"$repo/nix/wlroots-vglite/include" \
  "$repo/tests/vglite/renderer-test.c" "$WLROOTS_SOURCE/render/pass.c" \
  "$WLROOTS_SOURCE/render/pixman/pass.c" "$WLROOTS_SOURCE/render/color.c" "$WLROOTS_SOURCE/util/box.c" \
  $(pkg-config --libs pixman-1 wayland-server) -lpthread -lm -o "$build/renderer-test"
"$build/renderer-test"
