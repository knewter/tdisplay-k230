LABEL=$1
E="env SWAYSOCK=/run/shell/sway-ipc.sock"
S() { runuser -u shell -- $E swaymsg "$@" >/dev/null 2>&1; }
S card_shell back; sleep 1
S card_shell benchmark injected; sleep 0.5; S card_shell enter; sleep 1.5
M0=$(date +%s)

for pass in 1 2 3 4 5 6; do
  S card_shell down 7 460 700
  for x in $(seq 450 -12 110); do S card_shell motion 7 $x 700; done
  S card_shell up 7; sleep 0.9
  S card_shell down 7 110 700
  for x in $(seq 122 12 460); do S card_shell motion 7 $x 700; done
  S card_shell up 7; sleep 0.9
done
S card_shell benchmark-stop; sleep 1
S card_shell back
journalctl -u shell --since "@$M0" --no-pager -o cat | grep -a -E "K230_CARD_BENCH|filter-mode" > /run/k230-bench-$LABEL.log
echo "BENCHLINES $(grep -c K230_CARD_BENCH /run/k230-bench-$LABEL.log) FILTER $(grep -c filter-mode /run/k230-bench-$LABEL.log)"
