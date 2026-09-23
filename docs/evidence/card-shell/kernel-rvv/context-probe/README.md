# Vector context probe: full Linux guest passes; current board skips

`rvv-context-probe` has a scalar RV64GC entrypoint. It calls standard hwprobe
and exits 77 with SKIP when V is absent or probing fails. No vector instruction
runs before that gate. Only its separate assembly unit requires RVV 1.0.

Two processes pin themselves to the same allowed CPU and each perform 2,000
checks. An interval timer asynchronously interrupts live vector arithmetic;
the handler changes v8/v9, VL and VTYPE. Assembly waits for a signal, without
calls or syscalls, then verifies control state and writes the vector for scalar
checking. Both processes must complete, and each must have recorded involuntary
context switches. This tests representative state preservation, not the entire
ISA or every register. The pin affects only these test processes.

Linux permits syscalls to clobber vector registers. The probe deliberately does
not demand their preservation across syscalls; see the pinned Xuantie source's
`Documentation/riscv/vector.rst`, section 3. Signal delivery and preemption are
the relevant boundaries here.

```sh
nix build .#rvv-context-probe .#rvv-context-probe-corrupt --no-link --print-out-paths
python3 tools/rvv-context-qemu.py \
  --package /nix/store/4gn2z5fi5szrnflhzjsr1kq3f1b39wqx-k230-rvv-context-probe-riscv64-unknown-linux-gnu-0.1 \
  --corrupt-package /nix/store/yalzjvz5njqm5bqr5bqap1xsnsyfi51s-k230-rvv-context-probe-corrupt-riscv64-unknown-linux-gnu-0.1 \
  --kernel /nix/store/j6x14mc1bz3fh0ylya68qb9yj7qxjcdx-linux-riscv64-unknown-linux-gnu-6.18.52 \
  --output /tmp/new-vector-guest-evidence
```

The actual Nix builds and full-system QEMU harness passed on 2026-09-23:

| Guest case | Observation |
| --- | --- |
| V absent | SKIP, no vector execution |
| VLEN 128 | Both processes pass 2,000 checks; parent 2,068 signals and 524 involuntary switches |
| VLEN 256 | Both processes pass 2,000 checks; parent 2,031 signals and 500 involuntary switches |
| Deliberately corrupt v8 | Both processes reject the data with result 2; harness accepts this expected failure |

`result.json` identifies exact artifacts, commands and QEMU version. Boot logs
are retained with line endings and trailing whitespace normalized. The probe runs as guest PID 1 in a minimal generated initramfs;
its exit after the report causes the expected "Attempted to kill init" panic.
The harness checks the report, not that panic, as its result. No full NixOS
image or compositor is exercised by this separate diagnostic guest.

The earlier negative control failed to emit its report because the probe left
its timer active on error; `previous-reporting-failure.json` preserves that
rejected run. The final probe stops its timer on both success and failure, and
the corrupt control now reports the precise expected error. An absent report
always fails the harness.

## User emulation is insufficient for this test

The same final probe fails with VTYPE result 103 under QEMU user emulation;
`user-emulation-failure.json` records it. QEMU's inspected upstream
[linux-user/riscv/signal.c](https://github.com/qemu/qemu/blob/master/linux-user/riscv/signal.c)
saves scalar and floating-point signal context without vector state. That source
is consistent with the observed failure. The passing full-system guest runs
Linux's own signal handling instead. Do not label the user-emulation failure a
board kernel defect or remove signal clobbering merely to make it pass.

## Current physical board

After a transient missing UART prompt, the final probe transferred with matching
MD5 and ran on the unchanged normal image. `board-skip.json` records SKIP/77,
hwprobe value 59, active shell and seatd, and the unchanged boot ID. No new kernel
was booted and no physical vector operation was performed. The existing Python
capability probe and this compiled probe agree.

Board follow-up: after a verified recoverable vector-kernel boot, run
`timeout 15s /run/card-tools/rvv-context-probe` (or the immutable package binary),
require PASS, then test actual Pixman output and the card workload. Normal-image
SKIP is the expected fallback check, not acceleration acceptance.
