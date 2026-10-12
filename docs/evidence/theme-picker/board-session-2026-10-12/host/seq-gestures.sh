#!/bin/sh
for spec in "g-ca-theme-1 candidate theme" "g-ca-bg-1 candidate background" "g-mo-bg-1 motion background" "g-ca-theme-2 candidate theme" "g-mo-theme-2 motion theme" "g-mo-bg-2 motion background" "g-ca-bg-2 candidate background"; do
  set -- $spec; echo "=== $1 $(date -u +%FT%TZ)"; ./gog.sh $1 $2 $3 2 > runs.$1.log 2>&1; echo "rc=$? $(date -u +%FT%TZ)"
done
echo SEQ3_DONE
