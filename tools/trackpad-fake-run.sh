# Run on the board as root next to tools/fake-touchscreen.py copied to /tmp.
# trackpad-fake-run.sh 'fake script': run a second trackpad daemon on a fake panel.
# Panel raw X runs along the screen's vertical axis, raw Y along its horizontal
# axis (raw Y increasing = swipe left on screen).
PY=/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3
BIN=$(systemctl show -p ExecStart k230-touch-trackpad.service | grep -o '/nix/store/[^ ]*/bin/k230-touch-trackpad' | head -1)
T=$(date +%T.%N)
$PY /tmp/fake-touchscreen.py /dev/input/event1 "$1" > /tmp/fake.log 2>&1 &
FP=$!
for i in $(seq 50); do grep -q FAKE_READY /tmp/fake.log && break; sleep 0.05; done
EV=$(awk '/N: Name="Fake Goodix TouchScreen"/{f=1} f&&/H: Handlers/{match($0,/event[0-9]+/); print substr($0,RSTART,RLENGTH); exit}' /proc/bus/input/devices)
$BIN --device=/dev/input/$EV --shell-socket=/run/shell/sway-ipc.sock --panel-transform=270 --log-events > /tmp/td.log 2>&1 &
DP=$!
wait $FP
sleep 0.5; kill $DP; wait $DP 2>/dev/null
echo "fake=$EV"; grep -v 'out type=' /tmp/td.log | head -30; echo "-- out events: $(grep -c 'out type=' /tmp/td.log)"
echo "-- shell:"; journalctl -b --since "$T" -t k230-shell-rust --no-pager -o cat | grep -v 'HOME_FRAME\|configure\|commit\|pointer-state'
echo "-- sway trackpad:"; journalctl -b --since "$T" --no-pager -o cat | grep -E 'card_shell trackpad (begin|end|cancel)|accepted=0' | grep -v 'Handling command .card_shell trackpad move' | head
