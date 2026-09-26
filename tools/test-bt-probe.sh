#!/usr/bin/env bash
# Host-side fixture test for tools/bt-probe.sh, same pattern as
# tools/test-board-inventory-probe.sh: build a synthetic /proc, /sys and
# /dev tree, run the probe against it via BT_PROBE_ROOT, and assert on
# specific output lines. The command-based sections (rfkill, hciconfig,
# btmgmt, dmesg) are exercised only for their "tool not present" fallback
# here: PATH is pinned to a minimal directory holding just the coreutils
# the probe needs, deliberately excluding those four tools, so this test
# never depends on -- or touches -- whatever real hardware happens to be
# attached to the host it runs on.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT

# --- synthetic /sys/bus/sdio/devices: one function only, matching this
# board's already-captured wifi-preflight.txt (vendor 024c, device f179,
# one function, Wi-Fi-only) ---
mkdir -p "$fixture/sys/bus/sdio/devices/mmc0:0001:1"
sd="$fixture/sys/bus/sdio/devices/mmc0:0001:1"
printf '0x024c\n' > "$sd/vendor"
printf '0xf179\n' > "$sd/device"
printf 'sdio:c07v024CdF179\n' > "$sd/modalias"
mkdir -p "$fixture/sys/module/8189fs"
ln -s ../../../module/8189fs "$sd/driver"

# --- synthetic ttyS: one plain UART, no of_node (nothing BT-shaped) ---
mkdir -p "$fixture/sys/class/tty/ttyS0/device"

# --- synthetic USB: only the known r8152 USB LAN adapter, no BT dongle ---
mkdir -p "$fixture/sys/bus/usb/devices/1-1"
printf '0bda\n' > "$fixture/sys/bus/usb/devices/1-1/idVendor"
printf '8152\n' > "$fixture/sys/bus/usb/devices/1-1/idProduct"
printf 'USB 10/100 LAN\n' > "$fixture/sys/bus/usb/devices/1-1/product"

# --- minimal PATH: only the coreutils the probe uses, never
# rfkill/hciconfig/btmgmt/dmesg ---
bin="$fixture/bin"
mkdir -p "$bin"
for tool in basename dirname tr readlink date; do
  src=$(command -v "$tool")
  ln -s "$src" "$bin/$tool"
done

sh_bin=$(command -v sh)
out=$(PATH="$bin" BT_PROBE_ROOT="$fixture" "$sh_bin" "$repo/tools/bt-probe.sh")

grep -Fqx 'function=mmc0:0001:1 vendor=0x024c device=0xf179 modalias=sdio:c07v024CdF179 driver=8189fs' <<<"$out"
grep -Fqx 'tty=ttyS0 of_node=(none) compatible=(none)' <<<"$out"
grep -Fqx '<rfkill-unavailable>' <<<"$out"
grep -Fqx '<hciconfig-unavailable>' <<<"$out"
grep -Fqx '<btmgmt-unavailable>' <<<"$out"
grep -Fqx '<dmesg-unavailable>' <<<"$out"
grep -Fqx 'dev=1-1 id=0bda:8152 product=USB 10/100 LAN' <<<"$out"

printf '%s\n' 'bt-probe fixture: PASS'
