#!/usr/bin/env bash
# Host-side fixture test for tools/measure-panel-refresh.sh, same pattern as
# tools/test-board-inventory-probe.sh: build a synthetic /proc/interrupts and
# debugfs tree, run the script against it via MEASURE_PANEL_REFRESH_ROOT, and
# assert on specific output lines. modetest and the probe binary are
# deliberately left unavailable (minimal PATH) so this test exercises the
# graceful-degradation paths without depending on real DRM hardware.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT

mkdir -p "$fixture/proc" "$fixture/sys/kernel/debug/dri/0/crtc-0"
cat > "$fixture/proc/interrupts" <<'EOF'
           CPU0       CPU1
 39:      31207          0     PLIC     90840000.vo
 40:        512          3     PLIC     91000000.i2c
EOF
printf 'plane=OSD crtc=0 fb=12\n' > "$fixture/sys/kernel/debug/dri/0/crtc-0/state"

bin="$fixture/bin"
mkdir -p "$bin"
for tool in grep sed awk date sleep head sort tr cat find; do
  src=$(command -v "$tool")
  ln -s "$src" "$bin/$tool"
done

sh_bin=$(command -v sh)
out=$(PATH="$bin" MEASURE_PANEL_REFRESH_ROOT="$fixture" MEASURE_PANEL_REFRESH_SECONDS=0 \
  MEASURE_PANEL_REFRESH_PROBE="$fixture/no-such-probe" \
  "$sh_bin" "$repo/tools/measure-panel-refresh.sh")

grep -Fq 'PANEL_REFRESH v=1 event=probe_start' <<<"$out"
grep -Fqx 'PANEL_REFRESH v=1 event=note text=modetest-unavailable' <<<"$out"
grep -Fq 'PANEL_REFRESH v=1 event=irq_sample phase=before irq=39 count=31207' <<<"$out"
grep -Fq 'PANEL_REFRESH v=1 event=irq_sample phase=after irq=39 count=31207' <<<"$out"
grep -Fqx "PANEL_REFRESH v=1 event=note text=probe-unavailable path=$fixture/no-such-probe" <<<"$out"
grep -Fq 'PANEL_REFRESH v=1 event=debugfs path=/sys/kernel/debug/dri/0/crtc-0/state' <<<"$out"
grep -Fq 'PANEL_REFRESH_RAW debugfs /sys/kernel/debug/dri/0/crtc-0/state: plane=OSD crtc=0 fb=12' <<<"$out"
grep -Fqx 'PANEL_REFRESH v=1 event=probe_end' <<<"$out"

printf '%s\n' 'measure-panel-refresh fixture: PASS'
