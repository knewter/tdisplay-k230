#!/bin/sh
for spec in "tr-p1-base baseline trace" "tr-p1-cand candidate trace" "tr-p2-cand candidate trace" "tr-p2-base baseline trace" "tr-p3-base baseline trace" "tr-p3-cand candidate trace" \
            "of-p1-cand candidate off" "of-p1-base baseline off" "of-p2-base baseline off" "of-p2-cand candidate off" "of-p3-cand candidate off" "of-p3-base baseline off"; do
  set -- $spec; echo "=== $1 $(date -u +%FT%TZ)"; ./go.sh $1 $2 $3 > runs.$1.log 2>&1; echo "rc=$? $(date -u +%FT%TZ)"; tail -3 runs/$1/driver.log | cut -c1-150
done
echo SEQ2_DONE
