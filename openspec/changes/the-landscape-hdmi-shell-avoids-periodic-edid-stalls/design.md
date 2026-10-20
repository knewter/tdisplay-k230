## Context

The system kernel layer owns the fix. See proposal.md and the committed holder/stage diagnostics. The pinned generic bridge detect hook always calls HDMI metadata refresh after link detection. Its EDID-read stage accounts for almost the whole170–184ms connection_mutex hold on the observed board. The helper's source contract describes status changes. `drm_kms_helper_is_poll_worker()` identifies only the actual output-poll work function and is already declared by an included header.

## Goals / Non-Goals

Avoid only the measured redundant stable-connected/cached-EDID polling path. Keep the kernel pin, driver wiring and polling periods unchanged. Preserve landscape1280x800 normal scale1 and the max_render_time8 guard. Do not close the separate portrait change or alter its nine gates.

## Decisions

Guard the HDMI refresh call with the narrow exception: current context is the polling worker, both previous/new status are connected, and connector->edid_blob_ptr is non-null. Keep the bridge detect callback and HPD notification outside that exception. Missing cached EDID still retries discovery. Non-poll detection always retains refresh, even with unchanged status/cache: HPD handling can set connector->status before a later detect, so a blanket same-status guard would regress that path. Requested get_modes and force implementations stay byte-identical.

Add an applyPatches patch in the mainline DRM kernel source derivation. Test the actual patched C detect function against72 old/new-status x poll-context x HDMI-presence x cached-EDID cases with stub callbacks, checking returned status, detection/refresh/notification counts. Preserve the HPD/force/mode functions byte-for-byte. These are host semantic/source checks, not kernel runtime or physical proof; cross-build the actual NixOS kernel and closure separately.

Reuse the isolated function-only recorder (fresh smoke on the candidate) and exact workload collector for one untraced and one traced24-drag run. Require864 complete input/present joins per run, qualified mono clock/count/loss/cleanup, >=3 complete polling cycles, no stable-cycle EDID-reader markers and no >100ms poll-held interval. Report all input tails and any unrelated remaining stall honestly; do not weaken the gate or run unbounded retries. A fix-specific report will preserve distinct old/candidate kernel/system/boot/process identities and exact matching output/workload instead of pretending the reboot was the same process.

## Risks / Trade-offs

An old EDID cache must not prevent initial or explicitly requested refresh: cached-blob and polling-context guards plus the72-case matrix limit that risk; physical unplug/replug is still required. Cross-build success does not identify the running kernel. Tie candidate Image/DTB/initrd hashes, fresh boot identity, serial boot transcript and running/booted system/kernel evidence together. Keep raw serial/network/monitor data protected; publish allowlisted/redacted records and exact hashes. No runtime secrets enter Git or ad-hoc configuration paths.

The installed bundle identity names `k230-mainline-drm-shell-landscape-hdmi`.
Use that exact profile for both configured kernel and full closure. The first
cached build of default k230 resolved to the vendor6.6 kernel and is retained
as rejected target proof, not a successful candidate build.

## Migration Plan

Land proposal and proved source early. Use the one heavy-build slot for kernel then system closure. Before touching boot, reserve the board and inspect current image/boot hashes and recovery paths, preserve the known-good bundle, and stage a recoverable candidate without overwriting the only fallback. Record exact deployment commands/artifacts. Obtain a fresh serial-observed candidate boot and normal shell/landscape state, then bounded timing/gesture and physical cable/input proof. Roll back to the preserved normal if boot/runtime controls fail; keep failures in evidence. Promote persistent normal boot only after named candidate checks and operator physical acceptance, and verify its ordinary boot. Until physical proof exists, keep those tasks and UNVERIFIED markers open. Validate/delta-sync/archive/push only when every task and proof is complete.
