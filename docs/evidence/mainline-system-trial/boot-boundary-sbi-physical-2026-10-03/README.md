# Physical direct-SBI boundary trial — basic setup completed, login absent

2026-10-03 UTC. Coordinator branch `integrate/mainline-probe-path`, worktree
`/home/jadams/tmp/k230-mainline-probe-integration`; evidence base
`0a345adf34b9b6d8135161d5228d164b27b7a1ef`. Root reserved board/UART for this
single trial and released it when the controller stopped. Build and transfer
server reservations are also released.

The exact [matching direct-SBI bundle](../boot-boundary-sbi-build-2026-10-03/README.md)
passed staging RC0 and protected normal preflight: exact normal system/profile/
kernel/init, uname 6.6.36, three active shell services, eight unchanged protected
files and no registration marker. The selected Image/initrd/DT/bootargs matched
host proof and volatile U-Boot loads passed byte-count/CRC and printed-argument
gates. Both runtime flags and the original three qualified controls were used;
no earlycon/keep_bootcon, global clock bypass or console registration was added.

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --bundle /nix/store/j0ad6h3s23s5zlwizn3mbiw6cs98s4qn-k230-mainline-drm-trial-boot-files \
  --manifest ~/tmp/k230-mainline-boot-trace-sbi-board/candidate-manifest.json \
  --normal-report ~/tmp/k230-mainline-boot-trace-sbi-board/normal-report.json \
  --state ~/tmp/k230-mainline-boot-trace-sbi-board/ordinary-sbi-state.json \
  --log ~/tmp/k230-mainline-boot-trace-sbi-board/ordinary-sbi-uart.log \
  --result ~/tmp/k230-mainline-boot-trace-sbi-board/ordinary-sbi-result.json
```

Exit **1**, ordinary init login readiness unverified. After the fresh Linux
7.3.0-rc5 banner, this fixed allowlisted sequence was received:

```text
[    0.018364] K230_BOOT_TRACE_V1 seq=1 step=basic-setup-enter
[    0.021732] K230_BOOT_TRACE_V1 seq=2 step=initcalls-enter
K230_BOOT_SBI_V1 point=initcalls-before
[    2.774786] K230_BOOT_TRACE_V1 seq=3 step=initcalls-exit
K230_BOOT_SBI_V1 point=initcalls-after
K230_BOOT_SBI_V1 point=basic-before
[    2.801471] K230_BOOT_TRACE_V1 seq=4 step=basic-setup-exit
K230_BOOT_SBI_V1 point=basic-after
```

All four direct records and legacy seq1–4 were complete. No next
`initramfs-wait-enter` or login/root prompt appeared within the 180-second bound.
Last UART bytes arrived at 20:09:15.604722 UTC; failed result was saved at
20:12:11.958290 UTC. Exact artifacts, raw-log SHA/byte count/timestamps and
qualified observations are in [result.json](result.json). Raw UART remains
private. No candidate command, guessed reboot or retry was sent after failure.
The user then confirmed reset. The bounded fresh-prompt checker exited1
after90seconds with **zero UART bytes**, before sending any Linux command.
The privately reviewed camera frame shows a dark panel, with glare/focus/
perspective limits; its power state is unknown. See
[operator-reset-check.json](operator-reset-check.json). UART and camera are
released; a power cycle was requested and confirmation remains pending.
Protected normal recovery and automatic return remain **UNVERIFIED**.

## What the records establish

In the additionally patched source, `basic-before` at main.c:1758 follows
`do_basic_setup()`; `basic-after` at 1760 follows the original marker at1759.
The analogous initcalls pair surrounds the original post-initcall marker.
Thus `do_initcalls()` and `do_basic_setup()` returned, and both suspect
printk/emergency marker helpers returned far enough to reach their trailing
SBI calls. This attempt progressed past the previous visible boundary.
It does **not** establish a console deadlock or its resolution; extra output
perturbs timing.

The final visible `basic-after` record does not prove its ECALL returned.
`arch/riscv/kernel/sbi_ecall.c:37–46` includes firmware return and a return
trace hook after bytes may already be visible. KUnit at main.c:1762 is an inline
no-op under the actual disabled configuration (`include/kunit/test.h:402–408`).
The next diagnostic helper at 1764 precedes the actual initramfs wait at 1765.
The remaining gap includes final SBI return, next helper execution/emission
and scheduling. This transcript does not prove the initramfs wait was called
or identify it as the stall. Ordinary root/panel/glass/production/recovery
acceptance remains open; task 5b.5 stays unchecked.

## Next bounded discriminator

After committing this result and verified reset recovery, review a separate
opt-in variant that uses one direct-SBI attempt for each original diagnostic
marker instead of printk/emergency output in that enabled mode. Preserve both
current variants and all normal outputs. A fixed public step table, regular
rodata aligned/page-contained buffers, runtime/config/extension gates and the
original 32-attempt cap are necessary. No polling, printk fallback, new console
or kernel-driver change. This would isolate diagnostic-instrumentation behavior
without disabling normal kernel logging; it would not prove a root cause.
Source/native/object/identity and full matching artifact checks remain necessary
before another physical trial. No such variant is implemented by this evidence
increment.


## Subsequent user-confirmed reset recovery

After the initial zero-byte reset check above, the user confirmed another
reset. The fresh protected normal postflight now passed: a different boot ID,
exact system/profile/kernel/init, all eight boot hashes, three active services
and registration absence. See [operator-reset-recovery.json](operator-reset-recovery.json).
The bounded Home IPC command returned RC0; the reviewed private camera frame
shows normal Home icons, clock and wallpaper, with glare/focus/perspective
limits. This verifies operator reset recovery only. The failed mainline login
trial, last-SBI-return ambiguity, automatic-return UNVERIFIED marker and
ordinary root/panel/glass/task5b.5 gates remain unchanged. No power-cycle
claim is made from the user's reset confirmation.
