#!/usr/bin/env sh
# Read-only board hardware-inventory probe for the T-Display-K230.
#
# Companion to docs/research/board-capability-inventory.md: collects what
# the running Linux kernel currently sees for every peripheral named
# there, so a coordinator can tell "the driver never bound" from "the
# part never answered" from "we never asked" in one pass instead of one
# board boot per hypothesis.
#
# Run ON the board, at a root shell (it reads local /proc, /sys and runs
# local commands -- unlike tools/probe-display.sh it is not a serial
# wrapper, though its output can be captured the same way that script
# already captures other checks, via
# `tools/console.py --send 'sh tools/board-inventory-probe.sh'` over
# /dev/ttyACM0):
#
#   sh tools/board-inventory-probe.sh
#
# STRICTLY READ-ONLY. It never:
#   - writes an I2C/SPI register: i2cdetect runs with -r only, the SMBus
#     "receive byte" read, never the default "quick write" probe
#   - loads or unloads a kernel module
#   - writes a sysfs attribute (brightness, PWM duty cycle, GPIO value,
#     watchdog timeout, ...)
#   - resets, suspends, or power-cycles anything
#   - opens /dev/ttyACM0 itself -- it runs on the board, not over the
#     console link, so it never contends with another operator's session
#
# BOARD_INVENTORY_ROOT redirects the /proc and /sys walks to a synthetic
# tree for the host-side fixture test, tools/test-board-inventory-probe.sh
# (same pattern as tools/second-core-readiness.sh /
# SECOND_CORE_ROOT). BOARD_INVENTORY_I2C_SKIP is a space-separated list of
# extra hex addresses (e.g. "6b 55") a coordinator wants called out as
# already known to be read-sensitive on this board -- it is RECORDED
# against each bus in the output as a reviewer note, not used to mask
# i2cdetect's own table (i2cdetect has no such exclude option); the
# actual safety property is that every scan runs in "-r" mode regardless.
set -eu

root=${BOARD_INVENTORY_ROOT:-/}
skip_extra=${BOARD_INVENTORY_I2C_SKIP:-}
path() { printf '%s%s' "$root" "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

printf 'board-inventory-probe v1\n'
printf 'captured-utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'source-root=%s\n' "$root"

# --- 1. device tree: every node's status, or "(default okay)" -------------
printf '\n== device-tree ==\n'
dt=$(path /proc/device-tree)
if [ -d "$dt" ]; then
  find "$dt" -type d 2>/dev/null | sort | while IFS= read -r node; do
    rel=${node#"$dt"}
    [ -n "$rel" ] || rel="/"
    if [ -r "$node/status" ]; then
      status=$(tr -d '\000' < "$node/status")
    else
      status="(default okay)"
    fi
    printf 'node=%s status=%s\n' "$rel" "$status"
  done
else
  printf '<device-tree-unreadable>\n'
fi

# --- 2. I2C buses: read-only quick-read scan only --------------------------
printf '\n== i2c ==\n'
# i2cdetect's own reserved ranges (0x00-0x02, 0x78-0x7f) are always
# skipped by i2cdetect itself. -r selects the SMBus "receive byte" read;
# it is never the default "quick write" probe, which is the one that can
# have side effects on some parts -- that "-r" choice, not
# BOARD_INVENTORY_I2C_SKIP, is what makes every one of these scans safe.
# BOARD_INVENTORY_I2C_SKIP only annotates the output (see above); it does
# not change what gets scanned.
found_bus=0
for dev in "$root"/dev/i2c-*; do
  [ -e "$dev" ] || continue
  found_bus=1
  bus=${dev##*i2c-}
  name_file=$(path "/sys/class/i2c-dev/i2c-$bus/name")
  name="<unknown>"
  [ -r "$name_file" ] && name=$(tr -d '\000\n' < "$name_file")
  printf 'bus=%s name=%s\n' "$bus" "$name"
  if [ -n "$skip_extra" ]; then
    printf 'bus=%s skip-extra=%s\n' "$bus" "$skip_extra"
  fi
  if have i2cdetect; then
    i2cdetect -y -r "$bus" 2>&1 | sed "s/^/bus=$bus /"
  else
    printf 'bus=%s <i2cdetect-unavailable>\n' "$bus"
  fi
done
[ "$found_bus" = 1 ] || printf '<no-i2c-bus-found>\n'

# --- 3. sysfs class directories -------------------------------------------
printf '\n== sysfs classes ==\n'
for cls in power_supply backlight input sound video4linux bluetooth net \
           thermal pwm gpio; do
  dir=$(path "/sys/class/$cls")
  printf 'class=%s: ' "$cls"
  if [ -d "$dir" ]; then
    ls -1 "$dir" 2>/dev/null | tr '\n' ' '
    printf '\n'
  else
    printf '<absent>\n'
  fi
done

# --- 4. USB topology --------------------------------------------------------
printf '\n== usb ==\n'
if have lsusb; then
  lsusb 2>&1
else
  printf '<lsusb-unavailable>\n'
fi

# --- 5. dmesg, driver-probe-shaped lines only ------------------------------
printf '\n== dmesg (driver-probe lines) ==\n'
if have dmesg; then
  dmesg 2>/dev/null | grep -iE 'probe|bound|ready|okay|error|fail' || true
else
  printf '<dmesg-unavailable>\n'
fi

# --- 6. loaded modules ------------------------------------------------------
printf '\n== lsmod ==\n'
if have lsmod; then
  lsmod 2>&1
else
  printf '<lsmod-unavailable>\n'
fi
