# Same-image marker-free physical comparison — no login

2026-10-03 UTC. Root reserved board/UART for one attempt using reviewed
controller `b50e842b051f0d34231f5a608fe72391da3b9e56`, branch
`integrate/mainline-probe-path`, worktree
`/home/jadams/tmp/k230-mainline-probe-integration`. Owned paths are this
packet and the mainline task progress note. No kernel build or transfer:
the exact staged `brmp1qf9…` bundle and complete closure were reused.

[Controller host proof](../marker-free-controller-host-2026-10-03.md) records
36 passing focused tests and independent review. Fresh protected normal
preflight passed exact identities, eight unchanged files, three services
and registration absence. Five loads/five CRCs and exact printed arguments
passed. Exactly one kernel command-line record equals the expected parameters:
`initramfs_async=0` and the three existing controls retained, both diagnostic
enable tokens removed, immutable init/root and sole serial console unchanged.
No saveenv or protected boot/profile rewrite.

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers \
  --bundle /nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files \
  --manifest ~/tmp/k230-mainline-marker-free-board/candidate-manifest.json \
  --normal-report ~/tmp/k230-mainline-marker-free-board/normal-report.json \
  --state ~/tmp/k230-mainline-marker-free-board/ordinary-state.json \
  --log ~/tmp/k230-mainline-marker-free-board/ordinary-uart.log \
  --result ~/tmp/k230-mainline-marker-free-board/ordinary-result.json
```

Exit **1**, no login within 180 seconds. Fresh Linux 7.3.0-rc5, unpacking,
initrd-memory-free and unused-kernel-image-free messages are visible.
**Zero diagnostic records**, as expected from the disabled base helper gate.
No systemd/login banner. A newly reviewed private camera frame shows a dark
panel, with glare/perspective/focus limits; it cannot establish absence of
userspace. [result.json](result.json) preserves exact artifacts and fixed
observations, raw byte/hash/timestamps and private camera hash. Secret-bearing
raw UART and camera remain private.

The controller released UART and sent no command after unknown readiness.
A new user reset passed fresh protected normal postflight; see
[operator-reset-recovery.json](operator-reset-recovery.json). Exact identities,
eight unchanged files, three services and registration absence passed. Home
IPC returned RC0; a new reviewed private camera frame shows normal Home.
This is operator recovery, not automatic return or mainline/glass acceptance.
The command executed once after this new reset was:

```sh
python3 ~/tmp/k230-mainline-marker-free-board/reset-normal-check.py
```

The checker sends CR only until a fresh normal prompt; then it checks new
boot identity, protected system/profile/kernel/init, all eight files, three
services and registration absence. Unknown prompt sends no Linux command.

## Interpretation and next discriminator

Disabling both diagnostic runtime gates did not restore login in this
single comparison. That outcome does not identify the fault or establish
repeatability; generic exec/return-to-user/scheduling/output or initial
userspace failure remain possible. The preceding enabled-marker run proved
`kernel_execve()` returned, but did not encode its retval or first user
instruction. With markers suppressed this attempt supplies no equivalent
exec boundary observation. Regular printk and serial console remained enabled.

Read-only inspection confirms this same initrd contains an ELF RISC-V
systemd `/init` and Bash `/bin/sh`. A separately reviewed minimal-PID1
comparison could retain these artifacts/controls and select `/bin/sh` as
initial executable. A fresh shell and guarded receipt would prove actual
userspace execution and console TX/RX; no receipt would remain ambiguous.
That comparison must be recorded as a diagnostic shell, not ordinary NixOS
root or shipped capability. Controller support and normal recovery are still
required. No combined console-null/loglevel or kernel rebuild is proposed here.
Ordinary root, panel/glass, automatic return, production and task 5b.5 stay
**UNVERIFIED**. This change remains open and unarchived.
