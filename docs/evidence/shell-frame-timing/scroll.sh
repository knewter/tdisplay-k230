#!/usr/bin/env bash
# Deterministic 20-line/s scrolling terminal workload; no input injection.
set -eu
printf '\033[2J\033[H'
for ((line=1; line<=400; line++)); do
    printf '%04d K230 scrolling terminal\n' "$line"
    sleep 0.05
done
printf '\nScroll workload complete.\n'
sleep 5
