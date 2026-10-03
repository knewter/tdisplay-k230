# Bounded ordinary-initrd debug controller: host preparation

Evidence class: host implementation, fixtures and simulated UART. No board,
serial, staging, kernel/initrd build or physical recovery was performed by this
worker. Initrd debug-shell readiness, state observations and this controller's
automatic normal return remain **UNVERIFIED**. Task 5b.5 stays open.

Worktree `/home/jadams/tmp/k230-mainline-initrd-debug-trial`, branch
`mainline-initrd-debug-trial`, base
`79e9fdc8325d70541406ddf5526829686dca20d8`. Owned only
`tools/mainline-drm-initrd-debug-trial.py`, its new host test file, and this note.
No board/build reservation. Cached `python3 tools/work-status.py` start returned
zero; handoff runs at idle priority. The coordinator exclusively owns hardware.

## Scope and preflight

The new, separate controller implements the reviewed
[source proposal](../../research/mainline-initrd-debug-console-2026-10-03.md).
Existing shell, blkid and ordinary-system controllers are unchanged. It imports
their immutable bundle/system, exact manifest/artifact hash/CRC/size/address-range,
protected normal pre/postflight and serial-lock helpers. Both normal phases
include the registration-marker absence assertion before reporting success.

The original three qualified controls remain, with exactly two additions:

```text
fsck.mode=skip systemd.mask=k230-root-growth.service systemd.mask=register-nix-paths.service rd.systemd.unit=basic.target rd.systemd.debug_shell=ttyS0
```

Original bundle arguments and sole selected `init=` remain. Existing diagnostic
arguments are rejected; no rdinit, clock-ignore, logging/debug extras, saveenv,
normal profile change or full-root activation is added. Exact printed volatile
arguments must match before candidate boot.

`--blkid-result` is required before serial import/open. Its private owner/mode/
parent/path, schema, matching candidate bundle/system, successful diagnostic and
raw retrieval, acknowledged reboot, fresh boot IDs and exact protected normal
identities/services/boot hashes are checked. This is an operator-owned prior
result, not an independent attestation of hardware. The coordinator has now
recorded the physical prerequisite separately in commit `7e2a0a9d`; these host
tests do not create that proof.

## Runtime gates and bounds

Readiness requires a fresh candidate Linux banner, initrd systemd 261.2 and a
completed primary bash prompt; no command is sent while waiting. The fresh
receipt and guards then independently establish UID0, kernel/init/cmdline,
fresh boot ID, exact PID1 systemd, initrd-release, outer interactive shell PID/
PPID1, actual fd0 `/dev/ttyS0`, debug-shell ExecMainPID/TTYPath/active-running/noJob,
and unique proc/sysfs/devtmpfs/cgroup2 mounts on a volatile root. `/sysroot` and
all its submounts are forbidden. `sysroot.mount`, closure lookup, activation,
switch-root target and switch-root service must be inactive with no pending job.

One 90-second absolute deadline covers receipt, initial guards, observations,
retrieval and renewed guards. Each child snapshot uses five-second timeout/
TERM/KILL-after-two-second controls; ping also has a three-second daemon bound.
Snapshots cover unit jobs/properties, ping, 80 journal lines and at most 16
trigger/worker PIDs from verified exact unit cgroups. Only their comm, status
state and wchan are read; no Python, ps, process command-line/environment,
arbitrary MMIO or interrupt survey is required.

Every snapshot goes to a newly created mode700 volatile directory. Before the
next observation, a fresh framed retrieval copies it into the mode600 host UART
log and checks exact normalized byte size (at most 65,536) and SHA-256. Raw output
is private; structured facts store only RC, length and hash. Empty output is
valid, e.g. ping. Kernel text inserted into a retrieved payload fails its hash;
no broad printk stripping or guessed marker reconstruction is used.

The parser uses complete unique anchored fresh frames, a primary prompt, a
0.2-second quiet acceptance interval and cumulative received-byte bound 262144,
independent of the shared session's smaller rolling buffer. Future output beyond
that finite interval cannot be predicted; this is a bounded console protocol.
Stale/echoed/duplicate/truncated frames or unknown child completion stop input.
Known nonzero snapshots get their returned output retrieved, then stop too;
there is no automatic continuation/reboot on a failed diagnostic.

Only all completed snapshots and renewed same-boot/same-shell guards permit
one acknowledged `/bin/reboot -ff`, then SPL/normal readiness and protected
postflight. Missing receipt/return has no retry. Host timeouts cannot force a
kernel D-state task or guarantee recovery. Preserve the private result/log and
use the coordinator's operator-reset recovery if completion is unknown.

## Host checks and operator command

Commands run:

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_initrd_debug_trial.py -v
python3 -m unittest discover -s tests -p 'test_mainline_drm*.py'
python3 -m py_compile tools/mainline-drm-initrd-debug-trial.py
python3 tools/mainline-drm-initrd-debug-trial.py --help
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --cached --check
```

The 22 narrow tests and all 160 combined mainline controller tests pass. They
execute actual isolated sh/bash mount-table
payloads (including false final entries, missing/wrong/duplicate mounts and a
mounted sysroot), cgroup/proc fixtures (PID bound and private-field filtering),
and outer-shell PID capture. Simulated real session pumping exercises split
frames, delayed duplicates, stale/truncated markers across every stage, capped
buffer overflow, write-time deadline accounting, identity/TTY/PID/root-job
mismatches, private raw corruption, failed snapshots, renewed identity and
exactly one reboot only after success. Pure tests reject unsafe prerequisites/
arguments before serial and registration markers before success. Independent
read-only peer review reproduced all 22 passes and approved the final source.

After source landing, only the reserved operator may run:

```sh
python3 tools/mainline-drm-initrd-debug-trial.py \
  --bundle /nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files \
  --manifest "$PRIVATE/candidate-manifest.json" \
  --normal-report "$PRIVATE/normal-report.json" \
  --blkid-result "$PRIVATE/successful-blkid-result.json" \
  --log "$PRIVATE/new-debug-uart.log" --result "$PRIVATE/new-debug-result.json"
```

`PRIVATE` denotes an existing operator-owned mode700 directory outside the
repository; log/result must be fresh distinct paths. A matching staged bundle,
fresh protected normal preflight, reviewed controller and operator-reset route
remain required. Review/merge/push and physical debug readiness/observations/
protected return remain separate from this host handoff.
