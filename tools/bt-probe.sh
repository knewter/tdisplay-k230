#!/usr/bin/env sh
# Read-only onboard-Bluetooth probe for the T-Display-K230.
#
# Companion to docs/research/bluetooth-onboard.md: that document concludes,
# from the physical board's own already-captured SDIO enumeration
# (docs/evidence/wifi-preflight.txt: vendor 0x024c device 0xf179, one SDIO
# function) plus LILYGO's own upstream BSP doc
# (k230_bsp/docs/HARDWARE_PINMAP.md in Xinyuan-LilyGO/T-Display-K230), that
# this board's Wi-Fi part is the RTL8189FS/RTL8188F family, which is
# Wi-Fi-only -- not the RTL8723DS combo variant the same BSP names as an
# alternate build option. This script exists so a future board session (a
# different physical unit, a revision, or simply "double-check before
# trusting a research doc") can re-derive that conclusion from the running
# kernel directly, in one pass, without editing anything.
#
# Run ON the board, at a root shell:
#
#   sh tools/bt-probe.sh
#
# or captured over the console the way other probes here are, e.g.
# `tools/console.py --send 'sh tools/bt-probe.sh'` over /dev/ttyACM0.
#
# STRICTLY READ-ONLY. It never:
#   - loads or unloads a kernel module
#   - unblocks/blocks rfkill, powers a controller up/down, or writes any
#     sysfs attribute
#   - opens /dev/ttyACM0 itself -- it runs on the board, not over the
#     console link
#   - the `hciconfig -a`/`btmgmt info` calls below only query existing
#     controller state; neither is passed a subcommand that changes it
#     (no `up`, `down`, `power on`, `power off`, `reset`)
#
# BT_PROBE_ROOT redirects the /proc, /sys and /dev walks to a synthetic
# tree for the host-side fixture test, tools/test-bt-probe.sh (same
# BOARD_INVENTORY_ROOT pattern as tools/board-inventory-probe.sh).
set -eu

root=${BT_PROBE_ROOT:-/}
path() { printf '%s%s' "$root" "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

printf 'bt-probe v1\n'
printf 'captured-utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'source-root=%s\n' "$root"

# --- 1. SDIO devices and functions ------------------------------------------
# A Realtek Wi-Fi/BT combo part (e.g. RTL8723DS) that carried Bluetooth over
# SDIO would show a second function (mmcX:RCA:2) alongside the Wi-Fi
# function (mmcX:RCA:1) under the same card. A single mmcX:RCA:1 with no
# ":2" sibling is the Wi-Fi-only signature this board's own preflight
# capture already showed (docs/evidence/wifi-preflight.txt).
printf '\n== sdio ==\n'
sdio_dir=$(path /sys/bus/sdio/devices)
found_sdio=0
if [ -d "$sdio_dir" ]; then
  for dev in "$sdio_dir"/*; do
    [ -e "$dev" ] || continue
    found_sdio=1
    name=$(basename "$dev")
    vendor="<unreadable>"
    device="<unreadable>"
    modalias="<unreadable>"
    [ -r "$dev/vendor" ] && vendor=$(tr -d '\000\n' < "$dev/vendor")
    [ -r "$dev/device" ] && device=$(tr -d '\000\n' < "$dev/device")
    [ -r "$dev/modalias" ] && modalias=$(tr -d '\000\n' < "$dev/modalias")
    driver="(unbound)"
    if [ -L "$dev/driver" ]; then
      driver=$(basename "$(readlink "$dev/driver")")
    fi
    printf 'function=%s vendor=%s device=%s modalias=%s driver=%s\n' \
      "$name" "$vendor" "$device" "$modalias" "$driver"
  done
fi
[ "$found_sdio" = 1 ] || printf '<no-sdio-device-found>\n'

# --- 2. ttyS list, with any device-tree node ---------------------------------
# A UART-attached BT controller (hci_uart, as an RTL8723DS's Bluetooth half
# or a Zephyr hci_uart image would use) shows up as a ttyS whose ldisc has
# been switched by hciattach/btattach, or as a dedicated DT node naming a
# "bluetooth" or "brcm,bcm..."/"realtek,rtl..." compatible under that UART.
printf '\n== ttyS ==\n'
tty_dir=$(path /sys/class/tty)
found_tty=0
if [ -d "$tty_dir" ]; then
  for t in "$tty_dir"/ttyS*; do
    [ -e "$t" ] || continue
    found_tty=1
    name=$(basename "$t")
    of_node="(none)"
    if [ -L "$t/device/of_node" ]; then
      of_node=$(readlink "$t/device/of_node")
    fi
    of_compatible="(none)"
    if [ "$of_node" != "(none)" ]; then
      compat_file="$t/device/of_node/compatible"
      [ -r "$compat_file" ] && of_compatible=$(tr '\000' ' ' < "$compat_file")
    fi
    printf 'tty=%s of_node=%s compatible=%s\n' "$name" "$of_node" "$of_compatible"
  done
fi
[ "$found_tty" = 1 ] || printf '<no-ttyS-found>\n'

# --- 3. rfkill (read-only list) ---------------------------------------------
printf '\n== rfkill ==\n'
if have rfkill; then
  rfkill list 2>&1
else
  printf '<rfkill-unavailable>\n'
fi

# --- 4. Bluetooth controller query (read-only) ------------------------------
printf '\n== hciconfig ==\n'
if have hciconfig; then
  hciconfig -a 2>&1
else
  printf '<hciconfig-unavailable>\n'
fi

printf '\n== btmgmt ==\n'
if have btmgmt; then
  btmgmt info 2>&1
else
  printf '<btmgmt-unavailable>\n'
fi

# --- 5. dmesg, BT/HCI/Realtek-shaped lines only ------------------------------
printf '\n== dmesg (bt/hci/rtk lines) ==\n'
if have dmesg; then
  dmesg 2>/dev/null | grep -iE 'bt|bluetooth|hci|rtk' || true
else
  printf '<dmesg-unavailable>\n'
fi

# --- 6. USB device IDs from sysfs -------------------------------------------
# Confirms whether any USB Bluetooth dongle or hub-embedded BT chip is
# attached; a bare read of idVendor/idProduct/product never changes device
# state.
printf '\n== usb ids (sysfs) ==\n'
usb_dir=$(path /sys/bus/usb/devices)
found_usb=0
if [ -d "$usb_dir" ]; then
  for dev in "$usb_dir"/*; do
    [ -e "$dev/idVendor" ] || continue
    found_usb=1
    name=$(basename "$dev")
    vendor=$(tr -d '\000\n' < "$dev/idVendor" 2>/dev/null || printf '?')
    product=$(tr -d '\000\n' < "$dev/idProduct" 2>/dev/null || printf '?')
    label="<unnamed>"
    [ -r "$dev/product" ] && label=$(tr -d '\000\n' < "$dev/product")
    printf 'dev=%s id=%s:%s product=%s\n' "$name" "$vendor" "$product" "$label"
  done
fi
[ "$found_usb" = 1 ] || printf '<no-usb-device-found>\n'
