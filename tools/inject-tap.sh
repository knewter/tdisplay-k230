#!/bin/sh
# Inject one touch tap (or a drag) into a uinput touchscreen made with
# evemu-device, in PANEL pixel coordinates. Runs ON the board.
#
# This is a software proxy for a finger. It exercises the whole path from
# libinput through sway's map_to_output to the surface under the point, but
# it says nothing about the glass, the GT9895 or its axes; those are
# display/touch's evidence (docs/evidence/touch-reports.md). Anything
# recorded with this script is labelled "injected" in docs/evidence.
#
# The virtual device is created from the real controller's description
# (evemu-describe /dev/input/event0), so it reports the same 1024x2400 grid
# the GT9895 does and libinput scales it to the panel exactly as it does
# the real device. Panel pixels are converted here with the same factors.
#
#   inject-tap.sh DEV X Y            tap at panel pixel (X, Y)
#   inject-tap.sh DEV X Y X2 Y2      press at (X,Y), drag to (X2,Y2), release
#
# Coordinates: panel 568x1232 portrait, origin top-left, y down.
set -e
DEV=$1; X=$2; Y=$3; X2=${4:-}; Y2=${5:-}
[ -n "$Y" ] || { echo "usage: $0 DEV X Y [X2 Y2]" >&2; exit 2; }
# panel -> digitizer: 1024/568 and 2400/1232 (touch-reports.md ranges)
dx() { echo $(( $1 * 1024 / 568 )); }
dy() { echo $(( $1 * 2400 / 1232 )); }
ev() { evemu-event "$DEV" --type "$1" --code "$2" --value "$3"; }
syn() { evemu-event "$DEV" --type EV_SYN --code SYN_REPORT --value 0; }

ev EV_ABS ABS_MT_SLOT 0
ev EV_ABS ABS_MT_TRACKING_ID 7
ev EV_ABS ABS_MT_POSITION_X "$(dx "$X")"
ev EV_ABS ABS_MT_POSITION_Y "$(dy "$Y")"
ev EV_ABS ABS_MT_TOUCH_MAJOR 3
ev EV_KEY BTN_TOUCH 1
ev EV_ABS ABS_X "$(dx "$X")"
ev EV_ABS ABS_Y "$(dy "$Y")"
syn
if [ -n "$Y2" ]; then
  # 20 steps, ~10 ms apart: a drag a compositor sees as motion, not a jump
  i=1
  while [ $i -le 20 ]; do
    px=$(( X + (X2 - X) * i / 20 )); py=$(( Y + (Y2 - Y) * i / 20 ))
    ev EV_ABS ABS_MT_POSITION_X "$(dx "$px")"
    ev EV_ABS ABS_MT_POSITION_Y "$(dy "$py")"
    ev EV_ABS ABS_X "$(dx "$px")"
    ev EV_ABS ABS_Y "$(dy "$py")"
    syn
    sleep 0.01
    i=$(( i + 1 ))
  done
else
  sleep 0.08
fi
ev EV_ABS ABS_MT_TRACKING_ID -1
ev EV_KEY BTN_TOUCH 0
syn
