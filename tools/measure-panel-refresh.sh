#!/usr/bin/env sh
# Read-only board measurement for the-card-deck-still-misses-its-frame-budget.
#
# Companion to docs/evidence/card-shell/frame-budget/analysis.md, which lists
# the ranked hypotheses for the ~57.48ms tracking-presentation interval and
# what each possible result of this script means for the decision (accept
# the measured cadence, fix the canaan-drm driver, or keep optimizing the
# Pixman path). Collects, in one pass:
#
#   1. the currently programmed DSI/VO mode timing (read back from the
#      kernel, not the device tree source);
#   2. the VO vblank IRQ's raw firing rate over a fixed window, from
#      /proc/interrupts;
#   3. a distribution of real DRM vblank sequence numbers and kernel
#      timestamps, via tools/panel-refresh-probe (DRM_IOCTL_WAIT_VBLANK
#      only -- see nix/panel-refresh-probe.c for exactly which ioctls it
#      issues and why none of them can change what is on the glass);
#   4. whatever the generic DRM core debugfs already exposes (crtc/connector
#      state, if debugfs happens to be mounted) -- canaan-drm registers no
#      debugfs files of its own (checked against the pinned kernel source),
#      so this section is best-effort and commonly empty.
#
# It deliberately does NOT attempt to reproduce Sway's presentation-feedback
# numbers: docs/evidence/card-shell/board-cost/{long-trace,short-trace}/
# telemetry.log and tools/card-shell-benchmark.py already capture that (the
# 'present' events, K230_CARD_BENCH schema) for both an idle desktop and a
# scripted card_shell drag. Run that harness alongside this script rather
# than duplicating it; docs/evidence/card-shell/frame-budget/analysis.md's
# command list shows both invocations together.
#
# Run ON the board, at a root shell (same pattern as
# tools/board-inventory-probe.sh -- it reads local /proc, /sys and runs
# local commands; it is not a serial wrapper). The coordinator gets it and
# tools/panel-refresh-probe there with tools/push-file.py, then captures
# this script's output over the console with tools/capture-boot.py, exactly
# as docs/evidence/card-shell/frame-budget/analysis.md's command list shows.
#
# STRICTLY READ-ONLY. It never:
#   - performs a modeset, atomic commit, or page flip (the probe binary
#     issues only DRM GET* ioctls and a non-signalling, non-flip
#     DRM_IOCTL_WAIT_VBLANK; see nix/panel-refresh-probe.c)
#   - writes a sysfs or debugfs attribute
#   - loads or unloads a kernel module
#   - resets, suspends, or power-cycles anything
#
# MEASURE_PANEL_REFRESH_ROOT redirects the /proc and /sys walks to a
# synthetic tree for the host-side fixture test,
# tools/test-measure-panel-refresh.sh (same pattern as
# tools/test-board-inventory-probe.sh). MEASURE_PANEL_REFRESH_PROBE
# overrides the probe binary path (default /tmp/panel-refresh-probe, where
# push-file.py drops it). MEASURE_PANEL_REFRESH_SECONDS overrides the
# /proc/interrupts sampling window (default 5s). MEASURE_PANEL_REFRESH_COUNT
# overrides the number of vblank samples the probe collects (default 120,
# about 2.3s at ~52.19Hz).
set -eu

root=${MEASURE_PANEL_REFRESH_ROOT:-/}
probe=${MEASURE_PANEL_REFRESH_PROBE:-/tmp/panel-refresh-probe}
seconds=${MEASURE_PANEL_REFRESH_SECONDS:-5}
count=${MEASURE_PANEL_REFRESH_COUNT:-120}
card=${MEASURE_PANEL_REFRESH_CARD:-/dev/dri/card0}
path() { printf '%s%s' "$root" "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

printf 'PANEL_REFRESH v=1 event=probe_start tool=measure-panel-refresh.sh\n'
printf 'PANEL_REFRESH v=1 event=captured_utc value=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'PANEL_REFRESH v=1 event=source_root value=%s\n' "$root"

# --- 1. currently programmed mode, read back from the kernel -------------
# modetest issues only GETRESOURCES/GETCONNECTOR/GETCRTC-shaped queries in
# this mode (-c lists connectors and their current mode; it never sets one).
# Kept as human-readable cross-check text, tagged so the parser can skip it;
# tools/panel-refresh-probe's own event=mode line below is the parsed source
# of truth because its ioctls are explicit and reviewed line by line.
printf '\n== modetest -c (informational only; not machine-parsed) ==\n'
if have modetest; then
  modetest -c 2>&1 | sed 's/^/PANEL_REFRESH_RAW modetest: /'
else
  printf 'PANEL_REFRESH v=1 event=note text=modetest-unavailable\n'
fi

# --- 2. VO vblank IRQ firing rate, from /proc/interrupts ------------------
# The VO platform device is vo@90840000 in the pinned device tree
# (arch/riscv/boot/dts/canaan/k230.dtsi); devm_request_irq() in
# drivers/gpu/drm/canaan/canaan_vo.c names the IRQ dev_name(dev), which for
# a platform device is its DT node name, "90840000.vo". Match case
# insensitively and fall back to any line mentioning "canaan" or "vo" so a
# kernel version that names it differently still gets flagged, not silently
# skipped.
printf '\n== VO vblank IRQ rate ==\n'
interrupts=$(path /proc/interrupts)
if [ -r "$interrupts" ]; then
  line=$(grep -i '90840000\.vo\|canaan.*vo\|vo.*canaan' "$interrupts" | head -1 || true)
  if [ -z "$line" ]; then
    printf 'PANEL_REFRESH v=1 event=note text=vo-irq-line-not-matched\n'
    printf 'PANEL_REFRESH_RAW interrupts-unmatched-table:\n'
    sed 's/^/PANEL_REFRESH_RAW interrupts: /' "$interrupts"
  else
    irq=$(printf '%s' "$line" | awk '{print $1}' | tr -d ':')
    before=$(printf '%s' "$line" | awk '{for(i=2;i<=NF;i++){if($i ~ /^[0-9]+$/) s+=$i; else break} print s}')
    printf 'PANEL_REFRESH v=1 event=irq_sample phase=before irq=%s count=%s t_unix=%s\n' \
      "$irq" "$before" "$(date +%s)"
    sleep "$seconds"
    line2=$(grep -i '90840000\.vo\|canaan.*vo\|vo.*canaan' "$interrupts" | head -1 || true)
    after=$(printf '%s' "$line2" | awk '{for(i=2;i<=NF;i++){if($i ~ /^[0-9]+$/) s+=$i; else break} print s}')
    printf 'PANEL_REFRESH v=1 event=irq_sample phase=after irq=%s count=%s t_unix=%s window_seconds=%s\n' \
      "$irq" "$after" "$(date +%s)" "$seconds"
  fi
else
  printf 'PANEL_REFRESH v=1 event=note text=proc-interrupts-unreadable\n'
fi

# --- 3. real vblank sequence/timestamp samples -----------------------------
printf '\n== vblank samples (tools/panel-refresh-probe) ==\n'
if [ -x "$probe" ]; then
  "$probe" "$card" "$count"
else
  printf 'PANEL_REFRESH v=1 event=note text=probe-unavailable path=%s\n' "$probe"
  printf 'PANEL_REFRESH v=1 event=note text=push-it-first-see-analysis-md\n'
fi

# --- 4. generic DRM core debugfs, best-effort ------------------------------
# canaan-drm registers no debugfs files of its own (grep -rl debugfs
# drivers/gpu/drm/canaan/ against the pinned kernel source returns nothing),
# so this is only whatever drm_debugfs_init's generic per-minor files show
# (connector/crtc "state" dumps of DRM's cached atomic state, not live
# hardware registers) -- and only if CONFIG_DEBUG_FS's mountpoint happens to
# already be mounted. This script never mounts it.
printf '\n== DRM debugfs (best-effort; canaan-drm has none of its own) ==\n'
dridbg=$(path /sys/kernel/debug/dri)
if [ -d "$dridbg" ]; then
  find "$dridbg" -maxdepth 3 -type f 2>/dev/null | sort | while IFS= read -r f; do
    rel=${f#"$root"}
    if [ -r "$f" ]; then
      printf 'PANEL_REFRESH v=1 event=debugfs path=%s\n' "$rel"
      sed "s|^|PANEL_REFRESH_RAW debugfs $rel: |" "$f" 2>/dev/null || true
    fi
  done
else
  printf 'PANEL_REFRESH v=1 event=note text=debugfs-dri-not-mounted\n'
fi

printf '\nPANEL_REFRESH v=1 event=probe_end\n'
