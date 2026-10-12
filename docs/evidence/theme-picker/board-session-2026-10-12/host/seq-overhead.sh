#!/bin/sh
for spec in "ov-off2 candidate off" "ov-counters2 candidate counters" "ov-trace candidate trace" "ov-off3 candidate off" "ov-counters3 candidate counters"; do
  set -- $spec; echo "=== $1 $(date -u +%FT%TZ)"; ./go.sh $1 $2 $3 > runs.$1.log 2>&1; echo "rc=$? $(date -u +%FT%TZ)"
done
echo SEQ1_DONE
