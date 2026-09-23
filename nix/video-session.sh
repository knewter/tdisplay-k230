#!/usr/bin/env bash
# Own one bounded mpv child and keep its runtime state out of argv when a
# private playlist file is supplied. The Nix wrapper provides absolute paths.
set -u

: "${K230_VIDEO_PLAYER:=mpv}"
: "${K230_VIDEO_PUBLIC_URL:=https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd}"
: "${K230_VIDEO_RUNTIME_DIR:=/run/shell}"
: "${K230_VIDEO_PID_FILE:=$K230_VIDEO_RUNTIME_DIR/k230-video.pid}"
: "${K230_VIDEO_LOG:=$K230_VIDEO_RUNTIME_DIR/k230-video.log}"
: "${K230_VIDEO_MODE:=software}"
: "${K230_VIDEO_URL_FILE:=}"

usage() {
  echo "usage: k230-video-session {run|stop|status}" >&2
  exit 2
}

pid_starttime() {
  local pid=$1 stat rest
  [ -r "/proc/$pid/stat" ] || return 1
  rest=$(cat "/proc/$pid/stat") || return 1
  # comm may contain spaces; field 22 is field 20 after the closing ')'.
  rest=${rest#*) }
  set -- $rest
  printf '%s\n' "${20-}"
}

read_state() {
  [ -r "$K230_VIDEO_PID_FILE" ] || return 1
  IFS=' ' read -r video_pid video_starttime video_owner < "$K230_VIDEO_PID_FILE" || return 1
  [ -n "${video_pid:-}" ] && [ -n "${video_starttime:-}" ]
}

owned_alive() {
  read_state || return 1
  [ "$video_owner" = "${UID:-$(id -u)}" ] || return 1
  [ "$(pid_starttime "$video_pid" 2>/dev/null || true)" = "$video_starttime" ]
}

clear_state() { rm -f "$K230_VIDEO_PID_FILE"; }

stop_owned() {
  if ! owned_alive; then
    clear_state
    return 0
  fi
  kill -TERM "$video_pid" 2>/dev/null || true
  for _ in 1 2 3 4 5 6; do
    owned_alive || { clear_state; return 0; }
    sleep 0.5
  done
  if owned_alive; then kill -KILL "$video_pid" 2>/dev/null || true; fi
  clear_state
}

run_video() {
  if owned_alive; then
    echo "video is already running (pid $video_pid)" >&2
    return 1
  fi
  clear_state
  mkdir -p "$K230_VIDEO_RUNTIME_DIR"
  local -a decoder geometry track extra playlist_args
  local playlist_file=${K230_VIDEO_URL_FILE:-$K230_VIDEO_RUNTIME_DIR/k230-video.playlist}
  if [ -e "$playlist_file" ]; then
    [ -f "$playlist_file" ] || { echo "video URL file is not regular" >&2; return 1; }
    local mode
    mode=$(stat -c '%a' "$playlist_file" 2>/dev/null || true)
    [ "$mode" = 600 ] || { echo "video URL file must be mode 0600" >&2; return 1; }
    [ "$(stat -c '%u' "$playlist_file")" = "${UID:-$(id -u)}" ] || { echo "video URL file owner mismatch" >&2; return 1; }
    playlist_args=("--playlist=$playlist_file")
  else
    playlist_args=("$K230_VIDEO_PUBLIC_URL")
  fi
  case "$K230_VIDEO_MODE" in
    software)
      decoder=(--vd=h264)
      geometry=480x270
      track=6
      extra=()
      ;;
    mvx)
      # This is the known 30-fps silent MVX experiment. Listing h264 second
      # lets mpv fall back if the V4L2 decoder cannot negotiate the stream.
      decoder=(--vd=h264_v4l2m2m,h264 --correct-pts=no --container-fps-override=30)
      geometry=568x320
      track=7
      extra=(--sws-scaler=point)
      ;;
    *) echo "K230_VIDEO_MODE must be software or mvx" >&2; return 2 ;;
  esac
  "$K230_VIDEO_PLAYER" --no-config --vo=wlshm --profile=sw-fast --hwdec=no \
    "${decoder[@]}" --audio=no --cache=yes --demuxer-readahead-secs=30 \
    --network-timeout=10 --start=45 --length=30 --title=k230-video \
    --force-window=yes --geometry="$geometry" --vid="$track" \
    --wayland-internal-vsync=auto "${extra[@]}" "${playlist_args[@]}" \
    >>"$K230_VIDEO_LOG" 2>&1 &
  video_pid=$!
  video_starttime=$(pid_starttime "$video_pid" 2>/dev/null || true)
  # A short EOF can reap the child before /proc exposes its stat line. It is
  # still a successful, fully cleaned-up session rather than a launch error.
  if [ -z "$video_starttime" ]; then
    wait "$video_pid"; return $?
  fi
  printf '%s %s %s\n' "$video_pid" "$video_starttime" "${UID:-$(id -u)}" > "$K230_VIDEO_PID_FILE"
  trap 'stop_owned' INT TERM HUP
  wait "$video_pid"; rc=$?
  clear_state
  trap - INT TERM HUP
  return "$rc"
}

case "${1:-}" in
  run) [ "$#" -eq 1 ] || usage; run_video ;;
  run-mvx) [ "$#" -eq 1 ] || usage; K230_VIDEO_MODE=mvx run_video ;;
  stop) [ "$#" -eq 1 ] || usage; stop_owned ;;
  status) [ "$#" -eq 1 ] || usage; owned_alive ;;
  *) usage ;;
esac
