#!/usr/bin/env bash
# Run ON the reserved board. The coordinator alone owns its console.
set -euo pipefail
umask 077
runtime=${K230_CARD_RUNTIME:-/run/k230-card-composition}
unit=k230-card-composition-probe.service
user=${K230_CARD_USER:-shell}
duration=${K230_CARD_DURATION:-120}
jq_bin=${K230_CARD_JQ:-jq}
usage() { echo 'usage: card-composition-board-session.sh --probe /nix/store/.../bin/card-composition-probe --restore-shell | --restore-shell | --collect | --verify-restored' >&2; exit 64; }
[[ $# -gt 0 ]] || usage
mode=$1; shift
if [[ ! -d $runtime ]]; then mkdir -p "$runtime"; chmod 700 "$runtime"; fi
log=$runtime/session.jsonl
# Collection may read a running session. Every mutating operation is exclusive.
if [[ $mode != --collect ]]; then
    exec 9>"$runtime/operator.lock"
    flock -n 9 || { echo 'card session already reserved' >&2; exit 75; }
fi
log_event() { printf '{"event":"%s","uptime_s":%s}\n' "$1" "$(cut -d' ' -f1 /proc/uptime)" >>"$log"; }
verify() {
    systemctl is-active --quiet shell || return 1
    systemctl is-active --quiet seatd || return 1
    if systemctl is-active --quiet "$unit"; then return 1; fi
    log_event normal_services_active
    # Apps, keyboard, terminal, touch and normal renderer need operator proof.
}
restore() {
    # Stop waits for the complete transient cgroup, including both test clients.
    if systemctl show "$unit" --property=LoadState --value 2>/dev/null | grep -qx loaded; then
        systemctl stop "$unit" || return 1
    fi
    if systemctl is-active --quiet "$unit"; then return 1; fi
    if ! systemctl is-active --quiet shell && pgrep -x sway >/dev/null; then
        log_event competing_sway_prevents_restore
        return 1
    fi
    systemctl reset-failed "$unit" 2>/dev/null || true
    systemctl start shell || return 1
    verify || return 1
    log_event shell_restored
}
collect() {
    test -r "$log"
    # Positive field allowlist: never copy arbitrary journal strings, paths,
    # environment, titles, network state or key contents into shared evidence.
    "$jq_bin" -c 'with_entries(select(.key | IN("event","uptime_s","cpu_ns","memory_bytes","compositor_cpu_seconds","compositor_rss_bytes")))' "$log"
    for file in "$runtime"/session/client-{one,two}.jsonl; do
        [[ -r $file ]] || continue
        "$jq_bin" -c 'select(.app_id == "k230.card.one" or .app_id == "k230.card.two") | with_entries(select(.key | IN("event","app_id","elapsed_ms","frames","callbacks","releases","child_frames","child_callbacks","child_releases","callback_age_ms","child_callback_age_ms","max_callback_gap_ms","child_max_callback_gap_ms","width","height","stride","format","subsurface","presentation","key_presses")))' "$file"
    done
    if [[ -r $runtime/invocation ]]; then
        invocation=$(cat "$runtime/invocation")
        [[ $invocation =~ ^[a-f0-9]{32}$ ]] || return 1
        journalctl "_SYSTEMD_INVOCATION_ID=$invocation" --no-pager -o cat -n 10000 |
          head -c 8388608 >"$runtime/compositor.log" || true
    fi
    if [[ -r $runtime/compositor.log ]]; then
        # Only the source-audited K230_CARD grammar, never surrounding journal.
        sed -n 's/.*K230_CARD /K230_CARD /p' "$runtime/compositor.log" |
          grep -E '^K230_CARD (map|buffer-reference|mirror-release|attached|dragging|selected-expanded|dismissal-requested|close-refused|app-exit|unmap|focus-restored|restored|live)( (card|container|format|width|height|stride|owner|cards|renderer|source|contact|basis|keyboard|reason|commits|samples|sampled|frame-done|output-presented|input)=[A-Za-z0-9_.:-]+)*$' || true
    fi
    printf '%s\n' '{"event":"evidence_limits","class":"board-session-telemetry","renderer_requested":"pixman","client_format":"XRGB8888","physical_touch":"UNVERIFIED","normal_apps_keyboard_terminal":"UNVERIFIED","frame_callback_is_presentation":false}'
}
case "$mode" in
    --probe)
        [[ $# == 2 && $2 == --restore-shell ]] || usage
        probe=$1
        client=${K230_CARD_CLIENT:-$(dirname "$probe")/card-composition-probe-client}
        keyboard=${K230_CARD_KEYBOARD:-}
        # Paths enter Sway exec config: reject whitespace and shell metacharacters.
        for path in "$probe" "$client" "$runtime"; do
            [[ $path =~ ^/[A-Za-z0-9_./-]+$ ]] || usage
        done
        [[ -z $keyboard || $keyboard =~ ^/[A-Za-z0-9_./-]+$ ]] || usage
        [[ $duration =~ ^[0-9]+$ && $duration -ge 1 && $duration -le 600 ]] || usage
        test -x "$probe"; test -x "$client"
        [[ -z $keyboard ]] || test -x "$keyboard"
        systemctl is-active --quiet shell
        systemctl is-active --quiet seatd
        rm -f "$runtime/invocation" "$runtime/compositor.log" \
          "$runtime/session/client-one.jsonl" "$runtime/session/client-two.jsonl"
        : >"$log"
        log_event reservation_acquired
        # Register restoration before stop so interruption cannot strand shell.
        cleanup() {
            result=$?
            trap - EXIT INT TERM
            if ! restore; then log_event restore_failed; result=1; fi
            exit "$result"
        }
        trap cleanup EXIT
        trap 'exit 130' INT
        trap 'exit 143' TERM
        systemctl stop shell
        [[ $(systemctl show shell --property=MainPID --value) == 0 ]]
        if pgrep -x sway >/dev/null; then
            log_event competing_sway_detected
            exit 1
        fi
        log_event normal_shell_stopped
        # This directory survives shell RuntimeDirectory cleanup on stop/start.
        install -d -m 0700 -o "$user" -g "$user" "$runtime/session"
        chmod 711 "$runtime"
        config=$runtime/session/sway.conf
        cat >"$config" <<CONFIG
output * bg #17202b solid_color
output * scale 1
# Sway's selector is per-channel depth; 6 selects RGB565 on this board.
output * render_bit_depth 6
input type:touch map_to_output DSI-1
seat seat0 hide_cursor 100
for_window [app_id="^k230.card.(one|two)$"] floating enable, border none, resize set 520 1040, move position 24 48
exec $client --app-id k230.card.one --duration $duration > $runtime/session/client-one.jsonl
exec $client --app-id k230.card.two --duration $duration --refuse-close > $runtime/session/client-two.jsonl
CONFIG
        if [[ -n $keyboard ]]; then printf 'exec %s\n' "$keyboard" >>"$config"; fi
        chmod 644 "$config"
        log_event opt_in_starting
        # systemd owns all descendants; no second DRM owner can survive cleanup.
        systemd-run --unit="$unit" --property=Type=exec \
          --property=Conflicts=shell.service --property=After=shell.service \
          --property=StandardOutput=journal --property=StandardError=journal \
          --property=LogRateLimitIntervalSec=30s --property=LogRateLimitBurst=2000 \
          --property="User=$user" --property="Group=$user" \
          --property=KillMode=control-group --property=TimeoutStopSec=10 \
          --property="RuntimeMaxSec=$((duration+15))" \
          --property=CPUAccounting=yes --property=MemoryAccounting=yes \
          --setenv="XDG_RUNTIME_DIR=$runtime/session" --setenv=XDG_SEAT=seat0 \
          --setenv=LIBSEAT_BACKEND=seatd --setenv=WLR_RENDERER=pixman \
          --setenv="SWAYSOCK=$runtime/session/sway-ipc.sock" \
          "$probe" --sway --verbose --config "$config"
        invocation=$(systemctl show "$unit" --property=InvocationID --value)
        [[ $invocation =~ ^[a-f0-9]{32}$ ]]
        printf '%s\n' "$invocation" >"$runtime/invocation"
        # Report cgroup totals separately from Sway CPU seconds and RSS.
        deadline=$((SECONDS+duration))
        while systemctl is-active --quiet "$unit"; do
            if (( SECONDS >= deadline )); then
                log_event bounded_session_stop
                systemctl stop "$unit"
                break
            fi
            cpu=$(systemctl show "$unit" --property=CPUUsageNSec --value 2>/dev/null || true)
            memory=$(systemctl show "$unit" --property=MemoryCurrent --value 2>/dev/null || true)
            if [[ $cpu =~ ^[0-9]+$ && $memory =~ ^[0-9]+$ ]]; then
                printf '{"event":"resources","uptime_s":%s,"cpu_ns":%s,"memory_bytes":%s}\n' "$(cut -d' ' -f1 /proc/uptime)" "$cpu" "$memory" >>"$log"
            fi
            if read -r process_cpu rss_kib < <(ps -C sway -o cputimes=,rss=) &&
                [[ $process_cpu =~ ^[0-9]+$ && $rss_kib =~ ^[0-9]+$ ]]; then
                printf '{"event":"compositor_resources","uptime_s":%s,"compositor_cpu_seconds":%s,"compositor_rss_bytes":%s}\n' "$(cut -d' ' -f1 /proc/uptime)" "$process_cpu" "$((rss_kib * 1024))" >>"$log"
            fi
            sleep 1
        done
        if systemctl is-failed --quiet "$unit"; then log_event opt_in_failed; exit 1; fi
        ;;
    --restore-shell) [[ $# == 0 ]] || usage; restore ;;
    --collect) [[ $# == 0 ]] || usage; collect ;;
    --verify-restored) [[ $# == 0 ]] || usage; verify ;;
    *) usage ;;
esac
