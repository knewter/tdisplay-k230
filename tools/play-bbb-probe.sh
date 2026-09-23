#!/usr/bin/env bash
# Run as the shell user inside its Wayland session, with a built target mpv path.
# This is a bounded public-media diagnostic, not the integrated player UI.
set -euo pipefail
mpv_path=${1:?usage: play-bbb-probe.sh /path/to/mpv [software|mvx]}
mode=${2:-software}
case "$mode" in
  software)
    size='480 270'; geometry=480x270; track=6
    decoder=(--vd=h264)
    ;;
  mvx)
    size='568 320'; geometry=568x320; track=7
    # Known 30-fps silent clip only: MVX timestamp correctness remains open.
    decoder=(--vd=h264_v4l2m2m --correct-pts=no --container-fps-override=30 --sws-scaler=point)
    ;;
  *) echo 'mode must be software or mvx' >&2; exit 2 ;;
esac
swaymsg 'for_window [title="k230-video-probe"] floating enable, border none, resize set '"$size"', move position center' >/dev/null
exec timeout --signal=TERM --kill-after=3s 90s "$mpv_path" --no-config --vo=wlshm --profile=sw-fast --hwdec=no \
  "${decoder[@]}" --audio=no --cache=yes --demuxer-readahead-secs=30 \
  --start=45 --length=30 --title=k230-video-probe --force-window=yes \
  --geometry="$geometry" --vid="$track" --wayland-internal-vsync=auto \
  --term-status-msg='pos=${time-pos} fps=${estimated-vf-fps} decoder_drop=${decoder-frame-drop-count} vo_drop=${frame-drop-count} cache=${demuxer-cache-duration}' \
  https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd
