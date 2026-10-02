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
five loads by reported byte count and U-Boot memory CRC, imports the matching
211-byte bootargs file, checks that its `init=` still names the exact system,
then appends only volatile `rdinit=/bin/sh`. It uses the existing addresses
and `bootm 0x8000000 0x9000000 0x8400000`. It never saves U-Boot environment
or edits the normal boot selector/profile/files. Raw serial output is created
with mode 0600 beneath `/home/jadams/tmp/k230-coordination/` and is not sent
to stdout or committed. The default log directory is
`/home/jadams/tmp/k230-coordination/mainline-initrd-private/` (mode 0700).

Once the kernel version banner is seen, the controller sends a bounded shell
command to record `/proc/uptime`, `/proc/interrupts`, `/proc/cmdline`,
`/proc/mounts`, `/dev/disk/by-label`, and `dmesg`. It does not send `exit`:
the diagnostic shell is PID 1, and exiting it would panic the kernel. The
command waits ten seconds and invokes the initrd's existing `reboot -f` as a
child. Successful restoration is counted only when the unchanged normal path
returns to a `nixos login:` prompt. If the kernel or shell does not reach the
bounded markers, the operator must keep the board reservation and use the
coordinator's agreed physical power-cycle recovery; the controller clearly
reports that PID 1 may still be the shell.

A responsive initrd shell would show that early userspace can run commands
and report early device state. It would not prove stage2/root login, display
usability, or touch acceptance. Existing logs show kernel/driver activity
through roughly 7.22 seconds in the first boot; the later truncated systemd
debug line is not evidence of a failed sysctl write or udev failure. Task
5b.5 remains open until root login, deliberate touch interaction, and
committed normal restoration evidence exist.
