D=$(cat /run/k230-inject-dev.path); T=/run/k230-inject-tap.sh
dx() { echo $(( $1 * 1024 / 568 )); }; dy() { echo $(( $1 * 2400 / 1232 )); }
ev() { evemu-event "$D" --type "$1" --code "$2" --value "$3"; }
syn() { evemu-event "$D" --type EV_SYN --code SYN_REPORT --value 0; }
down() { ev EV_ABS ABS_MT_SLOT 0; ev EV_ABS ABS_MT_TRACKING_ID $3; ev EV_ABS ABS_MT_POSITION_X "$(dx $1)"; ev EV_ABS ABS_MT_POSITION_Y "$(dy $2)"; ev EV_ABS ABS_MT_TOUCH_MAJOR 3; ev EV_KEY BTN_TOUCH 1; ev EV_ABS ABS_X "$(dx $1)"; ev EV_ABS ABS_Y "$(dy $2)"; syn; }
move() { ev EV_ABS ABS_MT_POSITION_Y "$(dy $1)"; ev EV_ABS ABS_Y "$(dy $1)"; syn; }
up() { ev EV_ABS ABS_MT_TRACKING_ID -1; ev EV_KEY BTN_TOUCH 0; syn; }
echo "T0 $(date +%s.%N)"
sh $T $D 284 4 284 1000; sleep 2                           # open shade
echo "CLOSE_SLOW $(date +%s.%N)"
down 284 1100 21; for y in $(seq 1090 -15 400); do move $y; sleep 0.06; done; sleep 0.8; up; sleep 2
echo "OPEN2 $(date +%s.%N)"
sh $T $D 284 4 284 1000; sleep 2
echo "SHORT_DRAG $(date +%s.%N)"
down 284 1100 22; for y in $(seq 1090 -15 1000); do move $y; sleep 0.06; done; sleep 0.5; up; sleep 2
echo "TAP_BACKDROP $(date +%s.%N)"
sh $T $D 284 1150; sleep 2
echo CLOSE_DONE
