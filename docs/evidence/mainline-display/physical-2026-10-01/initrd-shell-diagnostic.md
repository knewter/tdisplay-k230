# Mainline initrd shell diagnostic preparation

Prepared after the two 2026-10-01 DRM trial boots stalled before a root login.
This is a source and controller review; the `rdinit=/bin/sh` trial has not
been run. It makes no claim about the stall's cause.

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
command to mount proc, sysfs, and devtmpfs in the in-memory initrd, then record
`/proc/uptime`, `/proc/interrupts`, `/proc/cmdline`, `/proc/partitions`,
`/proc/mounts`, `/sys/block`, block device nodes, udev label links, and direct
`e2label` results. It requires successful virtual mounts and at least one
readable partition label. `NIXOS_SD` is recorded independently; a missing
udev by-label link under direct `rdinit` is not treated as a cause. The
sanitized result file records whether any partition reports that exact label.
It does not
send `exit`: the diagnostic shell is PID 1, and exiting it would panic the
kernel. The command waits ten seconds and invokes `reboot -ff` as a child.
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
