# Same-image initramfs/initcall physical comparison — reached init-exec exit

2026-10-03 UTC. Coordinator branch `integrate/mainline-probe-path`,
worktree `/home/jadams/tmp/k230-mainline-probe-integration`, evidence base
`636e24e9b321560479c00d041caf4fbc26dd2590`. Root reserved board/UART for
one attempt and released it on controller exit. No build or transfer was
needed: the exact previously staged `brmp1qf9…` Image/initrd/DT/bootargs/
wrapper and complete closure were reused. Owned paths are this packet and
the mainline task progress note.

The [reviewed controller](../initramfs-initcall-controller-host-2026-10-03.md)
and its 29 focused tests passed CI. Fresh protected normal preflight passed
exact identities, uname 6.6.36, three active services, all eight unchanged
files and registration absence. All five volatile loads/CRCs passed, and
printed U-Boot arguments were exactly the previous candidate plus one
`initramfs_async=0` token. Sole serial/immutable init/root and the three
original qualified controls were retained; no saveenv or boot-file rewrite.

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall \
  --bundle /nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files \
  --manifest ~/tmp/k230-mainline-initramfs-initcall-board/candidate-manifest.json \
  --normal-report ~/tmp/k230-mainline-initramfs-initcall-board/normal-report.json \
  --state ~/tmp/k230-mainline-initramfs-initcall-board/ordinary-state.json \
  --log ~/tmp/k230-mainline-initramfs-initcall-board/ordinary-uart.log \
  --result ~/tmp/k230-mainline-initramfs-initcall-board/ordinary-result.json
```

Exit **1**, no login within 180 seconds. The qualified boot phase contains
exactly 18 complete fixed SBI-only records, no legacy marker:

```text
K230_BOOT_SBI_ONLY_V1 step=basic-setup-enter
K230_BOOT_SBI_ONLY_V1 step=initcalls-enter
K230_BOOT_SBI_ONLY_V1 step=initcalls-exit
K230_BOOT_SBI_ONLY_V1 step=basic-setup-exit
K230_BOOT_SBI_ONLY_V1 step=initramfs-wait-enter
K230_BOOT_SBI_ONLY_V1 step=initramfs-wait-exit
K230_BOOT_SBI_ONLY_V1 step=root-console-enter
K230_BOOT_SBI_ONLY_V1 step=root-console-exit
K230_BOOT_SBI_ONLY_V1 step=init-access-enter
K230_BOOT_SBI_ONLY_V1 step=init-access-exit
K230_BOOT_SBI_ONLY_V1 step=integrity-keys-enter
K230_BOOT_SBI_ONLY_V1 step=integrity-keys-exit
K230_BOOT_SBI_ONLY_V1 step=async-wait-enter
K230_BOOT_SBI_ONLY_V1 step=async-wait-exit
K230_BOOT_SBI_ONLY_V1 step=initmem-readonly-enter
K230_BOOT_SBI_ONLY_V1 step=initmem-readonly-exit
K230_BOOT_SBI_ONLY_V1 step=init-exec-enter
K230_BOOT_SBI_ONLY_V1 step=init-exec-exit
```

`Unpacking initramfs...` and the initrd-memory-free message are visible.
The namespace pair did not run; no systemd or login banner appeared. Exact
artifacts, records, raw hash/byte count/last-write and saved-result timestamps
are in [result.json](result.json). Raw capture remains private and preserves
the whole boot phase, including direct records before the printed Linux
banner. No candidate command, guessed reboot or retry was sent after failure.
A new user reset passed fresh protected normal postflight; see
[operator-reset-recovery.json](operator-reset-recovery.json). Exact identities,
three services, eight unchanged boot files and registration absence passed.
Home IPC returned RC0 and a newly reviewed private camera frame shows normal
Home icons, clock and background. This is operator recovery, not automatic
return or mainline/glass acceptance. No camera frame was captured
for this attempt; the earlier dark candidate photo is not reused as proof.

## What this establishes

Exact source remains
`/nix/store/26hzn5vin6b27cc4mpffc9fn5x8ikwqn-linux-mainline-k230-boot-trace-sbi-only-src`.
`init/initramfs.c:789–798` always schedules the same worker and joins its
domain/cookie inside the rootfs initcall when this option is false. The
complete `initcalls-exit` at main.c:1555 proves that earlier join returned.
The later wait-exit and subsequent labels prove progress through the
original previously missing boundary. This comparison records different progress with the changed overlap/order;
repetition would be needed to establish causality. It does not name a faulty
driver, console, clock or a production fix.

main.c:1581–1583 emits `init-exec-exit` after `kernel_execve()` returns, for
**both success and error**. The marker carries neither retval nor selected
filename. Successful ELF installation sets user registers and returns 0
(`fs/binfmt_elf.c:1375–1379`, `fs/exec.c:1867–1878`) before first userspace
execution. Success then returns kernel_init at main.c:1693–1696;
`arch/riscv/kernel/process.c:228–232` performs syscall exit-to-user work,
and `arch/riscv/kernel/entry.S:363–369,303–320` restores regs/EPC and executes
sret. The last marker's own SBI return and first userspace instruction
therefore remain **UNVERIFIED**. No exec failure is inferred from this label.
The initial ramdisk path is `/init`; it is tried before the selected stage2
`init=`. No namespace labels is consistent with accessible `/init`, but
those labels do not encode the access result.

The helper/state/table use ordinary text/data/rodata after init cleanup,
with fixed aligned buffers and no user/VMAP stack address. Actual config
enables MMU/RISCV_SBI/STRICT_KERNEL_RWX/VMAP_STACK; KUnit is disabled. No
lifetime fault, userspace-transition failure or console deadlock is proved.

## Next bounded discriminator

After verified reset recovery, preserve this same Image/initrd/DT and
`initramfs_async=0`, but remove both exact runtime trace-enable tokens only
from volatile arguments after validating the original artifact. Base helper
main.c:1510 then returns immediately at all diagnostic sites, eliminating
diagnostic SBI/printk/emergency perturbation while preserving normal logging.
Appending `=0` does not override a previously parsed `=1`; removing only the
SBI-only flag restores legacy printk markers. A reviewed controller opt-in
and meaningful exact-argument/resume/unknown tests are needed before a boot.
Do not combine console-null or loglevel changes with this discriminator.
Systemd/login/guarded root would be positive evidence; another quiet failure
would remain unknown. Ordinary root, panel/glass/automatic return and task 5b.5
stay open. No production or archive acceptance follows.


## Exact kernel command-line receipt

A separate read-only check found exactly one `Kernel command line:` record
in this private capture. Its complete parameter bytes equal the controller's
expected same-image comparison, including one `initramfs_async=0`, both
marker flags, sole serial/immutable init/root and the original three controls.
This supplements U-Boot printenv proof with the kernel's received arguments.
The comparison changed observed progress; one run does not establish a
repeatable causal fix or userspace acceptance.
