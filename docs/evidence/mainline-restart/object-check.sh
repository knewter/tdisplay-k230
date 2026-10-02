#!/usr/bin/env bash
# Host-only reset driver API/object check; no complete kernel link or MMIO.
set -euo pipefail
repo=$(git rev-parse --show-toplevel)
src=${MAINLINE_RESTART_SRC:-$(nix build .#kernelMainlineDrm.src --no-link --print-out-paths --max-jobs 1 --cores 4)}
base=$repo/.scratch/mainline-restart-object
mkdir -p "$base"
run=$(mktemp -d "$base/run.XXXXXX")
build=$run/build
module=$run/module
mkdir -p "$build" "$module"
printf 'UTC: %s\nSource: %s\n' "$(date -u +%FT%TZ)" "$src"
sha256sum "$src/drivers/reset/reset-k230.c" "$src/include/linux/reboot.h"
clang --version | head -1
# Prepare real headers from the exact pinned source with the host LLVM tools.
# The full Nix GCC/config/link proof is a separate task.
make -s -C "$src" O="$build" ARCH=riscv LLVM=1 defconfig
"$src/scripts/config" --file "$build/.config" --disable GCC_PLUGINS \
  --disable DEBUG_INFO --disable DEBUG_INFO_BTF --disable RUST \
  --enable RESET_CONTROLLER --enable RESET_K230
make -s -C "$src" O="$build" ARCH=riscv LLVM=1 olddefconfig prepare
grep -E '^CONFIG_(64BIT|RISCV|OF|RESET_CONTROLLER|RESET_K230)=' "$build/.config"
cp "$src/drivers/reset/reset-k230.c" "$module/"
printf 'obj-m += reset-k230.o\n' > "$module/Makefile"
make -C "$src" O="$build" M="$module" ARCH=riscv LLVM=1 W=1 reset-k230.o
file "$module/reset-k230.o"
llvm-nm "$module/reset-k230.o" | rg 'k230_rst_restart|devm_register_sys_off_handler|devm_ioremap'
sha256sum "$module/reset-k230.o" "$build/.config"
printf 'Object check passed; this did not link a complete kernel or execute restart.\n'
