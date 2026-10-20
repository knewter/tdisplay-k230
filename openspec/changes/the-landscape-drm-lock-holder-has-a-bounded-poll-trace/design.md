## Context

See proposal.md. Prior evidence: `docs/evidence/landscape-drm-wait/README.md`. Running kernel source `/nix/store/7vzlvixrdhv5a1iw75p18yzwkaqrlxjd-linux-mainline-k230-drm-src/drivers/gpu/drm/drm_probe_helper.c` has been read: `output_poll_execute` calls `drm_helper_probe_detect`; `drm_helper_probe_detect_ctx` locks `connection_mutex`, enters `detect_connector_status` on success, and subsequently calls `drm_modeset_drop_locks`. Atomic connector state acquisition uses that same device connection mutex. Preflight in `docs/evidence/landscape-drm-holder/preflight/` confirms selected functions are traceable on the unchanged board.

## Goals / Non-Goals

Measure the polling worker's source-grounded held-lock interval, and its overlap with shell DRM waits. Keep source221/j30, original DEBUG process, one idle Foot and 1280x800 normal scale1 unchanged. No persistent defaults or runtime polling-disable experiment.

## Decisions

Use an exclusive owned tracefs instance with mono clock, existing target-PID scheduler/raw-syscall filters, and function tracer filtered to `output_poll_execute`, `drm_helper_probe_detect_ctx`, `detect_connector_status`, `lt9611_bridge_detect`, `drm_modeset_backoff`, and `drm_modeset_drop_locks`. Track worker PID and function order. The interval from detect entry to drop-lock entry is a conservative held-lock interval, rather than an exact acquisition/release timestamp. A backoff, ambiguous/multiple detection, missing boundary, or absent bridge marker disqualifies that interval. Do not infer ownership from the task scheduled after Sway or overlap alone.

Prefer selected function entries over full function graphs to reduce volume and avoid unnecessary call/return arguments. Do not enable named syscall events that capture user buffers. Public records contain timestamps, scalar IDs, and allowlisted symbols only; raw pointers, task names, arguments and raw traces remain private with recorded hashes.

Use 32MiB CPU0 ring, <=64MiB total/export limits and >=128MiB available-memory gate. Arm an independent 600s cleanup timer before mutation; verify inode, event filters, function filter and tracer ownership before cleanup, remove only owned controls/instance, and preserve global hashes. Require zero overrun/commit-overrun/drops, exact numeric+function ring count, qualified monotonic markers, complete 864-input joins and ordered function streams.

## Risks / Trade-offs

Instrumentation changes timing: pair one untraced and one instrumented 24-drag workload and report both. Permit at most one extra instrumented workload if the first has no >100ms input. No late sample is an inconclusive result, not permission for an unbounded retry. First qualify a short idle-board smoke that records at least one complete poll/detect/bridge/drop interval plus main-process scheduler records; cap idle observation at 25s. If unsupported or ambiguous, retain rejection and keep its evidence gate open.

Symbol-only tracing cannot identify mutex addresses or distinguish multiple DRM devices without runtime/source grounding. Check unchanged single active HDMI output and source driver path; qualify claims accordingly. It does not show what consumes time inside detection; I2C remains unmeasured unless a later probe establishes it.

## Migration Plan

Land plan, then host-tested source; run qualified smoke before bounded trial. Restore Home and verify owned instance/timer absence, global controls, services, idle workload, runtime/image/output identity and no virtual inputs. Publish evidence and exact CI/Pages revision; archive only after named proofs exist. No image deployment required.
