# Opt-in normal-service VG-Lite descriptor access

Source review, 2026-09-23. This implements the source portion of task 2.5;
actual privileged broker/service isolation and device operation remain
**UNVERIFIED**. The default image still uses Pixman and includes no broker unit.
The separate root diagnostic's recorded isolation pass does not prove this path.

## Why descriptor adoption is feasible

The pinned SDK is `1104236db4d1e47873bd68924f912747b820228c`. Its
`VGLiteKernel/linux/vg_lite_ioctl.c` uses one process-global device descriptor;
all its kernel operations pass through `vg_lite_kernel`. The small local patch
adds descriptor adoption there, without changing the driver or device mode.

The pinned K230 kernel `drivers/gpu/vglite/vg_lite_hal.c` establishes the limits:

- `drv_open` (477–490) allocates `file->private_data`, without binding access to
  the opening process. Its open hook resets/powers the GPU. Thus a broker can
  open and pass one shared open-file description, but must not grant another
  while the first compositor lives.
- `drv_release` frees global device allocations. The broker closes its own
  reference only after SCM_RIGHTS transfer; the compositor retains the same
  open-file description. It does not reopen or proxy individual ioctls.
- `drv_mmap` (606 onward) returns immediately in this source. Actual allocations
  use `vg_lite_hal_map_memory` (278–324), with `vm_mmap`/`remap_pfn_range` in the
  *calling* process. Passing an fd therefore does not leave actual buffer
  mappings in the root broker. Device/cache behavior still requires board proof.

## Authorization contract

The root socket-activated broker accepts only the exact `shell.service`
MainPID running the pinned unwrapped Sway executable, with all four UIDs equal
to `shell`, parent PID 1, no tracer, and non-dumpability established before the
request. It obtains both SO_PEERCRED and SO_PEERPIDFD from the accepted socket;
Linux 6.6 supports the latter (UAPI socket option 77). This binds liveness to
the original socket creator even after descriptor transfer or numeric PID
reuse. MainPID and liveness are checked twice. A live grant blocks subsequent
opens. The root-owned device must already be a character device without any
group/other read/write permission; no chmod or UID-wide grant is used.

Checking non-dumpability alone would leave the earlier startup ptrace window.
The broker also requires Yama `ptrace_scope` 1, 2 or 3. The source-built kernel
configuration enables Yama; the **running board policy still needs checking**.
A sibling app cannot trace the startup process under that policy; requiring
PID 1 as parent excludes a compositor launched as an app's traceable child.
The compositor calls `PR_SET_DUMPABLE=0` before connecting. The broker checks
root ownership of its `/proc/<pid>/fd` inode, which the pinned kernel's
`fs/proc/base.c:task_dump_owner` uses for non-dumpable tasks. CAP_SYS_PTRACE
allows the broker to inspect that otherwise protected proc metadata; its unit
filters debug syscalls and carries no other capability. Missing evidence denies
access and the renderer remains Pixman for that process.

The ordinary Nix Sway wrapper may exec `dbus-run-session`, making the bus
launcher MainPID. The opt-in wrapper starts a session bus first and execs the
exact unwrapped Sway named in broker policy (and sets the normal desktop
environment). It does not broaden authorization to descendants.
No privileged compositor or client is introduced: the normal service remains
`User=shell` and uses the existing Sway/wlroots DRM backend.

## App descriptor and mapping isolation

The C receiver authenticates root SO_PEERCRED, becomes non-dumpable, receives
with MSG_CMSG_CLOEXEC, requires exactly one descriptor and closes all unexpected
ancillary descriptors. SDK adoption uses F_DUPFD_CLOEXEC. The patched SDK
registers `pthread_atfork` before opening/adopting the device, closes the private
fd in children, and prohibits subsequent SDK operations there. All pinned Sway
client launch sites use libc `fork` (`exec_always.c`, `config/bar.c`,
`config/output.c`, `swaynag.c`); Xwayland is disabled. CLOEXEC separately covers
exec paths which bypass the libc fork hook.

The initial SDK mmap and every returned INITIALIZE/ALLOCATE/MAP_MEMORY mapping
receive MADV_DONTFORK, including command, tessellation, power-context and pixel
buffers. The device mutex serializes the complete ioctl/protection interval
with fork. A failed allocation ioctl may leave an unknown driver mapping; a
failed protection operation may leave an inheritable mapping. In either case,
future forked children immediately exit 127 before app code runs. This is an
explicit unsupported-trial failure requiring shell-service restart, **not** a
claim that ordinary app launch remains available after that failure. Existing
apps stay unprivileged. The compositor retains its mappings/device; GPU
completion failures retain the renderer's existing quarantine policy.

This boundary assumes the reviewed compositor and root-owned unit/config, not
arbitrary code already executing inside the compositor. It does not promise
protection from compositor compromise, root, or denial-of-service by same-UID
signals/socket flooding. Ordinary apps have neither a vendor fd nor permission
to open the node or recover the compositor's fd through proc/ptrace.

## Activation and remaining proof

`k230.shell.vgliteAccessTrial = true` is a separate unsupported image/module
opt-in. It selects the MainPID-preserving Sway, creates the private broker
socket/service, and sets the renderer plus exact cache-experiment flag. It
changes no device permissions. Its default is false. Building
`nix build .#shell-compositor-vglite-service --no-link --print-out-paths`
only builds the wrapper/package; it does not activate units or change a board.

Before task 2.5 can close, the reserved operator must run a bounded service
trial with a separately reviewed trial configuration and restoration watchdog,
then record all of the following while the real compositor holds the device:

1. `systemctl show shell.service -p MainPID` equals the real Sway PID;
   `/proc/<pid>/exe` matches the configured unwrapped binary, `/proc/<pid>/fd`
   is root-owned, and `/proc/sys/kernel/yama/ptrace_scope` is 1–3.
2. `journalctl -u k230-vglite-broker.service` records exactly one grant to that
   PID. A separately launched `shell` client requesting `VG1\n` is denied;
   direct device open, proc-fd duplication and ptrace attempts are denied.
3. Actual Sway-launched apps have no VG-Lite fd or vendor mappings before exec
   (instrumented helper) or after exec; their normal UID/capabilities persist.
4. Repeated GPU scene passes, forced Pixman fallback, app launch and shell
   restart succeed; restart grants only the new MainPID after old-owner exit.
   Failure injection/restoration must leave the ordinary Pixman shell active.

No unbounded `systemctl restart` recipe is supplied as a substitute for that
watchdog and operator reservation. The existing root diagnostic remains a
separate bounded path for GPU scene proof. Host evidence and exact commands
are in `docs/evidence/vglite-service-access-host.md`.
