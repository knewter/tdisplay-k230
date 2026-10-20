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

UNVERIFIED: candidate timing,
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

The actual configured7.3 mainline kernel cross-build passed at18:13:12Z
from source19568595 in1102.482seconds. `host/mainline-kernel/` records the
command, successful exit, derivation and Image/System.map identities.
`host/mainline-source.json` verifies that the realized Nix bridge source
and patch exactly match the host semantic matrix. The new kernel output
is `/nix/store/21lz5c6pkk329c0xcac9bzlx40dplrlk-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
This is cross-build proof; no candidate boot or physical acceptance yet.

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
K230 UART is required before retrying the named serial-observed boot gate.
Neither task2.1 nor any runtime/physical/promotion gate is complete.

At18:30:46Z a fresh protected query verified recovered normal controls:
current/booted/persistent system all j30y; PID1076 with unchanged executable,
config, debug flags and landscape1280x800@59.91normal/scale1; idle Foot,
both shell services active, zero virtual test devices and no trace instances.
See `boot-attempt-a/recovered-normal.json`. This is recovery/runtime-state
proof on the original image, not a boot or timing result for the candidate.
The retry driver now requires a fresh K230 nonce received on an explicit
by-id UART before any serial input/reboot; the candidate remains staged.

The user clarified that SSH should be used rather than requiring a USB
data cable. `ssh-boot/` records an unchanged-image load/unload qualification
of the existing RV64 kexec_file_load API. First flags0 failed errno99;
existing NO_CMA flag16 passed. Both attempts retain all normal controls and
leave kexec_loaded0. The plan now uses a one-time SSH-controlled kernel
boot plus fresh boot/kernel-build-ID/boot-journal evidence. The rejected
UART attempt stays rejected; no UART observation is claimed. Boot, timing,
physical and persistent gates remain open pending their actual checks.

At18:58:31Z the one-time SSH boot is VERIFIED: new bootIDc17ee483,
current/booted systemhpmzja32, persistent profilej30y, and running GNU
kernel build ID7a61d8cea3e26df94695189b766de3fd66fa6860 exactly matches
the built vmlinux and a unique GNU note in candidate Image (absent from
original Image). `ssh-boot/` preserves commands, load/shutdown request,
transport disconnect255, fresh SSH observation and allowed kernel journal
lines. The transport disconnect itself is not boot proof. No UART log is
claimed. All five normal boot files remain unchanged; ordinary reset still
selects the original system.

Fresh candidate controls retain compositor9464072a/config575fa8d1, DEBUG
flags, onlyCPU0, idle Foot, both services active and normal1280x800@59.91
scale1 output. Numeric PID1076 is reused across the reboot; distinct boot
IDs and kernel build IDs distinguish the processes. Fresh function smoke
qualified4 records and cleanup; actual bounded motion/physical/promotion
gates remain separate. The kernel trial needs no USB data cable.
