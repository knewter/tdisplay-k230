#!/usr/bin/env bash
# Boot the k230-qemu system under QEMU.
#
# This proves the closure builds and STARTS. It is NOT evidence about the
# board. See .skills/k230-spec-change/SKILL.md.
#
# MACHINE=virt (the default) is used deliberately, not as a shortcut:
#
#   Mainline Linux has no bootable K230 platform yet. 6.18.52 carries
#   pinctrl-k230.c and reset-k230.c, but there is NO K230 device tree
#   (arch/riscv/boot/dts/canaan/ is K210-only) and no SOC_CANAAN_K230 --
#   only SOC_CANAAN_K210, which is `depends on !MMU`. So a stock nixpkgs
#   kernel cannot boot QEMU's k230 machine at all.
#
#   What this change needs to prove is that the closure builds and reaches
#   a prompt, which is machine-independent. `virt` answers that today.
#
#   MACHINE=k230 additionally needs the Xuantie kernel built with
#   CONFIG_ERRATA_THEAD_PBMT=n (that errata IS the T-Head MAEE page-table
#   extension QEMU does not implement). That kernel arrives with
#   the-screen-comes-up-under-linux, and this script will work with it then.
set -euo pipefail
cd "$(dirname "$0")/.."

MACHINE="${MACHINE:-virt}"
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

# The k230 machine generates no FDT of its own -- dumpdtb answers "This
# machine doesn't have an FDT" -- so it needs one supplied. `virt` builds
# its own, so no -dtb is required there.
DTB="${DTB:-}"
if [ "$MACHINE" = "k230" ] && [ -z "$DTB" ]; then
  DTB=$(find "$KERNEL/dtbs" -name 'k230*.dtb' 2>/dev/null | sort | head -1 || true)
  if [ -z "$DTB" ] || [ ! -f "$DTB" ]; then
    echo "ERROR: MACHINE=k230 needs a K230 device tree and none was found." >&2
    echo "Mainline 6.x ships no K230 DTS (canaan/ is K210-only), so a stock" >&2
    echo "kernel cannot boot this machine. Use the Xuantie kernel with" >&2
    echo "CONFIG_ERRATA_THEAD_PBMT=n, or pass DTB=/path/to.dtb." >&2
    exit 1
  fi
fi

KIMG="$KERNEL/Image"
[ -f "$KIMG" ] || KIMG=$(find "$KERNEL" -maxdepth 2 -name 'Image*' -o -maxdepth 2 -name 'vmlinu*' | head -1)
IIMG="$INITRD/initrd"
[ -f "$IIMG" ] || IIMG=$(find "$INITRD" -maxdepth 2 -type f | head -1)

echo "machine:  $MACHINE" >&2
echo "kernel:   $KIMG" >&2
[ -n "$DTB" ] && echo "dtb:      $DTB" >&2
echo "initrd:   $IIMG" >&2
echo "toplevel: $TOPLEVEL" >&2
echo >&2

QEMU=(qemu-system-riscv64 \
  -machine "$MACHINE" \
  -m "$MEM" \
  -nographic \
  -kernel "$KIMG" \
  ${DTB:+-dtb "$DTB"} \
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
