# Physical boot-boundary trial — initcalls returned, login absent

2026-10-03 UTC. Branch `integrate/mainline-probe-path`, worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, bounded evidence base
`174f8c164b870e5ecd9fa327eef202518fb25b20`. Root reserved board/UART for this
single trial; the controller closed serial and released its lock after failure.
No build reservation remains.

The exact matching [host-built bundle](../boot-boundary-build-2026-10-03/README.md)
was staged with command RC0, its own GC root and the protected normal system
retained. Actual ordinary-controller preparation passed before UART use.
Controller preflight passed exact normal system/profile/kernel/init identities,
6.6.36, three active shell services, eight unchanged protected files and absence
of a pending registration marker. Volatile U-Boot selection checked per-load
byte counts and CRC32 plus exact printed bootargs before its one boot command.
The option is `k230.boot_trace=1`, one serial console and the unchanged ordinary
controller's three qualified controls. No earlycon, keep_bootcon or global clock
bypass was added.

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --bundle /nix/store/cr8bv4s6gbchfmcm14c0hrl8agh7zn62-k230-mainline-drm-trial-boot-files \
  --manifest ~/tmp/k230-mainline-boot-trace-board/candidate-manifest.json \
  --normal-report ~/tmp/k230-mainline-boot-trace-board/normal-report.json \
  --state ~/tmp/k230-mainline-boot-trace-board/ordinary-trace-state.json \
  --log ~/tmp/k230-mainline-boot-trace-board/ordinary-trace-uart.log \
  --result ~/tmp/k230-mainline-boot-trace-board/ordinary-trace-result.json
```

Exit **1**: ordinary init login readiness unverified. Fresh Linux 7.3.0-rc5
was observed, then these fixed allowlisted records:

```text
[    0.018228] K230_BOOT_TRACE_V1 seq=1 step=basic-setup-enter
[    0.021599] K230_BOOT_TRACE_V1 seq=2 step=initcalls-enter
[    2.751970] clk: Disabling unused clocks
[    2.752146] PM: genpd: Disabling unused power domains
[    2.752212] K230_BOOT_TRACE_V1 seq=3 step=initcalls-exit
```

There were exactly three marker records. After the 180-second readiness bound
there was no fresh login/root prompt, no `basic-setup-exit` and no init-exec
record. Last UART bytes were received at 19:13:53.477346 UTC; the failed result
was saved at 19:16:49.802410 UTC. The full raw log stays private; its SHA-256,
byte count, exact artifact identities/CRCs and fixed-schema observations are in
[result.json](result.json). No candidate command or guessed reboot/retry was
sent after readiness failed. The user subsequently pressed reset; protected normal recovery is **verified**
in [operator-reset-recovery.json](operator-reset-recovery.json). The new boot ID
differs from preflight, normal system/profile/kernel/init and all eight boot
files match exactly, all three shell services are active, and registration is
absent. The bounded return-to-Home command completed with RC0; the privately reviewed
camera frame shows normal Home icons, clock and background, with glare/focus/
perspective limits. This is normal recovery, not mainline or glass acceptance.
Automatic return
from this failed trial remains **UNVERIFIED**.

## What this narrows, and what it does not prove

Exact realized source
`/nix/store/5k23sa4pbcs651vssp6ybifnr5qc1g9g-linux-mainline-k230-boot-trace-src/init/main.c`
has `do_initcalls()` at1486, its exit marker at1487, then returns at1488.
`kernel_init_freeable()` calls `do_basic_setup()` at1711 and immediately emits
`basic-setup-exit` at1712. There is no original blocking operation between these
sites. The visible `initcalls-exit` proves the initcall loop reached its
post-call marker; it **does not prove that marker returned**.

The helper's lines1472–1475 include emergency enter, printk, emergency exit.
Printk can flush consoles or defer/wake them; emergency exit may wake printing
threads and re-enable preemption. The missing next marker can therefore lie
in emission/flush, cleanup/scheduling or next-record visibility. This result
localizes observed progress and does not establish a console deadlock, a stack,
or a root cause. It does not show initramfs/root mounting stalled. The actual
built configuration has KUnit disabled; the optional gap after basic setup is
not a KUnit workload in this build.

The camera photograph was privately reviewed: the panel appears dark, with
glare and perspective limits. That does not prove its power state or provide
usable-mainline display/touch acceptance. Ordinary root, panel acceptance,
deliberate glass touch, production controls and task5b.5 remain open.

## Next bounded discrimination

After operator reset and protected normal postflight, inspect direct SBI DBCN
public markers around the current marker return boundary. `arch/riscv/include/asm/sbi.h`
and `arch/riscv/kernel/sbi.c` provide a direct call that bypasses printk/console
locks; extension availability, buffer physical addressing, return/error handling
and firmware-side blocking must be checked before implementation or another
boot. Avoid the earlycon writer's zero-progress retry loop. This is a candidate
diagnostic plan, not an implemented fix or hardware claim.
