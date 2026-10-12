#!/bin/sh
# Board work for 18.3 (gesture curves, candidate only) then 11.3 (three recorder-off matched pairs, alternating order).
cd "$(dirname "$0")"
for spec in "g-theme-1 candidate theme" "g-bg-1 candidate background" "g-theme-2 candidate theme" "g-bg-2 candidate background"; do
  set -- $spec; echo "=== $1 $(date -u +%FT%TZ)"; ./gog.sh $1 $2 $3 2 > runs.$1.log 2>&1; rc=$?; echo "rc=$rc $(date -u +%FT%TZ)"; [ $rc = 0 ] || exit 1
done
for spec in "of-p1-cand candidate off" "of-p1-base baseline off" "of-p2-base baseline off" "of-p2-cand candidate off" "of-p3-cand candidate off" "of-p3-base baseline off"; do
  set -- $spec; echo "=== $1 $(date -u +%FT%TZ)"; ./go.sh $1 $2 $3 > runs.$1.log 2>&1; rc=$?; echo "rc=$rc $(date -u +%FT%TZ)"; [ $rc = 0 ] || exit 1; tail -3 runs/$1/driver.log | cut -c1-150
done
echo SEQ_DONE
