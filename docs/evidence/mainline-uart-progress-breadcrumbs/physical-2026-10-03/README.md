# Physical worker-entry and first-post-sleep comparison

The new temporary boot delivered both fixed breadcrumbs, a matching fresh Bash
receipt, and numeric samples 0 and 1. No samples 2–5 or normal return were
observed during the 180.084-second passive capture. This is a useful diagnostic
result, **not** successful ordinary mainline boot or recovery acceptance.

Root alone operated the board/UART from worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, controller revision `90b1e288`. The full matching
build used frozen `2a548135`; reviewed source and controller code were unchanged
by the intervening host-evidence commit. The [public result](result.json)
records exact artifacts, command return 2, UTC timestamps and private capture
SHA256/size. Raw UART, nonce, boot IDs, baseline and transfer URL remain private.
Camera/glass evidence was not obtained.

The [exact/full host proof](../exact-full-host/README.md) and
[actual positive preparation](../positive-controller-host/README.md) passed
before hardware access. Transfer/import staged eight new paths with return 0;
the complete closure is GC-rooted on the board. The controller freshly checked
protected normal identities, boot hashes and services, rebooted into U-Boot,
verified each load's size/CRC and exact volatile arguments, then booted the
selected matching Image/initrd/DT. Persistent normal boot selection was unchanged.

Operator command:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py \
  --mode minimal --same-image-shell-pid1 --uart-progress \
  --uart-progress-breadcrumbs \
  --bundle /nix/store/mhq10143lsmgr6wlll431a8s3ggb8q6m-k230-mainline-drm-trial-boot-files \
  --manifest "$PRIVATE_RUN/candidate-manifest.json" \
  --normal-report "$PRIVATE_RUN/normal-report.json" \
  --log "$PRIVATE_RUN/trial.private.log" \
  --result "$PRIVATE_RUN/result.private.json"
```

## Observations and limits

The fresh 7.3.0-rc5 banner, exact received arguments, `/bin/sh` entry and primary
Bash prompt qualified one receipt stimulus. The actual parser observed its
matching response. A provisional raw-line monitor missed that response because
the real terminal prefixes it with bracketed-paste disable and CR; the completed
controller result, which handles that framing, supersedes the provisional
monitor. Exactly one stimulus was attempted. No retry, proc command, guard or
candidate reboot followed. No parser protocol error was recorded.

[Fixed records](fixed-records.txt) preserve only the four constant-schema lines.
Worker-entry arrived before the stimulus; first-post-sleep and samples 0/1 arrived
after it. This is host arrival order, not causal hardware receive timing.
Entry proves the worker reached its first SBI write. Post-sleep proves that entry
call returned and the first sleep completed. Sample 1 proves progression beyond
the post-sleep and sample 0 writes, and a second sleep. A visible sample 1 does
**not** prove its own SBI call returned. Missing sample 2 leaves return from that
call, subsequent sleep/scheduling and later output unresolved.

[Two-sample deltas](two-sample-deltas.json) show monotonic time advancing by
5.116997479 seconds, jiffies by 1280 and timer IRQ count by 252. This establishes
timer/scheduling progress over that interval; it does not establish future
progress or overall timer/interrupt health. Both snapshots report status 0,
UART IRQ 12, timer IRQ 10, UART IRQ count 30, RX 89 and TX 292. Cached UART
accounting is unchanged between the two samples, as expected without further
input. The 89-byte receipt command and matching Bash receipt establish command
execution, but the counters have no pre-stimulus baseline or per-byte identity.

In the selected `k5a5…` source, `8250_core.c`'s snapshot validates UART0 binding
and copies cached fields under a try-lock; it does not read live IIR/LSR/IER.
`8250_port.c` updates RX accounting before error-mask/SysRq/flip insertion.
UART TX accounting does not count direct-SBI output. IRQ aggregates count mapped
Linux interrupts, not successful TTY delivery. These source facts constrain
interpretation; none identifies why the previous reporter boot was silent or
why this one stopped producing records after sample 1.

## Recovery and next boundary

The controller sent no candidate reboot. Normal return was not observed, so a
new operator reset was requested only after capture completed. Guarded fresh
normal postflight is pending. Automatic return, ordinary mainline `/init`, usable
root, panel/glass and task 5b.5 remain **UNVERIFIED**.

The next source audit must distinguish the sample 1 SBI return from the following
sleep boundary. Repeating the same capture or treating the earlier missing
receipt as current RX failure would not be grounded in this result. Any added
after-write marker or changed input policy needs a separately reviewed typed
comparison, exact artifact proof and fresh protected normal recovery.
