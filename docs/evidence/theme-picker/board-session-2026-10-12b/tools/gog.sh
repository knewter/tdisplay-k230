#!/bin/sh
# usage: gog.sh NAME KIND(baseline|candidate|motion) ROW REPS  -> gesture trial, trace mode
NAME=$1; KIND=$2; ROW=$3; REPS=${4:-2}
CAND=/nix/store/3m65ag9zlzffdd86ajjfq7si96cj46y1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust
MOT=/nix/store/si9vd9hhdcb8kzppfsfq9id8kaqhnmwk-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust
case $KIND in candidate) EXE=$CAND; K=candidate;; motion) EXE=$MOT; K=baseline;; esac
B=/root/tmp/k230-theme-board-session-20261012
PY=/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3
SSH="ssh -F $HOME/tmp/k230-coordination/ssh_config.private k230"
mkdir -p runs/$NAME
$SSH "rm -rf $B/runs/$NAME; systemctl stop k230-theme-sess-$NAME 2>/dev/null; systemd-run --quiet --pipe --wait --collect --unit=k230-theme-sess-$NAME --property=RuntimeMaxSec=400s --setenv=PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin $PY $B/run.py run --label $NAME --kind $K --exe $EXE --mode trace --trace-seconds 175 --restore-s 330 --workload gestures --row $ROW --reps $REPS --out $B/runs/$NAME" 2>&1 | sed -E 's/([0-9]{1,3}\.){3}[0-9]{1,3}/<board>/g' | tee runs/$NAME/driver.log
for f in gestures.private.json plan.json meta.json rust-trace.json; do $SSH "cat $B/runs/$NAME/$f" > runs/$NAME/$f 2>/dev/null || true; done
mkdir -p runs/$NAME/shots; scp -q -r -F $HOME/tmp/k230-coordination/ssh_config.private k230:$B/runs/$NAME/shots/. runs/$NAME/shots/ 2>&1 | sed -E 's/([0-9]{1,3}\.){3}[0-9]{1,3}/<board>/g'
find runs/$NAME -size 0 -delete
ls runs/$NAME | head -20
