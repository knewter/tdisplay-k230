#!/usr/bin/env bash
set -euo pipefail
: "${WLROOTS_SOURCE:?set to pinned wlroots 0.20.2 source}"
repo=$(cd "$(dirname "$0")/.." && pwd)
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
mkdir -p "$build/render/allocator"
cp "$WLROOTS_SOURCE/render/allocator/drm_dumb.c" "$build/render/allocator/"
chmod u+w "$build/render/allocator/drm_dumb.c"
patch -s -d "$build" -p1 -i "$repo/nix/patches/wlroots-vglite-dumb-stride.patch"
cc -DWLR_USE_UNSTABLE -Wall -Wextra -Werror -Wno-unused-parameter -g -fsanitize=address,undefined \
  -ffunction-sections -fdata-sections -Wl,--gc-sections \
  $(pkg-config --cflags wayland-server libdrm pixman-1) \
  -I"$build/render/allocator" -I"$WLROOTS_SOURCE/include" \
  "$repo/tests/vglite/dumb-stride-test.c" $(pkg-config --libs wayland-server) -o "$build/test"
"$build/test"
