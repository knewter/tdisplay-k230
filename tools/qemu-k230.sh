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

# CAPTURE=<seconds> runs non-interactively and stops after that long, so a
# boot can be recorded into docs/evidence/ without hanging a terminal. With
# -nographic and no block device there is nothing to shut the guest down
# from, so the timeout is the exit path.
CAPTURE="${CAPTURE:-}"

echo "Building kernel and ramdisk..." >&2
KERNEL=$(nix build --no-link --print-out-paths .#packages.x86_64-linux.qemu-kernel)
INITRD=$(nix build --no-link --print-out-paths .#packages.x86_64-linux.qemu-initrd)
TOPLEVEL=$(nix build --no-link --print-out-paths .#nixosConfigurations.k230-qemu.config.system.build.toplevel)

# The k230 machine generates no FDT of its own -- "This machine doesn't have
# an FDT" -- so a device tree must be supplied. Mainline carries initial K230
# support under arch/riscv/boot/dts/canaan/, so the kernel build should ship
# one.
DTB="${DTB:-}"
if [ -z "$DTB" ]; then
  DTB=$(find "$KERNEL/dtbs" -name 'k230*.dtb' 2>/dev/null | sort | head -1 || true)
fi
if [ -z "$DTB" ] || [ ! -f "$DTB" ]; then
  echo "ERROR: no K230 device tree found under $KERNEL/dtbs" >&2
  echo "QEMU's k230 machine generates no FDT, so one must be supplied." >&2
  echo "Either enable Canaan DTBs in the kernel, or pass DTB=/path/to.dtb" >&2
  find "$KERNEL/dtbs" -maxdepth 2 -type d 2>/dev/null | head -10 >&2
  exit 1
fi

KIMG="$KERNEL/Image"
[ -f "$KIMG" ] || KIMG=$(find "$KERNEL" -maxdepth 2 -name 'Image*' -o -maxdepth 2 -name 'vmlinu*' | head -1)
IIMG="$INITRD/initrd"
[ -f "$IIMG" ] || IIMG=$(find "$INITRD" -maxdepth 2 -type f | head -1)

echo "kernel:   $KIMG" >&2
echo "dtb:      $DTB" >&2
echo "initrd:   $IIMG" >&2
echo "toplevel: $TOPLEVEL" >&2
echo >&2

QEMU=(qemu-system-riscv64 \
  -machine k230 \
  -m "$MEM" \
  -nographic \
  -kernel "$KIMG" \
  -dtb "$DTB" \
  -initrd "$IIMG" \
  -append "console=ttyS0,115200n8 earlycon=sbi init=$TOPLEVEL/init loglevel=7" \
  "$@")

if [ -n "$CAPTURE" ]; then
  # 124 from `timeout` means it ran for the whole window, which for a boot
  # capture is success, not failure.
  timeout --foreground "$CAPTURE" "${QEMU[@]}" < /dev/null
  rc=$?
  [ "$rc" -eq 124 ] && exit 0
  exit "$rc"
fi

exec "${QEMU[@]}"
