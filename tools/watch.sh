#!/bin/bash
# Poll USB + tty + block state; report any change. Exits on first change or after timeout.
deadline=$((SECONDS + ${1:-240}))
state() {
  for d in /sys/bus/usb/devices/*/; do
    [ -f "$d/idVendor" ] || continue
    echo "USB $(basename $d) $(cat $d/idVendor):$(cat $d/idProduct) $(cat $d/product 2>/dev/null)"
  done | sort
  ls -1 /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | sed 's/^/TTY /'
  lsblk -dno NAME,SIZE,TRAN 2>/dev/null | sed 's/^/BLK /'
}
prev=$(state)
echo "watching... (baseline: $(echo "$prev" | grep -c ^USB) usb devices)"
while [ $SECONDS -lt $deadline ]; do
  sleep 0.5
  cur=$(state)
  if [ "$cur" != "$prev" ]; then
    echo "=== CHANGE DETECTED at $(date +%H:%M:%S) ==="
    diff <(echo "$prev") <(echo "$cur") | grep -E '^[<>]'
    prev="$cur"
    sleep 2   # let enumeration settle
    cur=$(state)
    if [ "$cur" != "$prev" ]; then
      echo "--- settled state delta ---"
      diff <(echo "$prev") <(echo "$cur") | grep -E '^[<>]'
    fi
    echo "=== done ==="
    exit 0
  fi
done
echo "no change in ${1:-240}s"
