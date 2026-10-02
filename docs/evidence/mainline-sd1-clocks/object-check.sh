#!/usr/bin/env bash
# Host-only exact-source GCC/header check; no full link or board operation.
set -euo pipefail
: "${MAINLINE_SD1_SRC:?exact patched source required}"
: "${MAINLINE_SD1_CONFIG:?matching candidate Nix config required}"
: "${MAINLINE_SD1_CROSS_COMPILE:?matching GCC cross prefix required}"
repo=$(git rev-parse --show-toplevel)
base=$repo/.scratch/sd1-clocks
mkdir -p "$base"
run=$(mktemp -d "$base/object.XXXXXX")
build=$run/build
module=$run/module
mkdir -p "$build" "$module"
flags=(ARCH=riscv CROSS_COMPILE="$MAINLINE_SD1_CROSS_COMPILE")
printf 'UTC: %s\nSource: %s\nNix config: %s\n' "$(date -u +%FT%TZ)" "$MAINLINE_SD1_SRC" "$MAINLINE_SD1_CONFIG"
"${MAINLINE_SD1_CROSS_COMPILE}gcc" --version | head -1
cp "$MAINLINE_SD1_CONFIG" "$build/.config"
chmod u+w "$build/.config"
"$MAINLINE_SD1_SRC/scripts/config" --file "$build/.config" --disable GCC_PLUGINS \
  --disable DEBUG_INFO --disable DEBUG_INFO_BTF --disable RUST
make -s -C "$MAINLINE_SD1_SRC" O="$build" "${flags[@]}" olddefconfig prepare
grep -E '^CONFIG_(RISCV|MMC|MMC_SDHCI|MMC_SDHCI_PLTFM|MMC_SDHCI_OF_DWCMSHC_KENDRYTE|PM_SLEEP)=' "$build/.config"
cp "$MAINLINE_SD1_SRC/drivers/mmc/host/sdhci-of-kendryte.c" "$module/"
cp "$MAINLINE_SD1_SRC/drivers/mmc/host/sdhci.h" "$MAINLINE_SD1_SRC/drivers/mmc/host/sdhci-pltfm.h" "$module/"
printf 'obj-m += sdhci-of-kendryte.o\n' > "$module/Makefile"
make -C "$MAINLINE_SD1_SRC" O="$build" M="$module" "${flags[@]}" W=1 sdhci-of-kendryte.o
file "$module/sdhci-of-kendryte.o"
llvm-nm "$module/sdhci-of-kendryte.o" | rg 'clk_bulk|clk_prepare_enable|clk_disable_unprepare|dwcmshc_(probe|remove|suspend|resume)'
sha256sum "$module/sdhci-of-kendryte.c" "$module/sdhci-of-kendryte.o" "$build/.config"
printf 'GCC object check passed; full kernel and physical ownership are separate gates.\n'
