#!/usr/bin/env bash
# Run every display and touch check in one pass, on a board already at a
# root shell, and write the transcripts the-screen-comes-up-under-linux
# names as its evidence.
#
# Each boot of this board costs a card swap, so the point is to come back
# with everything at once rather than discover the next missing thing.
#
#   tools/probe-display.sh
#
# Prerequisites, all confirmed present in the image built from this tree:
#   fbset, modetest (libdrm), evtest, i2c-tools
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=docs/evidence
mkdir -p "$OUT"

echo "capturing panel + touch probe to $OUT/panel-probe.txt" >&2

python3 tools/capture-boot.py --out "$OUT/panel-probe.txt" --seconds 120 --kick \
  --expect 'root@nixos:~' \
  `# --- task 2.3: did the panel bind, and did DSI complain? ---` \
  --send 'dmesg | grep -iE "drm|dsi|panel|canaan|vo@|backlight" | head -40' \
  --send 'ls -l /dev/dri/ 2>&1; ls -l /dev/fb* 2>&1' \
  `# --- task 3.1: is there a 568x1232 framebuffer? ---` \
  --send 'fbset -i 2>&1 | head -20' \
  --send 'modetest -M canaan-drm -c 2>&1 | head -30' \
  `# --- thermal: the one unanswered safety question ---` \
  --send 'for z in /sys/class/thermal/thermal_zone*; do echo "$z $(cat $z/type) $(cat $z/temp)"; done 2>&1' \
  --send 'cat /sys/class/thermal/thermal_zone0/trip_point_* 2>&1 | head' \
  `# --- task 4.1: did the touch controller bind via the gt9916 fallback? ---` \
  --send 'dmesg | grep -iE "goodix|berlin|touch|i2c" | head -20' \
  --send 'i2cdetect -y -r 3 2>&1 | head -12' \
  --send 'ls -l /dev/input/ 2>&1; cat /proc/bus/input/devices 2>&1 | head -30'

echo >&2
echo "done. Next, by hand, because they need a person:" >&2
echo "  3.2  write a test pattern and PHOTOGRAPH the panel:" >&2
echo "         cat /dev/urandom > /dev/fb0     # or a solid fill" >&2
echo "       a framebuffer node is explicitly NOT sufficient evidence" >&2
echo "  4.3  evtest, then drag a finger across the panel:" >&2
echo "         evtest /dev/input/eventN | tee $OUT/touch-evtest.txt" >&2
echo "       needs a drag, not a tap, to show axes are not swapped/mirrored" >&2
