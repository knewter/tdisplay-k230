# Stable connected HDMI polling fix

The source guard is implemented and host semantics pass:72 matrix cases,
seven named discovery/retry/HPD/disconnect/reconnect scenarios and five
connector fallback cases. The actual patched C detector was compiled with
stub kernel callbacks; HPD handling, force and get_modes_edid functions are
byte-identical. `host/semantic-matrix.json` records source, patch and helper
hashes. No target build or hardware result is inferred from this check.

The patch skips HDMI refresh only when execution is in the polling worker,
old/new status are connected and cached EDID exists. Link detection and HPD
notification still run. All non-polling, missing-cache and transition cases
retain refresh. Nix wires the patch into the mainline DRM source derivation.

UNVERIFIED: configured kernel/system cross-build, candidate boot/timing,
fresh physical cable/input qualification and persistent promotion remain
open. Current landscape and separate portrait hardware gates are preserved.
The preceding committed holder/EDID-stage diagnostics ground the problem,
not an unperformed candidate result.

The initial default-k230 build exited0 from cache but resolved to vendor6.6,
so it is explicitly REJECTED_TARGET and proves nothing about this patch.
`host/rejected-vendor-target/` retains the command/result. The installed
bundle identifies `k230-mainline-drm-shell-landscape-hdmi`; corrected
builds use that profile. No candidate has been deployed.

`tools/hdmi-stable-poll-proof.py` provides the bounded candidate recorder
and separate report. Its host fixtures pass (see `host/recorder-check.json`);
this is preparation, not completion of task2.2. It requires a fresh function
smoke tied to the candidate boot/controller, explicit running system,
preserved persistent fallback and executable identities. It collects exactly
one untraced/traced24-drag pair, checks864 joins each, retains all >100ms
input samples, and separately qualifies >=3 complete polling cycles without
EDID-reader markers or >100ms source-grounded held intervals. It checks
trace clock/count/loss/cleanup and all nine root tracing control hashes.
Incomplete boundary probes remain explicit. No retries or native/glass claim.

Preflight at2026-10-20T18:02:27Z verified the unchanged installed7.3 image,
normal HDMI geometry/flags, services and idle Foot. `preflight/` records all
boot-file hashes, the protected on-board known-good backup and the exact
backup command. `/run/current-system` and the persistent profile are j30y,
while `/run/booted-system` still names cmdvr from an earlier boot. This is
recorded explicitly; the new candidate needs its own serial-observed boot.
No boot file or profile was changed by backup/preflight.
