#!/bin/bash
# Follow the kernel log for USB events INCLUDING failed enumerations.
dur=${1:-900}
echo "following kernel usb events for ${dur}s from $(date +%H:%M:%S)..."
timeout $dur journalctl -k -f -o short-iso --no-pager 2>/dev/null \
  | grep --line-buffered -iE 'usb [0-9]|usb[0-9]-port|ttyACM|cdc.acm|1a86|error -[0-9]+|unable to enumerate|not accepting|descriptor read' \
  | while read -r l; do
      echo "$l"
      case "$l" in
        *ttyACM*|*1a86*) echo ">>> CONSOLE DEVICE APPEARED <<<" ;;
      esac
    done
echo "kwatch done at $(date +%H:%M:%S)"
