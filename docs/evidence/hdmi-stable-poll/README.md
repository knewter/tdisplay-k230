# Stable connected HDMI polling fix

The accepted kernel is persistently installed and verified through ordinary boot. [Current installation and cleanup result](persistent/summary.json) ties the actual kernel build ID, fresh boot, exact installed system, preserved rollback and normal landscape controls together. [Operator acceptance](physical-a/operator-acceptance.json) is separate from the injected timing evidence. The dated stages below retain the unsuccessful attempts and original qualification limits.

## Source and host semantics

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

Physical cable/input behavior is now accepted and persistent ordinary boot is
verified in the named records below. Landscape is retained. The separate portrait
hardware gates remain open. The preceding holder/EDID-stage diagnostics ground
the problem; candidate results retain their distinct evidence classes.

The initial default-k230 build exited0 from cache but resolved to vendor6.6,
so it is explicitly REJECTED_TARGET and proves nothing about this patch.
`host/rejected-vendor-target/` retains the command/result. The installed
bundle identifies `k230-mainline-drm-shell-landscape-hdmi`; corrected
builds use that profile; deployment and its fresh boot are recorded separately below.

`tools/hdmi-stable-poll-proof.py` provides the bounded candidate recorder
and separate report. Its host fixtures pass (see `host/recorder-check.json`);
these fixtures prove the recorder only; the candidate board pair is recorded
separately below. The recorder requires a fresh function
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
recorded as a historical preflight. The later SSH boot route superseded the
serial prerequisite; no UART boot observation is claimed.
No boot file or profile was changed by backup/preflight.

The actual configured7.3 mainline kernel cross-build passed at18:13:12Z
from source19568595 in1102.482seconds. `host/mainline-kernel/` records the
command, successful exit, derivation and Image/System.map identities.
`host/mainline-source.json` verifies that the realized Nix bridge source
and patch exactly match the host semantic matrix. The new kernel output
is `/nix/store/21lz5c6pkk329c0xcac9bzlx40dplrlk-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
At cross-build time no candidate boot or physical acceptance had yet been obtained.

The full landscape system and coherent boot-bundle builds passed at18:16:14Z
and18:16:35Z. `host/mainline-system/` preserves both commands/results and
complete bundle inspection, including the narrow inspector allowlist variant.
The matching candidate system is hpmzja32; its42,752,512-byte Image has SHA256
`d6b2153d97ac8382b5329c64397b8b46435e6a423b16796f8c37e052d4bcd642`.
The evaluated Sway wrapper still selects3vk3p0ps and the exact ila85 config
(SHA575fa8d1), matching the installed compositor/config. Build source19568595
identifies the candidate kernel/system input; the reused compositor binary
remains the previously qualified221bbcf3 artifact. No runtime proof follows
from these successful builds.

Boot attemptA is REJECTED_WRONG_SERIAL_DEVICE. The historical ttyACM0 now
leads to an unrelated Linux USB gadget; only whitespace was sent there.
K230 was rebooted only through its protected SSH alias and returned to the
known-good j30y system/profile (bootID914f8346). The candidate was never
selected. The remaining CP2102N serial candidate fails to open with EIO;
no host serial input or K230 marker was sent through that failed port.
`boot-attempt-a/` retains the staging/copy/boot commands, failure, recovery
and private-source hashes. Candidate checksums and preserved boot-file
checks passed; no boot file/profile was modified. An identified, working
K230 UART would have been required for that serial retry. At this historical
stage the boot/runtime/physical/promotion gates were incomplete; the later
SSH method superseded the serial prerequisite and obtained separate proof.

At18:30:46Z a fresh protected query verified recovered normal controls:
current/booted/persistent system all j30y; PID1076 with unchanged executable,
config, debug flags and landscape1280x800@59.91normal/scale1; idle Foot,
both shell services active, zero virtual test devices and no trace instances.
See `boot-attempt-a/recovered-normal.json`. This is recovery/runtime-state
proof on the original image, not a boot or timing result for the candidate.
The prepared serial retry driver required a fresh K230 nonce on an explicit
by-id UART. It was not used for the later SSH-only boot route.

The user clarified that SSH should be used rather than requiring a USB
data cable. `ssh-boot/` records an unchanged-image load/unload qualification
of the existing RV64 kexec_file_load API. First flags0 failed errno99;
existing NO_CMA flag16 passed. Both attempts retain all normal controls and
leave kexec_loaded0. The plan now uses a one-time SSH-controlled kernel
boot plus fresh boot/kernel-build-ID/boot-journal evidence. The rejected
UART attempt stays rejected; no UART observation is claimed. Boot, timing,
physical and persistent gates were not passed by that load/unload probe;
their later actual checks are recorded below.

At18:58:31Z the one-time SSH boot is VERIFIED: new bootIDc17ee483,
current/booted systemhpmzja32, persistent profilej30y, and running GNU
kernel build ID7a61d8cea3e26df94695189b766de3fd66fa6860 exactly matches
the built vmlinux and a unique GNU note in candidate Image (absent from
original Image). `ssh-boot/` preserves commands, load/shutdown request,
transport disconnect255, fresh SSH observation and allowed kernel journal
lines. The transport disconnect itself is not boot proof. No UART log is
claimed. During this one-time trial all five normal boot files remained
unchanged and ordinary reset still selected the original system; the later
persistent installation below changed that selection after acceptance.

Fresh candidate controls retain compositor9464072a/config575fa8d1, DEBUG
flags, onlyCPU0, idle Foot, both services active and normal1280x800@59.91
scale1 output. Numeric PID1076 is reused across the reboot; distinct boot
IDs and kernel build IDs distinguish the processes. Fresh function smoke
qualified4 records and cleanup; actual bounded motion/physical/promotion
gates remain separate. The kernel trial needs no USB data cable.

The single24-drag untraced/traced candidate pair qualifies. `timing/`
commits all864 complete input/presentation joins per run, manifests, numeric
function export, raw-source hash, reports and exact commands. Six complete
poll cycles occur within the57.665-second traced motion span, with zero
EDID reader/callback markers and maximum conservative held interval0.753ms.
All5418 exported records match the ring count, with zero loss. No interval
was rejected. The owned trace/timer was removed, all nine root tracing
control hashes match, Home/benchmark-stop succeeded, both services are
active, idle Foot is unchanged and no test devices remain.

| Observation | p95 ms | p99 ms | max ms | >100ms / samples |
| --- | ---: | ---: | ---: | ---: |
| Original untraced |27.331278|45.781325|208.049997|1/864|
| Candidate untraced |37.920418|45.766998|47.456531|0/864|
| Candidate function-traced |25.959442|40.229160|46.961216|0/864|

The compositor/config/flags/output and injected collector/workload match the
original untraced capture. Kernel/system/boot/process identities differ
and are preserved; original traced runs also had syscall/scheduler tracing,
so their instrumentation differs. The earlier function-only idle diagnostic
measured170–184ms holds with EDID reads; this candidate observes no reread
and short holds during motion. Candidate p95 is not uniformly better. These
are bounded software measurements, not native/glass/optical smoothness or a
universal bound. These timing runs alone did not pass physical cable/input
or persistent-promotion gates; their separate later proof is linked below.

## Partial physical acceptance

[Operator report and read-only runtime record](physical-a/README.md) confirmed panel return and bottom-edge Overview on the candidate. At that stage HDMI replug/pinch and persistent promotion remained open; the later acceptance and installation below close them. A reported top notification-shade stutter is a separate userspace investigation.

## Operator acceptance for promotion

The operator replied “everything's good land whatever we're on tell me what's next” after the remaining HDMI reconnect/Overview and persistent-install gate were named. [Exact acceptance and provenance limits](physical-a/operator-acceptance.json) record this as acceptance of the remaining candidate behavior, with no invented contact/cable timestamps or camera proof. [Reserved-board preflight](physical-a/accepted-preflight.json) verifies the unchanged candidate boot, source identity, staged four payloads and original five-file backup before promotion.

## Persistent installation completed

[Guarded promotion and ordinary reboot proof](persistent/summary.json) now qualify the accepted candidate as persistent. Running, booted and persistent system are hpmz, with fresh boot ID69e90426-5ead-4ebb-82d5-2a592168e34d and actual GNU kernel build ID7a61d8cea3e26df94695189b766de3fd66fa6860. [Commands and limits](persistent/README.md) separate persistent file selection from fresh ordinary boot and preserve the old j30 root-backed backup and GC root. Final normal-state checks passed and the board lease was released; source diagnostics and duplicate staging payloads were removed after protected copies/hash checks. Root storage remains a separate issue; no portrait, optical or permanent shade fix is claimed.

## Completed publication and closeout

[Exact proof publication](persistent/proof-publication.json) records successful CI39489265282 and the matching published revision c81572e884fa78305a9941f5c44d827894be1b9d. Source, build, candidate timing, operator acceptance, persistent ordinary boot and cleanup proof are committed; all nine tasks are complete. The archive sync adds this single bounded requirement to existing `display/hdmi`. Other deferred performance/portrait changes retain their own unchecked tasks.
