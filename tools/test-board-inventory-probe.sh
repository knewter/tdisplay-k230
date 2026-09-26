#!/usr/bin/env bash
# Host-side fixture test for tools/board-inventory-probe.sh, same pattern
# as tools/test-second-core-readiness.sh: build a synthetic /proc and
# /sys tree, run the probe against it via BOARD_INVENTORY_ROOT, and
# assert on specific output lines.
#
# The command-based sections (i2cdetect, lsusb, dmesg, lsmod) are
# exercised only for their "tool not present" fallback here: PATH is
# pinned to a minimal directory holding just the coreutils the probe
# needs (find, sort, tr, sed, ls, date), deliberately excluding those
# four tools, so this test never depends on -- or touches -- whatever
# real hardware happens to be attached to the host it runs on.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT

# --- synthetic /proc/device-tree ---
mkdir -p "$fixture/proc/device-tree/soc/i2c@91409000"
mkdir -p "$fixture/proc/device-tree/soc/spi@91584000"
printf 'okay\0' > "$fixture/proc/device-tree/soc/i2c@91409000/status"
# spi@91584000 has no status file: probe must report "(default okay)".

# --- synthetic sysfs classes: some present, some absent ---
mkdir -p "$fixture/sys/class/power_supply/axp2101-battery"
mkdir -p "$fixture/sys/class/input"
# backlight, sound, video4linux, bluetooth, net, thermal, pwm, gpio: absent.

# --- synthetic /dev/i2c-* (i2cdetect is deliberately unavailable, so the
# probe's i2c section only needs to report the bus name, not a real scan) ---
mkdir -p "$fixture/dev" "$fixture/sys/class/i2c-dev/i2c-4"
: > "$fixture/dev/i2c-4"
printf '91409000.i2c\0' > "$fixture/sys/class/i2c-dev/i2c-4/name"

# --- minimal PATH: only the coreutils the probe uses, never
# i2cdetect/lsusb/dmesg/lsmod ---
bin="$fixture/bin"
mkdir -p "$bin"
for tool in find sort tr sed ls date; do
  src=$(command -v "$tool")
  ln -s "$src" "$bin/$tool"
done

sh_bin=$(command -v sh)
out=$(PATH="$bin" BOARD_INVENTORY_ROOT="$fixture" BOARD_INVENTORY_I2C_SKIP="6b" \
  "$sh_bin" "$repo/tools/board-inventory-probe.sh")

grep -Fqx 'node=/soc/i2c@91409000 status=okay' <<<"$out"
grep -Fqx 'node=/soc/spi@91584000 status=(default okay)' <<<"$out"
grep -Fqx 'class=power_supply: axp2101-battery ' <<<"$out"
grep -Fqx 'class=input: ' <<<"$out"
grep -Fqx 'class=backlight: <absent>' <<<"$out"
grep -Fqx 'bus=4 name=91409000.i2c' <<<"$out"
grep -Fqx 'bus=4 skip-extra=6b' <<<"$out"
grep -Fqx 'bus=4 <i2cdetect-unavailable>' <<<"$out"
grep -Fqx '<lsusb-unavailable>' <<<"$out"
grep -Fqx '<dmesg-unavailable>' <<<"$out"
grep -Fqx '<lsmod-unavailable>' <<<"$out"

printf '%s\n' 'board-inventory-probe fixture: PASS'
