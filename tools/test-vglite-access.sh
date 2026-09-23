#!/usr/bin/env bash
set -euo pipefail
: "${VGLITE_SOURCE:?set to pinned SDK buildroot-overlay/package/vg_lite}"
repo=$(cd "$(dirname "$0")/.." && pwd)
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
mkdir -p "$build/VGLiteKernel/linux"
cp "$VGLITE_SOURCE/VGLiteKernel/linux/vg_lite_ioctl.c" "$build/VGLiteKernel/linux/"
patch -s -d "$build" -p1 -i "$repo/nix/patches/vglite-broker-device.patch"
cc -Wall -Wextra -Werror -g -fsanitize=address,undefined \
  -I"$repo/nix/vglite-access" -I"$build/VGLiteKernel/linux" \
  -I"$VGLITE_SOURCE/inc" -I"$VGLITE_SOURCE/VGLiteKernel" -I"$VGLITE_SOURCE/VGLiteKernel/linux" \
  "$repo/tests/vglite/sdk-access-test.c" -pthread -o "$build/sdk-access-test"
"$build/sdk-access-test"
cc -Wall -Wextra -Werror -g -fsanitize=address,undefined \
  -I"$repo/nix/vglite-access" -I"$VGLITE_SOURCE/inc" \
  "$repo/tests/vglite/client-access-test.c" -pthread -o "$build/client-access-test"
"$build/client-access-test"
python3 "$repo/tests/vglite/test_broker.py"
