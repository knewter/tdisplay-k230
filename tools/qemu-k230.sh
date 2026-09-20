#!/usr/bin/env bash
# Boot the k230-qemu system under QEMU's `k230` machine.
#
# This proves the closure builds and starts. It is NOT evidence about the
# board: QEMU's k230 machine models no panel, no touch controller, no radio,
# no SD card and no vendored boot chain. See .skills/k230-spec-change/SKILL.md.
set -euo pipefail
cd "$(dirname "$0")/.."

MEM="${MEM:-2G}"   # more than the board's 1 GiB: the whole system is in the
                   # initrd here, which hardware does not do.

echo "Building kernel and ramdisk..." >&2
KERNEL=$(nix build --no-link --print-out-paths .#packages.x86_64-linux.qemu-kernel)
INITRD=$(nix build --no-link --print-out-paths .#packages.x86_64-linux.qemu-initrd)
TOPLEVEL=$(nix build --no-link --print-out-paths .#nixosConfigurations.k230-qemu.config.system.build.toplevel)

KIMG="$KERNEL/Image"
[ -f "$KIMG" ] || KIMG=$(find "$KERNEL" -maxdepth 2 -name 'Image*' -o -maxdepth 2 -name 'vmlinu*' | head -1)
IIMG="$INITRD/initrd"
[ -f "$IIMG" ] || IIMG=$(find "$INITRD" -maxdepth 2 -type f | head -1)

echo "kernel:   $KIMG" >&2
echo "initrd:   $IIMG" >&2
echo "toplevel: $TOPLEVEL" >&2
echo >&2

exec qemu-system-riscv64 \
  -machine k230 \
  -m "$MEM" \
  -nographic \
  -kernel "$KIMG" \
  -initrd "$IIMG" \
  -append "console=ttyS0,115200n8 earlycon=sbi init=$TOPLEVEL/init loglevel=7" \
  "$@"
