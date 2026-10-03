# Physical SBI-only marker trial — reached the initramfs wait boundary

2026-10-03 UTC. Coordinator worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, base `e02e553d32eb33e4de6200c4145f075c71e401ba`.
Root reserved board/UART for one attempt and released serial when the
controller stopped. Build, private transfer server and camera are released.
Owned paths are this packet and the mainline task progress note.

The [matching full bundle](../boot-boundary-sbi-only-build-2026-10-03/README.md)
staged with RC0. Fresh protected normal preflight passed exact system/profile/
kernel/init, uname 6.6.36, three active services, all eight unchanged files
and no registration marker. Volatile U-Boot loads passed byte counts/CRCs
and exact printed bootargs before a fresh Linux 7.3.0-rc5 banner. Sole serial
console, both exact marker flags and the three original qualified controls
were retained; no earlycon/keep_bootcon, clock bypass or observer was added.

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --bundle /nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files \
  --manifest ~/tmp/k230-mainline-boot-trace-sbi-only-board/candidate-manifest.json \
  --normal-report ~/tmp/k230-mainline-boot-trace-sbi-only-board/normal-report.json \
  --state ~/tmp/k230-mainline-boot-trace-sbi-only-board/ordinary-sbi-only-state.json \
  --log ~/tmp/k230-mainline-boot-trace-sbi-only-board/ordinary-sbi-only-uart.log \
  --result ~/tmp/k230-mainline-boot-trace-sbi-only-board/ordinary-sbi-only-result.json
```

Exit **1**, no ordinary login within 180 seconds. Exactly these five complete
public labels were received, with no legacy printk marker:

```text
K230_BOOT_SBI_ONLY_V1 step=basic-setup-enter
K230_BOOT_SBI_ONLY_V1 step=initcalls-enter
K230_BOOT_SBI_ONLY_V1 step=initcalls-exit
K230_BOOT_SBI_ONLY_V1 step=basic-setup-exit
K230_BOOT_SBI_ONLY_V1 step=initramfs-wait-enter
```

Firmware UART output adds carriage returns to the fixed record newlines.
The first two direct records precede the printed Linux banner in the same
qualified boot phase; filtering only bytes after that banner would lose them.
These records have no kernel-time field. Source's `Unpacking initramfs...`
message is present; its alternative `Trying to unpack…` branch is disabled by
the actual CONFIG_BLK_DEV_RAM unset configuration. No initramfs-wait-exit,
Freeing-initrd message, init-exec or login was observed. Exact artifacts,
raw hash/byte count/timestamps and the privately reviewed dark-panel photo
observation/limits are in [result.json](result.json). UART stopped receiving
bytes at 20:57:15.514879 UTC (log mtime); the result was saved at 21:00:11.894803 UTC.
No candidate command, guessed reboot or retry followed readiness failure.
Operator reset and normal postflight remain **UNVERIFIED** pending confirmation
and fresh protected recovery. The preceding candidate's reset is historical.

## What this narrows

Actual realized source is
`/nix/store/26hzn5vin6b27cc4mpffc9fn5x8ikwqn-linux-mainline-k230-boot-trace-sbi-only-src`.
In `init/main.c:1778–1786`, basic setup returns before its marker at 1780;
the visible next marker at 1784 proves that preceding SBI call returned and
that execution reached the new diagnostic helper. It does **not** prove
the last SBI ECALL returned or the actual `wait_for_initramfs()` at 1785 was
called. There is no diagnostic printk/emergency helper on this enabled path;
normal kernel logging remains active. This is a narrower observed boundary,
not a root cause or a production fix.

`init/initramfs.c:773–786` waits for the async rootfs cookie;
`:789–796` schedules the worker from a rootfs initcall. Worker
`:720–768` handles built-in/external unpacking, security population, initrd
freeing and deferred fput. The visible unpacking printk does not prove that
printk returned, unpacking completed or the worker cookie finished. Thus no
unpacking, scheduler, UART, clock or wait deadlock is established here.

## Next source-supported comparison under review

The existing `initramfs_async=` parser at `init/initramfs.c:603–608` accepts
false. `initramfs_async=0` still schedules the async worker but waits inside
the rootfs initcall before later initcalls continue. A same-Image volatile
comparison could discriminate overlap with later driver/initcall work; it
would not make unpacking run in the calling task or diagnose a cause.
Read-only audit and meaningful controller argument/guard tests are required
before implementation or another boot. Source-level worker progress and
firmware-return observability remain alternatives after that audit.
Task 5b.5 stays unchecked for ordinary root, usable panel, deliberate glass
and protected return. No archive or shipped-mainline claim is made.
