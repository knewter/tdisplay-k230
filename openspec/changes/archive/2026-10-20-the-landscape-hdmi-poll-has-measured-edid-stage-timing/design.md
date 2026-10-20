## Context

See proposal.md and `docs/evidence/landscape-drm-holder/README.md`. Read pinned kernel source `/nix/store/7vzlvixrdhv5a1iw75p18yzwkaqrlxjd-linux-mainline-k230-drm-src`: `drivers/gpu/drm/display/drm_bridge_connector.c` detection calls the HDMI hotplug helper; `drivers/gpu/drm/display/drm_hdmi_state_helper.c` HDMI update calls its EDID reader immediately before `drm_edid_connector_update`; the patched LT9611 EDID callback reads DDC blocks. No duration is inferred from source. Preflight confirms required functions on kernel7.3.0-rc5 and unchanged landscape PID77507/source221/j30.

## Goals / Non-Goals

Measure kernel detection stages while idle. Preserve existing DEBUG process, source, installed/persistent system, one idle Foot/color follower, and HDMI1280x800 normal scale1. Do not alter hotplug or claim a latency improvement from idle tracing.

## Decisions

Use an owned tracefs instance, mono clock, and selected function entries only. No scheduler/raw-syscall events or gestures are needed to identify the slow stage. A one-MiB CPU0 ring (<=8MiB total/raw/public export; >=128MiB available memory) bounds overhead/storage. Exact ring entries must equal exported records, all loss counters must be zero, and markers must lie in their recorded time.monotonic_ns brackets. Export only timestamps, scalar PIDs/CPU and allowlisted symbols/callers; raw text/addresses/task names and EDID contents remain private.

Reuse source-grounded polling detect-to-drop-lock intervals and caller-order guards, including compiled helper inlining and multiple connectors. Within each complete probe, qualify the EDID stage only when the HDMI helper path, connector EDID-reader entry, LT9611 EDID callback/block markers and subsequent connector-update entry occur in order on the same worker. Measure detect-to-reader, reader-to-connector-update, and update-to-drop entries. Reader-to-update includes wrappers, validation and return overhead: it is not exact exclusive function/I2C time. lt9611_read_edid is not separately traceable in this compiled kernel; do not invent its return marker or individual transaction durations. Reject ambiguous/repeated or incomplete stage boundaries.

Smoke uses only hrtimer_nanosleep tracing and a bracketed 50ms controller sleep. Require its sleep entry inside that bracket, matching source/kernel/system, qualified clock/count/loss and complete cleanup before the main run. Then perform exactly one 35s idle observation requiring >=3 complete EDID stage intervals. Preserve any rejection/inconclusive capture and leave its gate open, rather than extending trial count or weakening checks.

Arm an independent 600s cleanup timer before mutation. Verify owned inode, filter and tracer before stopping/removing only the owned instance; compare root controls, function/graph filters and options hashes before/after. Check unchanged runtime/output/idle/services before and after. No board queries/copies during recording. Preserve actual exit statuses and raw/source hashes.

## Risks / Trade-offs

Instrumentation and scheduling are included. Report within-trace stage shares and observed cycles; no uninstrumented per-stage calibration or new workload latency proof. Prior late-input evidence remains separate. Symbols do not expose mutex addresses or per-probe connector IDs. Inline helpers require explicitly source-grounded caller variants; retain all rejections.

## Migration Plan

Land plan then host-tested source. Qualify smoke, record single observation, strictly export, verify normal state/release board. Commit analysis, verify CI/exact Pages, archive only after all named proofs are committed. No system deployment.
