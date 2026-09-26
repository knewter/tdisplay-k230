D=$(cat /run/k230-inject-dev.path)
dx() { echo $(( $1 * 1024 / 568 )); }; dy() { echo $(( $1 * 2400 / 1232 )); }
ev() { evemu-event "$D" --type "$1" --code "$2" --value "$3"; }
syn() { evemu-event "$D" --type EV_SYN --code SYN_REPORT --value 0; }
move() { ev EV_ABS ABS_MT_POSITION_Y "$(dy $1)"; ev EV_ABS ABS_Y "$(dy $1)"; syn; }
ev EV_ABS ABS_MT_SLOT 0; ev EV_ABS ABS_MT_TRACKING_ID 9
ev EV_ABS ABS_MT_POSITION_X "$(dx 284)"; ev EV_ABS ABS_MT_POSITION_Y "$(dy 4)"; ev EV_ABS ABS_MT_TOUCH_MAJOR 3
ev EV_KEY BTN_TOUCH 1; ev EV_ABS ABS_X "$(dx 284)"; ev EV_ABS ABS_Y "$(dy 4)"; syn
for y in $(seq 20 20 620); do move $y; sleep 0.08; done   # slow pull to ~half
sleep 1.5                                                   # hold at half
for y in $(seq 620 -20 200); do move $y; sleep 0.06; done   # back up partway
for y in $(seq 200 40 1000); do move $y; sleep 0.03; done   # then pull fully
ev EV_ABS ABS_MT_TRACKING_ID -1; ev EV_KEY BTN_TOUCH 0; syn
echo SHADE_DONE
