# Mainline initrd shell diagnostic preparation

Prepared after the two 2026-10-01 DRM trial boots stalled before a root login.
This note records controller review and physical diagnostic attempts. The
first `rdinit=/bin/sh` shell attempt reached PID 1 but its probe failed because
the initrd environment had no usable `PATH`; it makes no claim about the
stall's cause.

The exact bundle remains
`/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-k230-mainline-drm-trial-boot-files`,
with matching system
`/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd`.
The committed source audit confirms the matching initrd contains executable
`/bin/sh` (Bash 5.3p15) and `reboot` in its initrd command environment. The
read-only IRQ review recommends this as the clean discriminator because it
replaces `/init` before systemd with no extra debug boot arguments.

From the repository root, the prepared operator command is:

```sh
nix shell nixpkgs#python3Packages.pyserial --command \
  python3 tools/mainline-drm-initrd-shell-trial.py
```

The controller takes `/tmp/k230-board.lock`, checks the exact manifest's
five loads with complete standalone byte-count and U-Boot CRC reports, imports the matching
211-byte bootargs file, checks that its `init=` still names the exact system,
then appends only volatile `rdinit=/bin/sh`. It uses the existing addresses
and `bootm 0x8000000 0x9000000 0x8400000`. It never saves U-Boot environment
or edits the normal boot selector/profile/files. Raw serial output is created
with mode 0600 beneath `/home/jadams/tmp/k230-coordination/` and is not sent
to stdout or committed. The default log directory is
`/home/jadams/tmp/k230-coordination/mainline-initrd-private/` (mode 0700).

Before rebooting, a temporary helper streamed into `/run` verifies the fresh
protected baseline in `/home/jadams/tmp/k230-coherent-boot-board/received/after.json`:
installed system, profile, booted kernel, `uname -r`, normal `init=` selector,
three services, and all eight protected boot/selector hashes. It also checks
the four staged candidate files and the `registration`, `store-paths`, and
`SHA256SUMS` hashes against the exact bundle, compares `nix-store -qR` with the
staged closure, and runs `nix-store --check-validity` in batches. The helper
and expected data are written only into `/run`.

Once the kernel version banner is seen, the controller sends a bounded shell
command that first sets volatile `PATH=/bin:/sbin`, then mounts proc, sysfs,
and devtmpfs in the in-memory initrd and records
`/proc/uptime`, `/proc/interrupts`, `/proc/cmdline`, `/proc/partitions`,
`/proc/mounts`, `/sys/block`, block device nodes, udev label links, and direct
`e2label` results. It requires successful virtual mounts and at least one
readable partition label. `NIXOS_SD` is recorded independently; a missing
udev by-label link under direct `rdinit` is not treated as a cause. The
sanitized result file records whether any partition reports that exact label.
It does not
send `exit`: the diagnostic shell is PID 1, and exiting it would panic the
kernel. The command waits ten seconds and invokes `/bin/reboot -ff` as a child.
Successful restoration is counted only after verifying the returned system,
kernel, profile, kernel release, `init=` selector, three services, a new boot
ID, and the same eight protected boot-file hashes. A login prompt alone is not
recovery proof. If the kernel or shell does not reach the
bounded markers, the operator must keep the board reservation and use the
coordinator's agreed physical power-cycle recovery; the controller clearly
reports that PID 1 may still be the shell.

A responsive initrd shell would show that early userspace can run commands
and report early device state. It would not prove stage2/root login, display
usability, or touch acceptance. Existing logs show kernel/driver activity
through roughly 7.22 seconds in the first boot. A read-only log audit also
finds systemd waiting for `/dev/disk/by-label/NIXOS_SD` around 5.99 seconds;
the kernel log detects the SD card and two partitions, but does not establish
whether udev created that label link or whether the partition label matches.
The captured directory listing and mounts will help distinguish root-device
handoff from a broader early-userspace stall. The later truncated systemd
debug line is not evidence of a failed sysctl write or udev failure. Task
5b.5 remains open until root login, deliberate touch interaction, and
committed normal restoration evidence exist.

## 2026-10-01 staging repair and first corrected-path attempt

The first fresh preflight confirmed the protected normal system/profile,
booted kernel, service state, and all eight baseline boot/selector hashes, then
stopped at `mainline-drm-normal-state.py:61`: the candidate stage's `system`
symlink was absent. Read-only inventory found the four candidate load files
and existing `SHA256SUMS` matched the immutable bundle, while `registration`
and `store-paths` were absent. Only those two missing files were added from
the exact bundle, with no-replace writes and board-side size/SHA-256 checks:

| staged file | bytes | SHA-256 |
| --- | ---: | --- |
| `registration` | 303363 | `cbd962f866f3d715ab3e56cc30be01e3c0093588834df3d61a0e7e516847d865` |
| `store-paths` | 49876 | `05b84ef55caf96fd7785b1dbe9760e5276e64c424ac80ab24abce0794bf7509d` |

`nix-store --check-validity` passed for the exact candidate system before a
no-replace symlink was created at the staging path; the resolved target was
checked against that system. These changes are confined to the opt-in stage
directory. The normal profile, normal boot files, selector files, and boot
selection were not changed.

The next volatile `rdinit=/bin/sh` attempt reached the PID 1 shell and emitted
its strict fresh-token probe marker, but returned `RC=1`. The raw private log
showed that PATH resolution failed for `cat`, `ls`, `mkdir`, `mount`, `reboot`,
and `sleep`. Therefore the accompanying `NIXOS_SD=false` value is invalid as a
device observation: the probe did not inspect partitions or labels. Its
`reboot -ff` command was also not found. Afterward the UART remained silent;
one direct volatile-PATH `/bin/reboot -ff` attempt yielded zero bytes over 60
seconds. No corrected probe, normal recovery identity check, display check, or
touch check was obtained. The controller now sets `PATH=/bin:/sbin` before the
probe and invokes `/bin/reboot -ff`. Static inspection of the exact pinned
kernel/initrd confirms the correction is compatible with that artifact:
kernel startup initializes only `HOME` and `TERM` (`init/main.c:198-199`); the
`rdinit` argument is selected before normal init (`init/main.c:590-600`), and
the console is duplicated onto standard input/output/error
(`init/main.c:1631-1643`). The pinned initrd's `/bin` resolves to its
executable environment, which contains Bash 5.3p15 and each external command
used by the probe. Its `reboot` entry resolves to systemd 261.2's `systemctl`;
double-force reboot mode is implemented as a direct reboot syscall without
asking the system manager ([pinned systemctl source](https://github.com/systemd/systemd/blob/v261.2/src/systemctl/systemctl.c)).
The probe input is 1,934 bytes plus its line ending, below the pinned TTY
canonical input limit of 4,096 bytes (`drivers/tty/n_tty.c:59,1652-1653`).
These are source/artifact checks only. They do not establish that the corrected
probe or reboot ran successfully on hardware. A passive capture following the
requested physical reset expired after 15 minutes with no UART bytes or
U-Boot, normal-kernel, or login markers. The reset and normal-system recovery
were unobserved at that point. See the 2026-10-02 attempt and subsequent
recovery below. Keep task 5b.5 open.

## 2026-10-02 observed power-swap recovery

The operator subsequently reported “power swapped it”. The fresh exclusive
serial postflight passed: exact normal system/profile/kernel/init, Linux
6.6.36, all three shell services active, a new boot ID and unchanged hashes
for all eight protected boot/selector files. Home is visible after injected
DPMS/Home commands and transient-surface hide, with reviewed native and
physical-camera captures. See [recovery commands, result and limits](power-swap-recovery-2026-10-02/README.md).
This supersedes the earlier unobserved-restoration status; it does not turn
the failed PATH probe into valid partition evidence or satisfy mainline
root-login/touch task 5b.5. The later corrected probe result is below.

## 2026-10-02 corrected PATH probe and recovery

At `2026-10-02T06:34:52Z`, controller source revision
`b209129b1cf681669edfe3e1e05be317842bf6f4` ran one bounded trial from the
exact `gf3aqks2dg0z3ksz33ysfprnlbk83vw3` bundle and matching
`k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1` system. The controller reached volatile
`bootm` only after its strict five-load count/CRC checks and protected-normal
preflight, including the selected p1 system/profile/kernel/init, three active
services, eight protected boot-file hashes, staged artifact hashes, closure
registration, and store validity. It observed the Linux 7.3.0-rc5 banner.

The corrected initrd command set `PATH=/bin:/sbin` and invoked external probe
commands before its final marker. The controller did not receive a complete
fresh-token `K230_RDINIT_PROBE ... RC=...` line within its 60-second bound and
stopped without sending `exit` or issuing another command. Sanitized parsing of
the private UART capture found one standalone `K230_PROC` marker, no complete
later sys-block, device-block, by-label, ext4-label, NIXOS_SD, or reboot marker,
and no login prompt. The full command echo including its token/final marker
was not present. The kernel banner was followed by 89 timestamped kernel
lines; the last reported candidate-kernel timestamp was 0.072493 seconds. A
generic command-not-found string elsewhere in the capture could not be
attributed to this probe. These observations do not establish what happened
inside the subsequent proc read, and provide no disk-label, IRQ, or root-handoff
evidence.

The raw capture remains outside Git at
`/home/jadams/tmp/k230-coordination/mainline-initrd-private/mainline-initrd-shell-20261002T063452Z.private.log`,
mode 0600, 43,726 bytes, SHA-256
`984609649a9e790e43072e84a70830b4df3357346ceeda7c07b56362701d89df`. The
controller source SHA-256 for that run was
`953e3dfdfa7e45f1c7781dd066e736698f19d59affd11b7ec30f142bbd174c10`; the
normal-state helper SHA-256 was
`86bcf6f2c175d44d27f68015a9cc5a1ad7731ad50b6bbf3347859a4840cc7df7`.
No result JSON was written because the strict marker gate failed. The
operator then performed a physical power-cycle; the coordinator independently verified
the exact normal p1 system/profile/kernel/init, Linux 6.6.36, all three active
services, unchanged eight protected hashes, and a new boot ID
`e7cf8096-44a0-4bdf-815d-2f1aec4126fb`. This restores the normal system after
this trial; reviewed native and physical Home captures are committed in
[corrected-probe recovery](corrected-probe-recovery-2026-10-02/README.md).

Host review found a false-failure case in the probe: `e2label` errors on any
non-ext partition set the global RC to failure even if another partition had
a readable label. The controller now reports unreadable per-device labels
without failing the probe for that alone; the final gate still requires at
least one readable ext label, while `NIXOS_SD` remains an independent exact
observation. It also emits unique-token stage markers around `mkdir`, virtual
mount checks, and proc/sys/device reads so a future bounded run can locate
progress without treating command echo as execution. Generated survey command
size is 2,885 bytes, below the 4,096-byte TTY canonical input limit. Focused
host tests cover the strict stage parser and conservative label policy.

## Host-only protocol revision (not physically run)

The controller's default probe is now a short sequential discriminator rather
than the full device survey: a fresh-token built-in receipt marker, an
absolute `/bin/true` with its return code, and one bracketed `/bin/cat /proc/uptime`,
followed by the bounded absolute `/bin/reboot -ff` request.
Each stage requires a complete standalone marker line for the current UUID;
missing or malformed stage markers stop further probe input. A missing reboot
marker is recorded separately while the existing normal login and protected
identity postflight remain required. The result schema identifies this as
`k230-initrd-minimal-v1`.

The broader proc/interrupt/device/label survey remains available only through
explicit `--mode survey`, and only after both minimal external-command stages
return zero. It has a distinct result schema so a minimal run cannot be read
as label or IRQ evidence. The focused fake-serial suite passes 16 tests,
including echoed, stale, truncated, duplicate, missing and nonzero markers,
timeouts, survey gating and reboot-marker absence. Python compilation,
`git diff --check`, and strict OpenSpec validation pass. This host-only
revision does not resolve why the previous probe stopped after `K230_PROC`;
no additional board attempt was made. Task 5b.5 remains open.
