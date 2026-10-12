#!/bin/sh
# Board, root. Run apply_trial.sh twice with shell-ui on the candidate ELF through a /run drop-in, then restore.
EXE=/nix/store/x6hhs64wvx9w2hca3wldyyvjhyp4qivl-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust
PY=/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3
B=/root/tmp/k230-theme-board-session-20261012
$PY /root/tmp/k230-session-b/swap-and-swipe.py $EXE apply-b leave || exit 1
for n in 1 2; do
  echo "=== TRIAL $n $(date -u +%FT%T.%3NZ)"; START=$(date -u '+%F %T')
  sh /root/tmp/k230-session-b/apply_trial.sh
  echo "RUST_EXE $(readlink /proc/$(systemctl show shell-ui -p MainPID --value)/exe)"
  journalctl -o short-iso-precise -u shell-ui -u theme-helper --since "$START" --no-pager > /root/tmp/k230-session-b/journal-trial-$n.private.txt
  sleep 3
done
rm -f /run/systemd/system/shell-ui.service.d/93-row-paint.conf; systemctl daemon-reload; systemctl restart shell-ui; sleep 5
echo "RESTORED $(readlink /proc/$(systemctl show shell-ui -p MainPID --value)/exe)"
