# Compositor-only VG-Lite diagnostic access

Source audit and host harness, 2026-09-23. This is not a normal-session GPU
access implementation and is not board execution evidence.

## Source-grounded constraints

The accepted trial keeps the existing Sway/wlroots DRM owner and forbids giving
ordinary Wayland clients `/dev/vg_lite`. It does not require the *diagnostic*
compositor to use the normal service's identity. A bounded root-owned Sway with
externally launched `shell` clients can exercise actual scene passes while
preserving that boundary. It cannot prove the whole normal shell experience.

Pinned SDK `1104236db4d1e47873bd68924f912747b820228c`,
`buildroot-overlay/package/vg_lite/VGLiteKernel/linux/vg_lite_ioctl.c:66-120`:

- A process-global `device` is lazily opened directly from `/dev/vg_lite` with
  `O_RDWR`, without `O_CLOEXEC`. The fd and its mmap are retained for later
  operations; there is no public descriptor-adoption API.
- Therefore simply granting the `shell` UID access exposes it to every normal
  application. Passing a descriptor also requires closing it across child
  exec and preventing same-UID `/proc/<compositor>/fd` access.

Pinned Sway 1.12 source (`/nix/store/2j7grygxd5da5r214vzz3y8b54rr739k-source`):

- `sway/main.c` has no root-UID refusal or privilege drop. In
  `sway/commands/exec_always.c:52-65`, a child forks and executes `sh -c`
  without changing UID. Running the ordinary config as root would launch
  privileged clients.
- `sway/ipc-server.c:638` dispatches `IPC_COMMAND` to `execute_command`.
  Connection handling at line 148 has no peer-UID authorization gate. Root
  compositor IPC must be unreachable by clients: hiding its pathname alone
  does not establish that boundary.
- `sway/config/output.c:1204` also forks/executes swaybg. Even a solid-color
  `output ... bg` command can spawn a privileged Wayland client. The harness
  disables `swaybg_command` as well as `swaynag_command`, omits all bar/exec/
  include/binding commands, and disables Xwayland. Those two commands explicitly
  accept `-` to disable their helpers, as their command implementations show.

## Bounded harness

`tools/vglite-root-scene-trial.py` creates only transient units and files under a
unique root-created `/run/k230-vglite-trial-*` directory. It refuses to replace
an inactive shell or use a non-Nix-store executable. Its fixed root config has
no privileged client launch command. Control files and IPC are in a root-only
0700 directory; only the separate Wayland socket receives `shell` group access.
No GPU, DRM or input device permissions are changed.

A transient root Sway unit conflicts with `shell.service`, using systemd job
ordering to stop the old owner before the diagnostic starts. The client runs
in an independent system-manager unit with `User=shell`, `Group=shell`, no
capabilities, `NoNewPrivileges=yes`, private devices, and a separate runtime
directory. Its inherited environment excludes root Sway IPC and the GPU flag.
It is launched by PID 1, not forked by the compositor, so it cannot inherit the
vendor library's descriptor. Root compositor IPC remains private throughout.

Recovery is armed before replacing the shell. A monotonic watchdog, root
compositor `RuntimeMaxSec`, `KillMode=control-group`, and `ExecStopPost` remain
managed by systemd even if the controller is killed. The stop hook queues the
normal shell restart non-blockingly to avoid deadlock with the compositor's
own conflicting stop job. Ordinary completion/error cleanup waits for the
compositor cgroup to stop, starts the normal shell, and checks it active before
removing the watchdog/files. Failed recovery preserves those files and reports
a failure; it is never reported as a successful restoration.

## Host checks and their limits

```sh
python3 tests/vglite/test_root_trial.py
```

Passed: six behavior tests cover success, failure while arming/starting/waiting/
sharing/running a client, recovery failure retaining the watchdog, fixed client
credentials and capability/device restrictions, root-private file permissions,
no root client-execution config path, no argument interpolation, inactive-shell
refusal, and actual execution of both generated recovery scripts against a
recording systemctl substitute. No board or system-manager unit is touched by
these tests. Python syntax compilation also passed.

A real user-manager subprocess check passed with
`NoNewPrivileges=yes`: UID 1000, effective capabilities zero. The same test with
an empty capability bounding set failed at `218/CAPABILITIES`, because this
unprivileged user manager cannot perform the production root manager's
capability setup. It was not accepted as a production credential test.

The required real multi-UID isolation check is supplied as:

```sh
sudo python3 tests/vglite/check_root_trial_credentials.py --user shell
```

It uses a temporary root-private directory under `/run`, a shared socket and a
regular-file GPU fixture. It opens **no DRM or VG-Lite device**, does not replace
the normal shell, and launches only a bounded credential-check client unit. It
checks actual peer credentials, zero effective capabilities, no-new-privileges,
and denied access to private IPC, the GPU fixture and the root process's held
fixture descriptor. The current host is UID 1000 without passwordless sudo;
this check returned `SKIP` (77). Subordinate-UID namespace mappings also failed.
**Actual privileged unit credentials/isolation remain UNVERIFIED.** Run this
check as root on a suitable host, or as the reserved board operator, before the
diagnostic compositor trial. A skipped check is not a pass.

The coordinator subsequently ran this exact isolation prerequisite as root on
the reserved board and it passed. See
`docs/evidence/vglite-isolation/README.md` and its actual output. This supplies
the missing multi-UID observation; GPU and compositor-session tests remain
separate and unverified.

## Operator command after the isolation prerequisite

Import the opt-in Sway and a trusted, self-terminating Wayland probe into the
board store. Then, as the one reserved board operator, run the isolation test
and only on success run the harness. Replace `<probe>` with its actual store
executable and supply its own bounded arguments:

```sh
python3 tests/vglite/check_root_trial_credentials.py --user shell &&
python3 tools/vglite-root-scene-trial.py --seconds 20 \
  --compositor /nix/store/r9z3grgfnq82mvjyvnr97jyqqp302f6s-sway-1.12/bin/sway \
  -- <probe> <probe-arguments>
```

The harness captures compositor journal lines and restoration status. Commit
those logs with output samples and camera observations before claiming actual
GPU scene/scanout behavior. This diagnostic deliberately omits the normal
launcher/keyboard/client startup and therefore cannot close interaction task
3.3. No such command was run on hardware during this work.

## Normal-service option remains open

A narrower normal-service solution would patch the source-built library to
adopt a supplied descriptor with `FD_CLOEXEC`, and arrange privileged delivery
only to the exact compositor PID. The compositor must become non-dumpable
before receiving it; same-UID `/proc` descriptor access otherwise undermines
an fd-only design. A broker authenticating merely `shell` UID is insufficient.
It could validate the systemd unit's exact main PID through `SO_PEERCRED` and
reject every other peer. Any such design needs explicit adoption/lifetime,
child-exec, same-UID-access, PID-race, and recovery tests. It is not implemented
by this diagnostic harness and remains an open device-access gate before the
normal Sway service can use the experimental renderer.
