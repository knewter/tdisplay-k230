#!/usr/bin/env bash
set -u
: "${K230_VIDEO_PLAYER:=mpv}"
: "${K230_VIDEO_PUBLIC_URL:=https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd}"
: "${K230_VIDEO_RUNTIME_DIR:=/run/shell}"
: "${K230_VIDEO_PID_FILE:=$K230_VIDEO_RUNTIME_DIR/k230-video.pid}"
: "${K230_VIDEO_LOG:=$K230_VIDEO_RUNTIME_DIR/k230-video.log}"
: "${K230_VIDEO_LOCK_FILE:=$K230_VIDEO_RUNTIME_DIR/k230-video.lock}"
: "${K230_VIDEO_MODE:=software}"
: "${K230_VIDEO_URL_FILE:=}"
: "${K230_VIDEO_DEADLINE:=90}"
: "${K230_VIDEO_FLOCK:=flock}"
: "${K230_VIDEO_TIMEOUT_FILE:=$K230_VIDEO_RUNTIME_DIR/k230-video-timeout}"
: "${K230_VIDEO_CANCEL_FILE:=$K230_VIDEO_RUNTIME_DIR/k230-video-cancel}"
: "${K230_VIDEO_IPC_SOCKET:=$K230_VIDEO_RUNTIME_DIR/k230-video.sock}"

usage() { echo "usage: k230-video-session {run|run-mvx|stop|status}" >&2; exit 2; }
pid_starttime() {
  local pid=$1 rest
  [ -r "/proc/$pid/stat" ] || return 1
  rest=$(cat "/proc/$pid/stat") || return 1
  rest=${rest#*) }
  set -- $rest
  printf '%s\n' "${20-}"
}
read_state() {
  [ -r "$K230_VIDEO_PID_FILE" ] || return 1
  IFS=' ' read -r controller_pid controller_starttime video_pid video_starttime video_owner < "$K230_VIDEO_PID_FILE" || return 1
  [ -n "${controller_pid:-}" ] && [ -n "${controller_starttime:-}" ] && [ -n "${video_pid:-}" ]
}
owned_alive() {
  read_state || return 1
  [ "$video_owner" = "${UID:-$(id -u)}" ] || return 1
  [ "$(pid_starttime "$controller_pid" 2>/dev/null || true)" = "$controller_starttime" ] || return 1
  [ "$(pid_starttime "$video_pid" 2>/dev/null || true)" = "$video_starttime" ]
}
clear_state() { rm -f "$K230_VIDEO_PID_FILE"; }
stop_owned() {
  if ! owned_alive; then clear_state; return 0; fi
  kill -TERM "$video_pid" 2>/dev/null || true
  for _ in 1 2 3 4 5 6; do
    owned_alive || { clear_state; return 0; }
    sleep 0.5
  done
  if owned_alive; then kill -KILL "$video_pid" 2>/dev/null || true; fi
  clear_state
}
validate_source() {
  local playlist_file mode
  playlist_file=${K230_VIDEO_URL_FILE:-$K230_VIDEO_RUNTIME_DIR/k230-video.playlist}
  if [ -n "$K230_VIDEO_URL_FILE" ] && [ ! -e "$playlist_file" ]; then
    echo "video URL file is absent" >&2; return 1
  fi
  if [ -e "$playlist_file" ]; then
    [ ! -L "$playlist_file" ] || { echo "video URL file must not be a symlink" >&2; return 1; }
    [ -f "$playlist_file" ] || { echo "video URL file is not regular" >&2; return 1; }
    mode=$(stat -c '%a' "$playlist_file" 2>/dev/null || true)
    [ "$mode" = 600 ] || { echo "video URL file must be mode 0600" >&2; return 1; }
    [ "$(stat -c '%u' "$playlist_file")" = "${UID:-$(id -u)}" ] || { echo "video URL file owner mismatch" >&2; return 1; }
    printf '%s\n' "$playlist_file"
  else printf '%s\n' "$K230_VIDEO_PUBLIC_URL"; fi
}
run_once() {
  local mode=$1 source=$2 geometry track app_id public_demo=0 output_log
  local -a decoder extra media_args
  case "$mode" in
    software) decoder=(--vd=h264); geometry=480x270; track=6; extra=(); app_id=k230-video-software ;;
    mvx) decoder=(--vd=h264_v4l2m2m); geometry=568x320; track=7
      extra=(--correct-pts=no --container-fps-override=30 --sws-scaler=point); app_id=k230-video-mvx ;;
    *) echo "unknown video mode: $mode" >&2; return 2 ;;
  esac
  if [[ "$source" == /* ]]; then media_args=("--playlist=$source"); else media_args=("$source"); public_demo=1; fi
  if [ "$public_demo" -eq 0 ]; then track=auto; extra=(); fi
  output_log=$K230_VIDEO_LOG
  [ "$public_demo" -eq 0 ] && output_log=/dev/null
  rm -f "$K230_VIDEO_IPC_SOCKET"
  "$K230_VIDEO_PLAYER" --no-config --vo=wlshm --profile=sw-fast --hwdec=no \
    "${decoder[@]}" --audio=no --cache=yes --demuxer-readahead-secs=30 \
    --network-timeout=10 --title=k230-video --force-window=yes \
    --geometry="$geometry" --vid="$track" --wayland-app-id="$app_id" \
    --input-ipc-server="$K230_VIDEO_IPC_SOCKET" \
    --wayland-internal-vsync=auto "${extra[@]}" "${media_args[@]}" \
    9>&- >>"$output_log" 2>&1 &
  video_pid=$!; video_starttime=$(pid_starttime "$video_pid" 2>/dev/null || true)
  if [ -z "$video_starttime" ]; then wait "$video_pid"; return $?; fi
  printf '%s %s %s %s %s\n' "$controller_pid" "$controller_starttime" "$video_pid" "$video_starttime" "${UID:-$(id -u)}" > "$K230_VIDEO_PID_FILE"
  # Bound startup only. Once mpv creates its IPC socket, healthy playback may
  # run until EOF or an explicit Stop; mpv's network timeout handles stalls.
  setsid bash -c 'exec 9>&-; for i in $(seq 1 "$1"); do [ -S "$2" ] && exit 0; sleep 1; done; printf "%s\\n" "$3" >"$4"; kill -TERM "$3" 2>/dev/null || true; sleep 2; kill -KILL "$3" 2>/dev/null || true' _ \
    "$K230_VIDEO_DEADLINE" "$K230_VIDEO_IPC_SOCKET" "$video_pid" "$K230_VIDEO_TIMEOUT_FILE" & watchdog_pid=$!
  wait "$video_pid"; local rc=$?
  kill -- "-$watchdog_pid" 2>/dev/null || kill "$watchdog_pid" 2>/dev/null || true
  wait "$watchdog_pid" 2>/dev/null || true
  if [ -r "$K230_VIDEO_TIMEOUT_FILE" ] && [ "$(cat "$K230_VIDEO_TIMEOUT_FILE")" = "$video_pid" ]; then rc=124; fi
  clear_state; return "$rc"
}
run_video() {
  mkdir -p "$K230_VIDEO_RUNTIME_DIR"; umask 077
  exec 9>"$K230_VIDEO_LOCK_FILE"
  "$K230_VIDEO_FLOCK" -n 9 || { echo "video is already starting or running" >&2; return 1; }
  if owned_alive; then echo "video is already running (pid $video_pid)" >&2; return 1; fi
  clear_state
  controller_pid=$$; controller_starttime=$(pid_starttime "$controller_pid")
  rm -f "$K230_VIDEO_TIMEOUT_FILE"
  rm -f "$K230_VIDEO_CANCEL_FILE"
  trap 'printf "%s\n" cancel >"$K230_VIDEO_CANCEL_FILE"; stop_owned; exit 143' INT TERM HUP
  local source playlist_file rc
  source=$(validate_source) || return 1
  playlist_file=${K230_VIDEO_URL_FILE:-$K230_VIDEO_RUNTIME_DIR/k230-video.playlist}
  case "$K230_VIDEO_MODE" in
    mvx)
      [ -z "$K230_VIDEO_URL_FILE" ] && [ ! -e "$playlist_file" ] || { echo "MVX mode is limited to the public demo" >&2; return 1; }
      run_once mvx "$source"; rc=$?
      if [ "$rc" -ne 0 ] && [ ! -r "$K230_VIDEO_CANCEL_FILE" ] && [ ! -r "$K230_VIDEO_TIMEOUT_FILE" ]; then run_once software "$source"; rc=$?; fi
      return "$rc" ;;
    software) run_once software "$source" ;;
    *) echo "K230_VIDEO_MODE must be software or mvx" >&2; return 2 ;;
  esac
}
case "${1:-}" in
  run) [ "$#" -eq 1 ] || usage; run_video ;;
  run-mvx) [ "$#" -eq 1 ] || usage; K230_VIDEO_MODE=mvx run_video ;;
  stop) [ "$#" -eq 1 ] || usage; printf '%s\n' cancel >"$K230_VIDEO_CANCEL_FILE"; stop_owned ;;
  status) [ "$#" -eq 1 ] || usage; owned_alive ;;
  *) usage ;;
esac
