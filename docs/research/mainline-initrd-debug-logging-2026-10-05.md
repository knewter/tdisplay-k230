# Logging the ordinary-init closure boundary

The [current p2 physical run](../evidence/mainline-system-trial/current-p2-ordinary-physical-2026-10-05/README.md)
shows mounted `/sysroot` and starting NixOS closure lookup, but no completion,
switch-root or login within 180 seconds. This is a unit boundary to investigate,
not proof that the closure helper or a particular syscall is blocked.

Host inspection of the selected archive shows `initrd.target` requires
`initrd-find-nixos-closure.service`. That oneshot requires mounts for the root
store and precedes activation/switch-root. Its Bash script reads the kernel
commandline, extracts init, runs `resolve-in-root`, obtains the containing
directory, creates the volatile closure link, checks the executable prepare-root
path and writes volatile switch-root configuration. It does not execute
prepare-root; the later activation helper does. The archive uses a referenced
immutable initrd fstab via `SYSTEMD_SYSROOT_FSTAB`; absence of `/etc/fstab` is
not evidence of a broken root mount.

The selected nixos-init source `src/path.rs` resolves the path through
`pathrs::Root`, then uses procfs to recover the resolved fd path. This names a
path-resolution/metadata boundary, not a demonstrated syscall or card-I/O stall.
The quiet transcript contains no nested shell-command completion evidence.

The earlier [quiet initrd debug-shell controller](../evidence/mainline-system-trial/initrd-debug-controller-host-2026-10-03.md) selects a different target and shell policy. It did not implement this logging-only ordinary-init comparison; its private scratch and captures are kept separate. The [earlier source audit](mainline-initrd-debug-console-2026-10-03.md) listed logging as a future alternative.

The next bounded step adds exactly
`rd.systemd.log_level=debug rd.systemd.log_target=console` to ordinary init.
Pinned systemd 261.2 supports the [two logging settings](https://github.com/systemd/systemd/blob/v261.2/src/basic/log.c#L1177-L1202)
and [initrd prefix handling](https://github.com/systemd/systemd/blob/v261.2/src/basic/proc-cmdline.c#L177-L190).
Its [ExecStart spawn logging](https://github.com/systemd/systemd/blob/v261.2/src/core/execute.c#L555-L556),
[execution logging](https://github.com/systemd/systemd/blob/v261.2/src/core/exec-invoke.c#L6063)
and [service transitions](https://github.com/systemd/systemd/blob/v261.2/src/core/service.c#L1446-L1447)
can distinguish queued dependencies, spawn/exec failure, a running main process
without completion, and completed closure lookup before activation. They do not
trace Bash's silent subprocesses or a blocked call. If the main process remains
running, a separately scoped helper observation is needed next.

Controller ownership stays in userspace: a typed begin-only
`--initrd-debug-logging` requires both existing
`--wait-initramfs-in-initcall --without-boot-markers` selectors. Pure host policy
grows 299→356 argument bytes and 317→374 literal command bytes, below the
unchanged 512-byte bound. Before UART, reject conflicting inherited logging
settings, including systemd's underscore/hyphen aliases, invalid types and
unsupported combinations. Persist the selection for guarded continuation;
old state defaults false. Keep all default paths unchanged.

Retain the same p2 artifacts, five load/CRC checks, exact printed/live arguments,
normal guards, masks, initrd/system/kernel and 180-second passive readiness
bound. No kernel rebuild, new masks/targets, alternate PID1, clock/reporter
change, debug shell, global shell tracing or udev verbosity is included.
Complete private logging must survive rolling-buffer eviction. Readiness still
requires a fresh banner/login/prompt and the existing identity guard before any
candidate input. Unknown reads/writes/readiness preserve facts without retries.
Additional console output can perturb timing or block; silence alone cannot
identify the last executed instruction.

Actual-artifact preparation, independent controller review, NEW protected
recovery, one physical capture and safe fixed observations are required before
claiming a result. Keep raw verbose output, identifiers and arguments private.
Task 5b.5 and ordinary root/panel/glass acceptance remain **UNVERIFIED**.
