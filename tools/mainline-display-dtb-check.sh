#!/usr/bin/env bash
# Preprocess, compile, and round-trip the opt-in mainline DRM board DTB.
# This host-only check does not prove board clocking, power, pinmux, or probe.
set -euo pipefail

repo=$(git rev-parse --show-toplevel)
src=${MAINLINE_KERNEL_SRC:-/nix/store/302cz10wl1g77aspr3gc2hm999rr5701-linux-mainline-k230-drm-src}
base=${MAINLINE_DISPLAY_DTB_CHECK_ROOT:-$repo/.scratch/mainline-display-dtb-check}
cc=${HOST_CC:-gcc}
dtc_bin=${DTC:-dtc}

case "$base" in
  "$repo"/.scratch/*) ;;
  *) echo "check root must be inside this checkout's .scratch: $base" >&2; exit 2 ;;
esac
if [[ ! -f "$src/arch/riscv/boot/dts/canaan/k230.dtsi" ]]; then
  echo "pinned mainline DTS source is missing: $src" >&2
  exit 2
fi
mkdir -p "$base"
work=$(mktemp -d "$base/run.XXXXXX")
dts_dir=$src/arch/riscv/boot/dts/canaan
cp --no-preserve=mode "$dts_dir"/*.dtsi "$dts_dir"/*.h "$work/"
cp "$repo/nix/dts/k230-tdisplay-mainline.dts" "$work/"
cp "$repo/nix/dts/k230-tdisplay-mainline-drm.dts" "$work/"
cp "$repo/nix/dts/display-rm69a10-568x1232.dtsi" "$work/"

"$cc" -E -nostdinc -I "$src/scripts/dtc/include-prefixes" \
  -undef -D__DTS__ -x assembler-with-cpp \
  -o "$work/k230-tdisplay-mainline-drm.dts.pre" \
  "$work/k230-tdisplay-mainline-drm.dts"
"$dtc_bin" -I dts -O dtb -b 0 -@ -i "$work" \
  -i "$src/scripts/dtc/include-prefixes" \
  -o "$work/k230-tdisplay-mainline-drm.dtb" \
  "$work/k230-tdisplay-mainline-drm.dts.pre"
"$dtc_bin" -I dtb -O dts "$work/k230-tdisplay-mainline-drm.dtb" \
  > "$work/roundtrip.dts"
for compatible in 'snps,designware-i2c' 'goodix,gt9895' \
  'canaan,display-subsystem' 'canaan,k230-vo' \
  'canaan,k230-mipi-dsi' 'canaan,universal'; do
  grep -Fq "$compatible" "$work/roundtrip.dts"
done
"$dtc_bin" -I dtb -O dts "$work/k230-tdisplay-mainline-drm.dtb" \
  | grep -n -E 'designware-i2c|goodix,gt9895|display-subsystem|k230-vo|k230-mipi-dsi|canaan,universal'
file "$work/k230-tdisplay-mainline-drm.dtb"
printf 'DTB=%s\n' "$work/k230-tdisplay-mainline-drm.dtb"
