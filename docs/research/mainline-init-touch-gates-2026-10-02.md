# Ordinary mainline init and touch gates, 2026-10-02

Recorded `2026-10-03T03:37:06Z` (October 2 local time). Evidence class:
read-only host artifact/source inspection. No board, serial, build or source
implementation. Ordinary mainline root/login, deliberate touch and coordinate
mapping remain **UNVERIFIED**. The coordinator owns all physical trials.

Worktree `/home/jadams/tmp/k230-mainline-init-touch-gates`, branch
`audit/mainline-init-touch-gates`, base
`65578ff208fbe999b7f69ad0db9c98cd591211a2`. Own only this note; no board or
build slot reserved. Cached work-status start/handoff run at idle priority.

## Exact candidate and prerequisite boundary

Inspected bundle:
`/nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files`.
Its `system` selects
`/nix/store/9gdmsrh2igqla1qz0ll97czfw2x42icw-nixos-system-nixos-26.11.20260919.20b1ddd`,
with kernel
`/nix/store/9vdk79pa4pm38mlmbflkqh4i4sc9kha0-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
The artifact inspector returned matching Image/system initrd, valid uImage
CRCs, exact DTB/environment bootargs, all four SHA checks and 629 closure paths.
Compressed initrd is
`/nix/store/jdgads5ibbb0zflglhjfncq8ayc1jbfz-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd`,
SHA-256 `046c5b012a2b993caa1082926e9928c14bccc0fff456f20f8716c91d13f51842`.

The coordinator reports this five-clock candidate passed the no-flag minimal
trial, kernel unused-clock cleanup, reboot/SPL and protected normal postflight.
Label and read-only root-mount tests were next, not reported complete when
this note was prepared. Gate ordinary init on their returned success, including
known unmount and independently verified normal recovery. Minimal reboot does
not prove label, filesystem, activation, console login or touch.

## What ordinary init actually runs

A read-only newc archive walk after `zstd -dc` confirms `/init` points to
`/nix/store/srwrq12f962d5prr382vvsq76nfvmm84-systemd-riscv64-unknown-linux-gnu-261.2/lib/systemd/systemd`.
The selected system's `init` is the same ELF by SHA-256
`d3e109a270c0b4463ac5b7b0655ce7667d7c55f6f93341bb461300a5dd5c8c63`.
It is not a shell script. Boot **without `rdinit=`**: the kernel executes
initramfs `/init`; sole `init=<selected-system>/init` is retained for NixOS
closure selection and the eventual root transition. Do not run the selected
init or `prepare-root` manually from the diagnostic PID-1 shell.

The archived fstab remains `/dev/disk/by-label/NIXOS_SD / ext4 x-initrd.mount 0 1`.
`initrd-find-nixos-closure.service` requires `/sysroot/nix/store`; its
`14ryr1zz8qc76fixhpvf91xjra7vwp6h…/bin/initrd-find-nixos-closure-start` resolves
`init=` inside `/sysroot` and verifies `prepare-root`. Activation's
`sqzh9kfs50h02j082xm5xrjsggkg5rd0…/bin/initrd-nixos-activation-start` exports
`IN_NIXOS_SYSTEMD_STAGE1=true` and chroots to the selected `prepare-root`.
Switch-root is ordered after activation and hands `/sysroot` to systemd.

Selected `prepare-root:131–158` executes activation, records `/run/booted-system`,
and lets initrd systemd perform switch-root. Selected `activate:119–121` updates
`/run/current-system`. This is normal writable-root activation; `ro,noload`
diagnostic success cannot substitute for it. Serial getty's exact override
uses agetty with `--autologin root`; default target is multi-user. Expect a
login/autologin sequence and root prompt, then require a fresh command receipt
and candidate identity. A prompt alone or `Linux version` alone is insufficient.

## First ordinary-init comparison flags and limits

Keep bundle bootargs exactly, including `root=fstab`, both existing loglevels
and sole selected `init=`; append only this explicit first-comparison set:

```text
fsck.mode=skip systemd.mask=k230-root-growth.service systemd.mask=register-nix-paths.service
```

Use the existing volatile U-Boot environment import/setenv/printenv path and
exact complete argument comparison. No `saveenv`, `rdinit`, clock-ignore flag,
boot initcall tracing, emergency shell or permanent profile change.

Why these guards are concrete:

- The initrd includes `systemd-fsck@.service` with infinite service timeout;
  the root fstab has pass 1. Its exact systemd-fsck binary recognizes
  `fsck.mode`. Masking only `systemd-fsck-root.service` would not cover this
  instantiated unit. `fsck.mode=skip` explicitly excludes checker/repair
  behavior from this comparison; it does not make normal ext4 mounting free
  of journal replay or other writes.
- Selected `k230-root-growth.service` runs
  `/nix/store/6sca423wcjlq1v9ynjpbv4ai48jf53l9-k230-root-growth/bin/k230-root-growth --apply`
  with a 180-second start timeout. Mask it to exclude partition/filesystem
  resizing, rather than assume this card makes the service a no-op.
- [nix/k230.nix:63](../../nix/k230.nix) and the selected registration unit
  condition on `/nix-path-registration`. The script runs
  `nix-env -p /nix/var/nix/profiles/system --set /run/current-system` and removes
  that marker. Mask it even if fresh protected preflight finds the marker absent:
  a diagnostic must not replace the persistent normal profile.

This is a qualified ordinary-init comparison, **not production acceptance**
with the guards removed. Activation can update mutable `/etc` and runtime
state. Retain all eight protected boot hashes and persistent profile identity
as pre/postflight gates; never run `switch-to-configuration` or write boot files.
After candidate reboot, verify the protected normal system and restore its
normal runtime/Home using the existing reviewed recovery procedure.

## Proposed controller interface and scope, not implemented

A separate `tools/mainline-drm-system-trial.py` with its host test file and
host evidence is appropriate: the existing shell controller unconditionally
adds `rdinit=/bin/sh` and its readiness/probe schemas describe that shell.
Reuse its immutable bundle/manifest/normal-report preparation, actual address
range/size checks, protected preflight/postflight, load/CRC and serial locking.
Leave the existing minimal/label/root-mount protocols unchanged. Proposed
operator interface after review:

```sh
python3 tools/mainline-drm-system-trial.py begin --bundle <exact-5yqilsfy-store-path> --normal-report <fresh-protected-report> --state <private-state-path>
python3 tools/mainline-drm-system-trial.py touch --state <same-private-state-path>
python3 tools/mainline-drm-system-trial.py finish --state <same-private-state-path>
```

`begin` verifies protected normal state, boots ordinary init with the exact
guards, and waits at most 180 seconds for login/root receipt. Before declaring
usable root, independently require UID 0, fresh boot ID, selected
`/run/current-system` and `/run/booted-system`, selected booted kernel path,
7.3-rc5 uname, sole matching `init=` with no `rdinit`, root source/type/options,
unchanged persistent profile and active serial getty. Check the three guards
from parsed cmdline/unit state without publishing raw cmdline. Print fixed
token/RC/match fields; save exact candidate boot ID and original normal report
in mode-0600 private state. Initial failure before `bootm` can use existing
U-Boot reset recovery; unknown post-boot state receives no guessed input.

`touch` and `finish` must recheck that exact live candidate boot ID, system,
kernel and preserved profile before any action. Reject stale state, a different
candidate or a normal shell that happens to have the same prompt. Candidate
`sw/bin/python3` **does not exist**. Use selected system `sw/bin/sh`, `uname`,
`readlink`, `findmnt`, `systemctl`, `timeout` and `evtest` plus shell builtins
for candidate probes, with parsing on the host. Their absolute prefix is the
selected `9gdms…` system above; all those executables were checked to exist.
Existing normal-state helper Python is for the protected normal system.

`finish` issues one clean selected `sw/bin/systemctl reboot` after the guard,
then passively waits at most 180 seconds for kernel restart/SPL and normal login.
Require fresh normal boot ID and full protected postflight before success.
Never retry after absent acknowledgements or use Ctrl-C/exit to guess recovery.
A host deadline is an observation limit, **not a reset watchdog**. No autonomous
hardware watchdog is armed in this plan; reset-button recovery remains the
operator route if Linux stalls. Preserve partial facts/private capture on timeout.

## Bounded real-touch proof

Resolve the live event node by sysfs name `Goodix Berlin Capacitive TouchScreen`
and physical ancestry under `soc/91408000.i2c/.../<bus>-005d/input`, rejecting
virtual/uinput nodes, ambiguity and fixed-event-number assumptions. Pinned
`goodix_berlin_core.c:618–639` gives that name and uses touchscreen properties
for ABS ranges. Capture the actual header/ranges rather than assume scaling.

After the identity gate, run exactly one bounded read-only capture, with a
fresh token in the `/run` filename and the verified `/dev/input/eventN`:

```sh
<selected-system>/sw/bin/timeout --signal=TERM --kill-after=2s 30s <selected-system>/sw/bin/evtest /dev/input/eventN > /run/k230-mainline-touch-<token>.log 2>&1
```

Return a fixed final RC marker (124 is the expected completed capture window),
then collect the bounded file only after that marker. Record a deliberate
finger tap, drag and release on the glass during the window, with operator
timing and a panel photograph/video. Host parsing should retain tracking-ID
down/up, position changes and complete SYN frames; no contacts is a failed
interaction gate, not a dead-driver diagnosis. Do not use `--grab`, uinput or
injected events. Do not reuse `touch-axis-test.py` unchanged: it hardcodes
event0, writes assumed RGB565 fb0 and broadly kills evtest. Known glass-corner
interactions and actual reported ranges are needed for any coordinate mapping
claim. Probe registration, real events, mapping and visible panel acceptance
remain distinct proofs; the optional console system makes no graphical-shell
acceptance claim.

Meaningful host tests: exact guarded args and forbidden flags; candidate/normal
identity and stale private-state failures; absent Python; split/stale/echoed,
duplicate and truncated receipts; no input before login readiness; unknown
timeout/no retry; guard failure suppresses touch/reboot; physical versus virtual
Goodix selection; bounded evtest RC/complete frames/no events; finish normal
return timeout preserving facts and protected hash/profile mismatch rejecting
success. These tests do not satisfy task 5b.5.

## Host checks and remaining gate

`python3 tools/mainline-drm-trial-inspect.py <exact-5yqilsfy-store-path>` passed.
Read-only archive walking, selected units/scripts/executable checks and SHA
comparisons supplied the source facts above. `git diff --cached --check` and
`openspec validate the-board-runs-a-mainline-kernel --strict` passed.
Cached status is run at start and handoff; review/merge/push and controller
implementation remain coordinator/worker work. No full build is needed for
that host controller. Matching ordinary boot, physical touch and protected
normal restoration remain the operator's explicit gates; task 5b.5 stays open.
