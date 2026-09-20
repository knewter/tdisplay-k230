#!/bin/bash
# Snapshot USB + serial + block state. Usage: snap.sh <outfile>
out="$1"
{
  echo "### lsusb"
  lsusb | sort -t' ' -k6
  echo
  echo "### usb sysfs (vid:pid product serial)"
  for d in /sys/bus/usb/devices/*/; do
    [ -f "$d/idVendor" ] || continue
    printf '%-10s %s:%s  %-28s %-24s %s\n' \
      "$(basename $d)" \
      "$(cat $d/idVendor)" "$(cat $d/idProduct)" \
      "$(cat $d/product 2>/dev/null || echo -)" \
      "$(cat $d/manufacturer 2>/dev/null || echo -)" \
      "$(cat $d/serial 2>/dev/null || echo -)"
  done | sort
  echo
  echo "### tty"
  ls -1 /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
  echo
  echo "### net interfaces"
  ls -1 /sys/class/net/
  echo
  echo "### block"
  lsblk -o NAME,SIZE,TYPE,TRAN,LABEL -n
} > "$out" 2>&1
