#!/usr/bin/env bash
# Sample finite Wayland screencopy PNG frames on the board for host encoding.
#
# /proc/uptime's first field is a boot-relative, monotonically increasing
# timestamp.  The file records the time immediately before and immediately
# after each grim invocation; it does not claim that the requested interval
# was achieved when capture itself takes longer.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: sample-grim-frames.sh FEATURE --description TEXT [options]

Capture a finite sequence of PNG frames with grim and write frames.tsv with
actual boot-relative monotonic start/end timestamps for every capture.

Options:
  --duration SECONDS       Total sampling window (default: 20; max: 30)
  --interval SECONDS       Minimum start-to-start interval (default: 0.5)
  --output-dir DIR         Parent directory (default: ./grim-samples)
  --display NAME           Wayland display socket (default: $WAYLAND_DISPLAY or wayland-1)
  --runtime-dir DIR        XDG runtime directory (default: $XDG_RUNTIME_DIR or /run/shell)
  --grim PATH              grim executable (default: grim on PATH)
  --provenance VALUE       real-touch, injected, or unknown (default: unknown)
  --description TEXT       What the sampled clip is intended to show (required)

Run this as the graphical-session user.  The output is sampled Wayland
screencopy, not continuous video or performance evidence.
EOF
}

die() { echo "sample-grim-frames: $*" >&2; exit 2; }

feature=""
description=""
duration=20
interval=0.5
output_parent=./grim-samples
display="${WAYLAND_DISPLAY:-wayland-1}"
runtime_dir="${XDG_RUNTIME_DIR:-/run/shell}"
grim=grim
provenance=unknown

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --duration|--interval|--output-dir|--display|--runtime-dir|--grim|--provenance|--description)
      [ "$#" -ge 2 ] || die "$1 needs a value"
      case "$1" in
        --duration) duration=$2 ;;
        --interval) interval=$2 ;;
        --output-dir) output_parent=$2 ;;
        --display) display=$2 ;;
        --runtime-dir) runtime_dir=$2 ;;
        --grim) grim=$2 ;;
        --provenance) provenance=$2 ;;
        --description) description=$2 ;;
      esac
      shift 2 ;;
    --*) die "unknown option: $1" ;;
    *)
      [ -z "$feature" ] || die "only one feature name is allowed"
      feature=$1
      shift ;;
  esac
done

[ -n "$feature" ] || die "feature name is required"
[ -n "$description" ] || die "--description is required"
case "$feature" in *[!a-zA-Z0-9_-]*|'') die "feature may contain only letters, numbers, _ and -" ;; esac
case "$provenance" in real-touch|injected|unknown) ;; *) die "invalid --provenance: $provenance" ;; esac

is_positive_number() { awk -v value="$1" 'BEGIN { exit !(value + 0 > 0 && value ~ /^[0-9]+([.][0-9]+)?$/) }'; }
is_positive_number "$duration" || die "--duration must be a positive number"
is_positive_number "$interval" || die "--interval must be a positive number"
awk -v value="$duration" 'BEGIN { exit !(value + 0 <= 30) }' || die "--duration may not exceed 30 seconds"

monotonic_seconds() { awk '{ print $1; exit }' /proc/uptime; }
elapsed_at_least() { awk -v start="$1" -v limit="$2" -v now="$3" 'BEGIN { exit !((now - start) >= limit) }'; }
sleep_until() {
  local target=$1 now wait
  now=$(monotonic_seconds)
  wait=$(awk -v target="$target" -v now="$now" 'BEGIN { value = target - now; if (value > 0) printf "%.6f", value }')
  [ -z "$wait" ] || sleep "$wait"
}

command -v "$grim" >/dev/null 2>&1 || die "grim was not found: $grim"
[ -S "$runtime_dir/$display" ] || die "Wayland socket is not available: $runtime_dir/$display"

utc=$(date -u +%Y%m%dT%H%M%SZ)
output_dir="$output_parent/$utc-$feature"
mkdir -p "$output_dir"
frames_tsv="$output_dir/frames.tsv"
info="$output_dir/capture-info.txt"
printf 'index\tstart_monotonic_seconds\tend_monotonic_seconds\tfile\n' > "$frames_tsv"
cat > "$info" <<EOF
feature=$feature
description=$description
provenance=$provenance
capture_kind=sampled-wayland-screencopy-png
timestamp_clock=/proc/uptime first field (boot-relative monotonic seconds)
requested_duration_seconds=$duration
requested_minimum_start_interval_seconds=$interval
wayland_display=$display
xdg_runtime_dir=$runtime_dir
note=Sampling timestamps describe grim invocation bounds. They do not prove a smooth frame rate, compositor performance, or real touch.
EOF

export XDG_RUNTIME_DIR="$runtime_dir"
export WAYLAND_DISPLAY="$display"

start_window=$(monotonic_seconds)
index=0
while :; do
  frame_start=$(monotonic_seconds)
  elapsed_at_least "$start_window" "$duration" "$frame_start" && break
  index=$((index + 1))
  frame=$(printf 'frame-%06d.png' "$index")
  "$grim" "$output_dir/$frame"
  frame_end=$(monotonic_seconds)
  printf '%s\t%s\t%s\t%s\n' "$index" "$frame_start" "$frame_end" "$frame" >> "$frames_tsv"
  next_start=$(awk -v start="$frame_start" -v interval="$interval" 'BEGIN { printf "%.6f", start + interval }')
  sleep_until "$next_start"
done

archive="$output_parent/$(basename "$output_dir").tar.gz"
tar -C "$output_parent" -czf "$archive" "$(basename "$output_dir")"
printf 'captured %s sampled PNG frame(s): %s\n' "$index" "$output_dir"
printf 'serial-transfer archive: %s\n' "$archive"
