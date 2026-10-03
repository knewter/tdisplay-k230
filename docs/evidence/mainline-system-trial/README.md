# Qualified ordinary-init controller host preparation

Evidence class: source and host tests only, 2026-10-02 local time (October 3
UTC). Worktree `/home/jadams/tmp/k230-mainline-system-trial`, branch
`mainline-drm-system-trial`, base `99068255a82383463681fcdd8e6115e15f06e4ee`.
Own only the new controller, its new test file and this evidence directory.
No build slot, board reservation, serial access, candidate boot or touch was
performed by this worker. Task 5b.5 and physical ordinary-init/touch remain
**UNVERIFIED**; the coordinator owns planning, integration and board work.

The selected host-built bundle is
`/nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files`.
Its exact kernel/system/DTB/initrd identities and successful matching inspector
are recorded in [SD1 clock build proof](../mainline-sd1-clocks/README.md).
The coordinator reports no-clock-ignore minimal restart/protected-normal
recovery. Ordinary init must additionally wait for returned label/root-mount
diagnostics and protected restoration. A root-marker parser failure is not
proof of a hardware stall or usable ordinary root.

## Source boundary and interface

[The independent init/touch audit](../../research/mainline-init-touch-gates-2026-10-02.md)
(`35f1fbbc301e52fb764f7bfd79ab0ebfcbd82874`) reads the actual selected initrd,
systemd 261.2 init/units, prepare-root/activation and executable paths. Kernel
boot without `rdinit=` executes the initramfs `/init`; the sole matching
`init=<system>/init` selects the closure for normal root activation/switch-root.
Neither init nor prepare-root is manually executed by this controller.
Candidate `sw/bin/python3` is absent; candidate reports use shell builtins and
the checked exact system's tools. The existing Python identity helper runs
only on protected normal preflight/postflight.

[The new controller](../../../tools/mainline-drm-system-trial.py) imports the
existing shell controller's immutable bundle/manifest/normal-report preparation,
protected normal helper, private serial log/session, load-range/count/CRC,
printed bootargs and locking helpers. It leaves the existing rdinit protocols
and schemas unchanged. It adds exactly these volatile first-comparison controls:

```text
fsck.mode=skip systemd.mask=k230-root-growth.service systemd.mask=register-nix-paths.service
```

Source grounds them as excluding the initrd fsck unit's unbounded checker,
explicit root-growth resize and registration service's persistent profile
replacement. Fresh normal preflight requires `/nix-path-registration` absent
(including a dangling symlink). Both masked services must report LoadState
`masked` on the candidate. Exact complete printed bootargs must match: no
`rdinit`, PATH, clock-ignore, boot debug, rescue override or persistent
environment save is added. This is a **qualified first ordinary boot**.
Writable activation and ext4 mounting can update mutable root/runtime state;
unmasked production acceptance and a graphical mainline shell are not proved.

The operator explicitly selects three phases:

- `begin` verifies fresh normal identities/services/eight hashes and registered
  staged closure, records root source/type/UUID/label, performs exact protected
  U-Boot loads/counts/CRCs and volatile args, then waits at most 180 seconds for
  a fresh 7.3-rc5 banner, autologin and root prompt before sending reports.
  Reports require UID 0, selected current/booted system/kernel/PID1, fresh boot
  ID, active serial getty, sole init/exact guards, ext4 `NIXOS_SD` root at the
  observed `/dev/mmcblk1p2` with `rw`, unchanged UUID/profile/eight hashes, and
  absent registration marker. It persists mode-0600 state and leaves candidate
  running for an explicitly reserved operator/finger interaction.
- `touch` requires `--real-touch` and a fresh same-boot identity/profile/root/
  control/hash report before one read-only Goodix capture. It leaves candidate
  running. No contact is recorded as an unproved interaction; a known completed
  capture allows a separate guarded `finish` even if interaction was unproved.
- `finish` rechecks all those identities against private state, requests exactly
  one selected `systemctl reboot`, requires a complete fresh RC-zero receipt,
  then passively waits up to 180 seconds for SPL, 6.6.36, login and root prompt.
  Protected postflight requires a fresh normal ID, original profile/system/
  kernel/init, three active services and eight hashes. A successful ordinary
  boot can be finished without performing touch; it does not then prove touch.

Reports use separate complete begin/end/field tokens, RC fields and a fresh
prompt; generated identity lines are 720–1,385 bytes. Split serial reads and
rolling-buffer rollover are tested. Echoes, stale/wrong tokens, duplicate,
malformed, missing or nonzero reports stop input. Arbitrary kernel printk
interleaving is **not stripped or repaired**. Reboot acknowledgement is allowed
without a subsequent candidate prompt; fresh recovery bytes in that same read
are retained. All received valid identity stages survive a later failure.
Unknown completion invalidates resumable state and preserves a recovery-required
private result, with no Ctrl-C, guessed exit, reboot retry or automatic reset.
A busy board lock opens no serial and preserves previously ready state.
Deadlines bound observation; they do not provide autonomous hardware recovery.

## Real touch boundary

Sysfs must identify exactly one `Goodix Berlin Capacitive TouchScreen` under
`/sys/devices/platform/soc/91408000.i2c/i2c-<n>/<n>-005d/input/input<n>`.
Virtual/uinput nodes, ambiguity and fixed event-number assumptions are rejected.
The verified `/dev/input/event<n>` must be a character device. The fixed capture
is `timeout --signal=TERM --kill-after=2s 30s evtest <node>`, writing only a
fresh private `/run/k230-mainline-touch-<token>.log`. No grab, injection, framebuffer
write or broad process kill occurs. Only known RC 0/124 permits one bounded file
retrieval; unknown capture/retrieval receives no further input.

Pinned evtest 1.36 executable strings confirm the dashed SYN_REPORT format and
typed ABS rows. Host parsing requires one contact with tracking-ID down, XY
coordinates and changed positions in distinct completed SYN frames, release
and final SYN. Separate stationary taps cannot substitute for a drag. Raw
header/ranges/events remain in the protected serial log; structured result
records counts and down/move/up/SYN facts. `--real-touch` declares operator
intent; serial events alone do not prove physical provenance. The operator
must deliberately tap/drag/release the glass during the capture, record timing
and camera evidence separately, and inspect reported ranges before any
coordinate-mapping claim. Mapping remains **UNVERIFIED**.

## Host proof and operator commands

```sh
python3 -m unittest discover -s tests -p 'test_mainline_drm_*trial.py' -v
openspec validate the-board-runs-a-mainline-kernel --strict
```

[Host test log](host-tests-2026-10-03.log) records 118 passing tests (96 existing
rdinit tests plus 22 new ordinary-init tests), including a complete begin/touch/finish flow using the
real rolling serial pump, readiness beyond eight seconds, exact controls,
stale/duplicate/split/truncated/nonzero markers, no premature probe, isolated
actual sh reports, wrong boot/profile/hash/normal services, physical node
selection, complete real-format frames, unknown capture/retrieval/no retry,
normal-return timeout preserving candidate facts, and private state/board lock.
All shell execution replaces proc/sys/run/boot/profile/registration paths and
utilities with temporary fixtures; no host sysfs, mounts or debug state is used.
Injected fixture events are host parser proof, never physical touch evidence.
Final suite exit zero was observed by `2026-10-03T04:03:56Z` (15.587 seconds).
Python compilation, strict OpenSpec validation and staged whitespace checks
also pass.
The cached work-status scan runs at start and handoff. No task checkbox or
canonical specification is changed.

After review, successful returned root diagnostics, staging and a fresh
protected normal report, the sole board operator can use these commands. The
directory must already exist with mode 0700; every log/result pathname must be
new. State remains private and contains exact boot IDs; no runtime contents
belong in committed evidence without deliberate sanitization.

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --bundle /nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-system-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-system-board/normal-report.json" \
  --state "$HOME/tmp/k230-mainline-system-board/state.json" \
  --log "$HOME/tmp/k230-mainline-system-board/begin-uart.log" \
  --result "$HOME/tmp/k230-mainline-system-board/begin-result.json"
python3 tools/mainline-drm-system-trial.py touch --real-touch \
  --state "$HOME/tmp/k230-mainline-system-board/state.json" \
  --log "$HOME/tmp/k230-mainline-system-board/touch-uart.log" \
  --result "$HOME/tmp/k230-mainline-system-board/touch-result.json"
python3 tools/mainline-drm-system-trial.py finish \
  --state "$HOME/tmp/k230-mainline-system-board/state.json" \
  --log "$HOME/tmp/k230-mainline-system-board/finish-uart.log" \
  --result "$HOME/tmp/k230-mainline-system-board/finish-result.json"
```

Review/merge/push/deployment and physical qualified root/login, real-glass
interaction and protected normal restoration remain with the coordinator.
This host preparation cannot close task 5b.5 or establish unmasked acceptance.

The [first physical ordinary-init attempt](physical-2026-10-03/README.md)
reached systemd/udev but timed out before root activation/login. Its result,
curated excerpt and camera limits are recorded separately; no touch acceptance
or task completion is inferred from it.
