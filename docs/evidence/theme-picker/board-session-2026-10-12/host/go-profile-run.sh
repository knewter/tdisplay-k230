#!/bin/sh
# usage: go.sh NAME KIND(baseline|candidate) MODE   -> runs on board, pulls results to ./runs/NAME
NAME=$1; KIND=$2; MODE=$3
CAND=/nix/store/ybpnyqmcn672n7x45nx9ybzprljgdhfg-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust
BASE=/nix/store/8cikjd811d7b7hsdhn7nnb3lnipf3vwp-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust
MOT=/nix/store/si9vd9hhdcb8kzppfsfq9id8kaqhnmwk-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust
case $KIND in baseline) EXE=$BASE;; candidate) EXE=$CAND;; motion) EXE=$MOT;; esac
K=$KIND; [ $KIND = motion ] && K=baseline
B=/root/tmp/k230-theme-board-session-20261012
PY=/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3
SSH="ssh -F $HOME/tmp/k230-coordination/ssh_config.private k230"
mkdir -p runs/$NAME
$SSH "rm -rf $B/runs/$NAME; systemctl stop k230-theme-sess-$NAME 2>/dev/null; systemd-run --quiet --pipe --wait --collect --unit=k230-theme-sess-$NAME --property=RuntimeMaxSec=400s --setenv=PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin $PY $B/run.py run --label $NAME --kind $K --exe $EXE --mode $MODE --out $B/runs/$NAME" 2>&1 | sed -E 's/([0-9]{1,3}\.){3}[0-9]{1,3}/<board>/g' | tee runs/$NAME/driver.log
for f in raw.private.json plan.json meta.json rust-trace.json; do $SSH "cat $B/runs/$NAME/$f" > runs/$NAME/$f 2>/dev/null || true; done
find runs/$NAME -size 0 -delete
ls -l runs/$NAME
