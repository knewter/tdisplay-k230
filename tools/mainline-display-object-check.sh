#!/usr/bin/env bash
# Compile the opt-in DRM forward-port as external modules against a prepared
# v7.3-rc5 kernel dev output. This is an API/object check, not an in-tree
# kernel build. See docs/evidence/mainline-display-api-compile.md.
set -euo pipefail

repo=$(git rev-parse --show-toplevel)
dev=${MAINLINE_KERNEL_DEV:-/nix/store/0148bw9nb2cb9prgj6505kywvy2096bw-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev/lib/modules/7.3.0-rc5}
cc=${RISCV_CROSS_COMPILE:-/nix/store/4j2mwxqjvnyr6da0925sp0bm4jaj5r5i-riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0/bin/riscv64-unknown-linux-gnu-}
base=${MAINLINE_DISPLAY_CHECK_ROOT:-$repo/.scratch/mainline-display-api-check}

case "$base" in
  "$repo"/.scratch/*) ;;
  *) echo "check root must be inside this checkout's .scratch: $base" >&2; exit 2 ;;
esac
for path in "$dev/source/Makefile" "$dev/build/.config" "${cc}gcc"; do
  if [[ ! -e "$path" ]]; then
    echo "required prepared build input is missing: $path" >&2
    exit 2
  fi
done

mkdir -p "$base"
run=$(mktemp -d "$base/run.XXXXXX")
src=$dev/source
src=${MAINLINE_KERNEL_SRC:-$src}
build=$run/build
mods=$run/modules
cp -a "$dev/build" "$build"
chmod -R u+w "$build"
mkdir -p "$mods/canaan" "$mods/panel" "$mods/bridge"
cp "$repo"/nix/patches/mainline/drm/canaan_*.[ch] "$mods/canaan/"
cp "$repo/nix/patches/mainline/drm/panel-canaan-universal.c" "$mods/panel/"
cp "$repo/nix/patches/mainline/drm/lontium-lt9611-k230.c" "$mods/bridge/"
cat > "$mods/canaan/Makefile" <<'MAKE'
obj-m += canaan-drm.o
canaan-drm-y := canaan_drv.o canaan_vo.o canaan_crtc.o canaan_plane.o canaan_phy.o
obj-m += canaan_dsi.o
MAKE
cat > "$mods/panel/Makefile" <<'MAKE'
obj-m += panel-canaan-universal.o
MAKE
cat > "$mods/bridge/Makefile" <<'MAKE'
obj-m += lontium-lt9611-k230.o
MAKE

printf 'Prepared config:\n'
grep -E '^CONFIG_(DRM|DRM_CLIENT_SETUP|DRM_FBDEV_EMULATION)=' "$build/.config" || true
if [[ -f "$src/drivers/gpu/drm/canaan/Kconfig" ]]; then
  "$src/scripts/config" --file "$build/.config" \
    --enable DRM --enable DRM_CANAAN --enable DRM_CANAAN_DSI \
    --enable DRM_PANEL_CANAAN_UNIVERSAL --enable DRM_LONTIUM_LT9611 \
    --enable INPUT_TOUCHSCREEN --enable TOUCHSCREEN_GOODIX_BERLIN_I2C
  make -s -C "$src" O="$build" ARCH=riscv \
    CROSS_COMPILE="$cc" olddefconfig
  printf '\nResolved DRM config after olddefconfig:\n'
  grep -E '^CONFIG_(DRM|DRM_CANAAN|DRM_CANAAN_DSI|DRM_PANEL_CANAAN_UNIVERSAL|DRM_LONTIUM_LT9611|DRM_CLIENT_SETUP|DRM_FBDEV_EMULATION|DRM_MIPI_DSI|DRM_DISPLAY_HELPER|DRM_BRIDGE_CONNECTOR|INPUT_TOUCHSCREEN|TOUCHSCREEN_GOODIX_BERLIN_I2C|TOUCHSCREEN_GOODIX_BERLIN_CORE)=' "$build/.config"
  for symbol in DRM DRM_CANAAN DRM_CANAAN_DSI DRM_PANEL_CANAAN_UNIVERSAL \
    DRM_LONTIUM_LT9611 DRM_CLIENT_SETUP DRM_FBDEV_EMULATION DRM_MIPI_DSI \
    DRM_DISPLAY_HELPER DRM_BRIDGE_CONNECTOR INPUT_TOUCHSCREEN TOUCHSCREEN_GOODIX_BERLIN_I2C \
    TOUCHSCREEN_GOODIX_BERLIN_CORE; do
    grep -q "^CONFIG_${symbol}=y$" "$build/.config"
  done
fi
for part in canaan panel bridge; do
  printf '\n== %s ==\n' "$part"
  make -s -C "$src" O="$build" M="$mods/$part" ARCH=riscv \
    CROSS_COMPILE="$cc" KBUILD_MODPOST_WARN=1 modules
done
printf '\nBuilt external module files:\n'
find "$mods" -maxdepth 2 -name '*.ko' -printf '%P\n' | sort
